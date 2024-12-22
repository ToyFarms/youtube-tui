from textual.app import ComposeResult
from textual.binding import Binding
from textual.widget import Widget
from textual.widgets import ListView, ListItem, Label

from model import YoutubeVideo


class YoutubeVideosView(Widget):
    BINDINGS = [
        Binding("enter", "select_cursor", "Select"),
        Binding("k", "cursor_up", "Cursor up"),
        Binding("j", "cursor_down", "Cursor down"),
    ]

    action_select_cursor = lambda self: self.query_one(ListView).action_select_cursor()
    action_cursor_up = lambda self: self.query_one(ListView).action_cursor_up()
    action_cursor_down = lambda self: self.query_one(ListView).action_cursor_down()

    def compose(self) -> ComposeResult:
        yield ListView()

    def update_videos(self, videos: list[YoutubeVideo]) -> None:
        listview = self.query_one(ListView)
        listview.clear()

        for video in videos:
            listview.append(YoutubeVideoView(video))


class YoutubeVideoView(ListItem):
    def __init__(self, video: YoutubeVideo) -> None:
        super().__init__()

        self.video = video

    def compose(self) -> ComposeResult:
        yield Label(self.video.title)
