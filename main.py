from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Input
from textual.validation import Length

import shelve

from view import YoutubeVideosView, YoutubePlayer
from api import YoutubeAPI


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

    YoutubePlayer {
        dock: bottom;
        height: 3;
    }

    .center {
        align: center middle;
    }

    YoutubePlayer Button {
        height: 1;
        max-width: 6;
        margin-left: 1;
        margin-right: 1;
        border-top: none;
        border-bottom: none;
    }

    YoutubePlayer Button#playback {
        max-width: 5;
    }

    YoutubeProgress Meter {
        color: red;
        background: $foreground;
    }
    """

    def __init__(self) -> None:
        super().__init__()

    def compose(self) -> ComposeResult:
        yield Input(
            select_on_focus=False,
            validate_on=["submitted"],
            validators=[Length(minimum=1)],
        )
        yield YoutubeVideosView()
        yield YoutubePlayer()

    def action_focus_input(self) -> None:
        self.query_one(Input).focus()

    @on(Input.Submitted)
    @work
    async def search(self, ev: Input.Submitted) -> None:
        if (
            ev.validation_result and not ev.validation_result.is_valid
        ) and not DEBUG_DATA:
            self.notify("Search cannot be empty", severity="warning")
            return

        video_list = self.query_one(YoutubeVideosView)
        input = self.query_one(Input)

        try:
            video_list.loading = True
            input.disabled = True
            if DEBUG_DATA:
                with shelve.open("dummy_data.db", "r") as f:
                    video_list.videos = f["videos"]
            else:
                video_list.videos = await YoutubeAPI.search_async(ev.value)
        finally:
            video_list.loading = False
            input.disabled = False

        video_list.focus()

    @on(YoutubeVideosView.RequestPlay)
    async def play(self, ev: YoutubeVideosView.RequestPlay) -> None:
        self.query_one(YoutubePlayer).video = ev.video


if __name__ == "__main__":
    Youtube().run()
