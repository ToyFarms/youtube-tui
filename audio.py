import threading
import pyaudio
import av
import numpy as np

from typing import Callable
from collections import deque

import utils


# NOTE: the player buffering system is kinda ass, and i couldnt bother to fix it
class AudioPlayer:
    def __init__(
        self,
        filepath: str | None = None,
        sample_rate: int = 48000,
        frame_callback: Callable[["AudioPlayer", np.ndarray], None] | None = None,
        time_callback: Callable[[float], None] | None = None,
        buffer_ahead: float = 20,
    ) -> None:
        self.filepath = filepath
        self.sample_rate = sample_rate
        self.buffer_ahead = buffer_ahead

        if self.filepath:
            self._setup_av_container()

        self.resampler = av.AudioResampler(
            format="flt",
            layout="stereo",
            rate=self.sample_rate,
        )

        with utils.suppress_portaudio_error():
            self.pa = pyaudio.PyAudio()

        self.buffer = np.array([], dtype=np.float32)
        self.buffer_start_time = 0
        self.playback_time = 0

        self.stream = self.pa.open(
            rate=self.sample_rate,
            channels=2,
            format=pyaudio.paFloat32,
            frames_per_buffer=1024,
            output=True,
            stream_callback=self._audio_callback,
        )

        self.paused = threading.Event()
        self.stop_event = threading.Event()
        self.decoder_thread = None
        self.frame_callback = frame_callback
        self.time_callback = time_callback
        self._lock = threading.Lock()

        self.pending_seeks = deque()
        self.seeking = threading.Event()
        self.decoding_active = threading.Event()

    def _setup_av_container(self):
        try:
            self.container = av.open(self.filepath)
            self.audio_stream = self.container.streams.audio[0]
            self.frame_generator = self.container.decode(audio=0)
        except Exception as e:
            raise RuntimeError(f"Failed to open audio file: {e}")

    def _get_buffer_duration(self):
        return len(self.buffer) / (self.sample_rate * 2)

    def _audio_callback(self, in_data, frame_count, time_info, status):
        if status:
            print(f"Stream callback error: {status}")

        if self.stop_event.is_set() or self.paused.is_set():
            return (
                np.zeros(frame_count * 2, dtype=np.float32).tobytes(),
                pyaudio.paContinue,
            )

        with self._lock:
            if len(self.buffer) < frame_count * 2:
                if not self.decoding_active.is_set():
                    self.decoding_active.set()
                return (
                    np.zeros(frame_count * 2, dtype=np.float32).tobytes(),
                    pyaudio.paContinue,
                )

            data = self.buffer[: frame_count * 2].copy()
            self.buffer = self.buffer[frame_count * 2 :]
            frame_duration = frame_count / self.sample_rate
            self.playback_time = self.buffer_start_time + frame_duration
            self.buffer_start_time += frame_duration

            if self.time_callback:
                self.time_callback(self.playback_time)

            if not self.seeking.is_set():
                samples_needed = int(self.buffer_ahead * self.sample_rate * 2)
                if len(self.buffer) < samples_needed:
                    self.decoding_active.set()

        if self.frame_callback:
            self.frame_callback(self, data)

        return (data.tobytes(), pyaudio.paContinue)

    def _handle_seek(self, target_time: float) -> bool:
        """Handle seeking to a specific time. Returns True if seek was successful."""
        try:
            buffer_duration = self._get_buffer_duration()
            time_diff = target_time - self.buffer_start_time

            if 0 <= time_diff <= buffer_duration:
                samples_to_skip = int(time_diff * self.sample_rate * 2)
                with self._lock:
                    self.buffer = self.buffer[samples_to_skip:]
                    self.buffer_start_time = target_time
                    self.playback_time = target_time
                return True

            seek_pts = int(target_time / self.audio_stream.time_base)
            self.container.seek(seek_pts, stream=self.audio_stream)
            with self._lock:
                self.buffer = np.array([], dtype=np.float32)
                self.buffer_start_time = target_time
                self.playback_time = target_time
                self.frame_generator = self.container.decode(audio=0)
            return True

        except Exception as e:
            print(f"Seek error: {e}")
            return False

    def _decode_audio(self):
        while not self.stop_event.is_set():
            while self.pending_seeks and not self.stop_event.is_set():
                target_time = self.pending_seeks.popleft()
                self.seeking.set()
                success = self._handle_seek(target_time)
                if success:
                    self.decoding_active.set()
                self.seeking.clear()

            self.decoding_active.wait()
            if self.stop_event.is_set():
                break

            try:
                frame = next(self.frame_generator)
                resampled = self.resampler.resample(frame)

                for resampled_frame in resampled:
                    arr = resampled_frame.to_ndarray()
                    if len(arr.shape) == 2:
                        arr = arr.reshape(-1)

                    with self._lock:
                        if self.pending_seeks:
                            break
                        self.buffer = np.concatenate([self.buffer, arr])
                        samples_needed = int(self.buffer_ahead * self.sample_rate * 2)
                        if len(self.buffer) >= samples_needed:
                            self.decoding_active.clear()

            except StopIteration:
                self.decoding_active.clear()
                break
            except Exception as e:
                print(f"Decoder error: {e}")
                self.stop_event.set()
                break

    def play(self) -> None:
        if self.decoder_thread and self.decoder_thread.is_alive():
            return

        self.stop_event.clear()
        self.decoding_active.set()
        self.stream.start_stream()
        self.decoder_thread = threading.Thread(target=self._decode_audio, daemon=True)
        self.decoder_thread.start()
        self.paused.clear()

    def seek_to(self, s: float) -> None:
        """Seek to specific time in seconds"""
        s = max(0, float(s))
        self.pending_seeks.append(s)
        self.decoding_active.set()

    def seek(self, offset: float) -> None:
        """Seek by offset in seconds"""
        self.seek_to(self.playback_time + offset)

    def pause(self) -> None:
        self.paused.set()

    def resume(self) -> None:
        self.paused.clear()
        self.decoding_active.set()

    def toggle_playback(self) -> bool:
        if self.paused.is_set():
            self.resume()
            return True
        else:
            self.pause()
            return False

    def stop(self) -> None:
        self.stop_event.set()
        self.decoding_active.set()
        if self.decoder_thread:
            self.decoder_thread.join()
        if hasattr(self, "container"):
            self.container.close()

    def terminate(self) -> None:
        self.stop()
        self.stream.stop_stream()
        self.stream.close()
        self.pa.terminate()

    def update(self, filepath: str) -> None:
        self.stop()
        self.filepath = filepath
        self._setup_av_container()
        self.buffer = np.array([], dtype=np.float32)
        self.buffer_start_time = 0
        self.playback_time = 0

