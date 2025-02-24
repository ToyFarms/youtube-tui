# pyright: reportUnknownMemberType=false, reportUnknownLambdaType=false, reportUnknownArgumentType=false
from typing import Callable, final

from utils import expect

import mpv


@final
class AudioPlayer:
    def __init__(self, filepath: str | None = None, buffer_size: str = "100K") -> None:
        def my_log(loglevel: str, component: str, message: str) -> None:
            print("[{}] {}: {}".format(loglevel, component, message))

        self.player = mpv.MPV(ytdl=True, log_handler=my_log, vid="no")
        self.player.demuxer_max_bytes = buffer_size
        self.filepath = filepath

    def register_callback(self, event: str, fn: Callable[[object], None]) -> None:
        self.player.observe_property(event, lambda _, value: fn(value))

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
        return self.player.pause

    def stop(self) -> None:
        self.player.stop()

    def terminate(self) -> None:
        self.player.terminate()

    def update(self, filepath: str) -> None:
        self.filepath = filepath

    def get_duration(self) -> float:
        return expect(self.player.duration, float)

    def get_current_time(self) -> float:
        return expect(self.player.time_pos, float)
