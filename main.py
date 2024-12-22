from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widget import Widget
from textual.widgets import Input, Label, ListView

import shelve

from api import YoutubeAPI
from model import YoutubeModel
from view import YoutubeVideosView
from controller import YoutubeController


DEBUG_DATA = True


class Youtube(App):
    BINDINGS = [
        Binding("/", "focus_input", "Focus input"),
    ]

    CSS = """
    Input {
        dock: top;
        height: 1;
        border-top: none;
        border-bottom: none;
    }
    """

    def __init__(self) -> None:
        super().__init__()

        self.yt_model = YoutubeModel()
        self.yt_controller = YoutubeController(self.yt_model)

    def compose(self) -> ComposeResult:
        yield Input(select_on_focus=False)
        yield YoutubeVideosView()

    def on_input_submitted(self, ev: Input.Submitted) -> None:
        self.search(ev.value)

    def action_focus_input(self) -> None:
        self.query_one(Input).focus()

    @work(exclusive=True)
    async def search(self, query: str) -> None:
        video_list = self.query_one(YoutubeVideosView)
        input = self.query_one(Input)
        try:
            video_list.loading = True
            input.disabled = True
            if DEBUG_DATA:
                with shelve.open("dummy_data.db", "r") as f:
                    self.yt_model.search_results = f["videos"]
            else:
                await self.yt_controller.search_async(query)
        finally:
            video_list.loading = False
            input.disabled = False

        video_list.focus()
        video_list.update_videos(self.yt_model.search_results)


if __name__ == "__main__":
    Youtube().run()
