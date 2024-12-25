import threading
import pyaudio
import av
import numpy as np

from typing import Callable
from collections import deque

import utils
import mpv


class AudioPlayer:
    def __init__(
        self,
        filepath: str | None = None,
        sample_rate: int = 48000,
        buffer_ahead: float = 20,
    ) -> None:
        def my_log(loglevel, component, message):
            print("[{}] {}: {}".format(loglevel, component, message))

        self.player = mpv.MPV(ytdl=True, log_handler=my_log, vid="no")
        self.filepath = filepath

    def register_callback(self, event: str, fn) -> None:
        self.player.observe_property(event, fn)

    def play(self) -> None:
        self.player.play(self.filepath)
        self.resume()

    def seek_to(self, s: float) -> None:
        self.player.seek(s, "absolute")

    def seek(self, offset: float) -> None:
        self.player.seek(offset)

    def pause(self) -> None:
        self.player.pause = True

    def resume(self) -> None:
        self.player.pause = False

    def toggle_playback(self) -> bool:
        self.player.pause = not self.player.pause

    def stop(self) -> None:
        self.player.stop()

    def terminate(self) -> None:
        self.player.terminate()

    def update(self, filepath: str) -> None:
        self.filepath = filepath

    def get_duration(self) -> float:
        return self.player.duration

    def get_current_time(self) -> float:
        return self.player.time_pos

