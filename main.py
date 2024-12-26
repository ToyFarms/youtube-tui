from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import HorizontalScroll, VerticalGroup
from textual.widgets import Input, Label
from textual.validation import Length
from typing import final, override
from rich.markup import escape

import shelve

from view import YoutubeVideosView, YoutubePlayer, SettingPopup
from api import YoutubeAPI
from persistent import shared_db


DEBUG_DATA = False


@final
class Youtube(App[None]):
    BINDINGS = [
        Binding("/", "focus_input", "Focus input"),
        Binding("right", "seek(5)", "Seek +5 seconds"),
        Binding("left", "seek(-5)", "Seek -5 seconds"),
        Binding("space", "toggle_playback", "Toggle play/pause"),
        Binding(":", "open_setting", "Open setting"),
    ]

    CSS = """
    #yt-searchbar {
        height: 1;
        border-top: none;
        border-bottom: none;
    }

    .yt-setting-container {
        width: 30%;
        align: center middle;
        height: auto;
        padding: 1;
    }

    .yt-setting-container Label {
        width: 100%;
        text-align: center;
        background: $panel;
        margin-left: 1;
        margin-right: 1;
    }

    .setting-title {
        background: $background !important;
        text-align: center;
        text-style: bold;
        padding-bottom: 1;
    }

    .yt-maintext {
        text-style: bold;
    }

    .yt-subtext {
        color: #AAAAAA;
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

    .header {
        dock: top;
    }

    .header-info {
        height: 2;
    }

    .info-card {
        margin-left: 1;
        padding-left: 1;
        padding-right: 1;
    }

    .download-status {
        width: 2;
        height: 100%;
        background: #aaaaaa;
    }
    """

    def __init__(self) -> None:
        super().__init__()

    @override
    def compose(self) -> ComposeResult:
        with VerticalGroup(classes="header"):
            with HorizontalScroll(classes="header-info"):
                for k, v in shared_db.items():
                    yield Label(f"{escape(k)}: {escape(str(v))}", classes="info-card")
            yield Input(
                select_on_focus=False,
                validate_on=["submitted"],
                validators=[Length(minimum=1)],
                classes="yt-searchbar",
            )
        yield YoutubeVideosView()
        yield YoutubePlayer()

    @work
    async def action_open_setting(self) -> None:
        await self.push_screen_wait(SettingPopup())

    def action_focus_input(self) -> None:
        _ = self.query_one(Input).focus()

    @on(Input.Submitted, ".yt-searchbar")
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
                video_list.videos = await YoutubeAPI.search_async(
                    ev.value,
                    max_results=shared_db.get("max_search", 5),
                )
        finally:
            video_list.loading = False
            input.disabled = False
            _ = input.focus()

    @on(YoutubeVideosView.RequestPlay)
    def play(self, ev: YoutubeVideosView.RequestPlay) -> None:
        self.query_one(YoutubePlayer).video = ev.video

    def action_seek(self, s: int) -> None:
        self.query_one(YoutubePlayer).seek(s)

    def action_toggle_playback(self) -> None:
        self.query_one(YoutubePlayer).toggle_playback()


def default_db() -> None:
    def set(k: str, v: object) -> None:
        if k not in shared_db:
            shared_db.set(k, v)

    set("outdir", "~")
    set("max_search", 5)
    set("format", "bestaudio[ext=m4a]")


if __name__ == "__main__":
    default_db()
    Youtube().run()
