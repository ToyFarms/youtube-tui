from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import HorizontalGroup
from textual.widget import Widget
from textual.widgets import ListView, ListItem, Label

from model import YoutubeVideo


class YoutubeVideosView(ListView):
    BINDINGS = [
        Binding("enter", "select_cursor", "Select"),
        Binding("k", "cursor_up", "Cursor up"),
        Binding("j", "cursor_down", "Cursor down"),
    ]

    def update_videos(self, videos: list[YoutubeVideo]) -> None:
        self.clear()

        for video in videos:
            self.append(YoutubeVideoView(video))


class YoutubeVideoView(ListItem):
    def __init__(self, video: YoutubeVideo) -> None:
        super().__init__()

        self.video = video

    def compose(self) -> ComposeResult:
        yield Label(self.video.title)
