from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Input
from textual.validation import Length

import shelve

from model import YoutubeModel
from view import YoutubeVideosView
from controller import YoutubeController


DEBUG_DATA = False


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

    .yt-maintext {
        text-style: bold;
    }

    .yt-subtext {
        color: #aaaaaa;
    }

    .gap {
        width: 2;
    }

    ImageView {
        width: auto;
    }
    """

    def __init__(self) -> None:
        super().__init__()

        self.yt_model = YoutubeModel()
        self.yt_controller = YoutubeController(self.yt_model)

    def compose(self) -> ComposeResult:
        yield Input(
            select_on_focus=False,
            validate_on=["submitted"],
            validators=[Length(minimum=1)],
        )
        yield YoutubeVideosView()

    def action_focus_input(self) -> None:
        self.query_one(Input).focus()

    @on(Input.Submitted)
    @work
    async def search(self, ev: Input.Submitted) -> None:
        if ev.validation_result and not ev.validation_result.is_valid:
            self.notify("Search cannot be empty", severity="warning")
            return

        video_list = self.query_one(YoutubeVideosView)
        input = self.query_one(Input)
        try:
            video_list.loading = True
            input.disabled = True
            if DEBUG_DATA:
                with shelve.open("dummy_data.db", "r") as f:
                    self.yt_model.search_results = f["videos"]
            else:
                await self.yt_controller.search_async(ev.value)
        finally:
            video_list.loading = False
            input.disabled = False

        video_list.focus()
        await video_list.update_videos(self.yt_model.search_results)


if __name__ == "__main__":
    Youtube().run()
