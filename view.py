# pyright: reportUnknownMemberType=false, reportUnknownLambdaType=false, reportUnknownArgumentType=false
# mypy: ignore-errors

from typing import final, override
from textual import work, on
from textual.await_complete import AwaitComplete
from textual.message import Message
from textual.css.query import NoMatches
from textual.reactive import Reactive
from textual.validation import Number
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import HorizontalGroup, VerticalGroup, VerticalScroll
from textual.css.scalar import Scalar
from textual.widget import Widget
from textual.widgets import (
    Link,
    ListView,
    ListItem,
    Label,
    Button,
    Input,
)
from textual.screen import ModalScreen
from textual_image.renderable import Image as AutoRenderable
from textual_image.widget._base import Image
from PIL import Image as PILImage

from image import NetworkImage
from model import YoutubeVideo
from audio import AudioPlayer
from meter import Meter
from path_input import PathInput
from persistent import shared_db
from utils import expect, format_number, format_time


@final
class YoutubeVideosView(ListView):
    BINDINGS = [
        Binding("enter", "select_cursor", "Select"),
        Binding("k", "cursor_up", "Cursor up"),
        Binding("j", "cursor_down", "Cursor down"),
        Binding("g", "cursor_top", "Cursor to top"),
        Binding("G", "cursor_bot", "Cursor to bottom"),
    ]
    videos: Reactive[list[YoutubeVideo]] = Reactive([])

    @final
    class RequestPlay(Message):
        def __init__(self, video: YoutubeVideo) -> None:
            super().__init__()

            self.video = video

    def action_cursor_top(self) -> None:
        self.index = 0

    def action_cursor_bot(self) -> None:
        self.index = len(self) - 1

    @work
    async def watch_videos(self, videos: list[YoutubeVideo]) -> None:
        await self.clear()

        for video in videos:
            await self.append(YoutubeVideoView(video))

    @on(ListView.Selected)
    def handle_play(self, ev: ListView.Selected) -> None:
        item = ev.item
        if isinstance(item, YoutubeVideoView):
            _ = self.post_message(YoutubeVideosView.RequestPlay(item.video))


@final
class ImageView(Image, Renderable=AutoRenderable):
    def __init__(self, height: int) -> None:
        super().__init__()

        self.img_height = height
        self.styles.height = height

    @work
    async def update_image(self, image: PILImage.Image | NetworkImage) -> None:
        self.loading = True

        if isinstance(image, PILImage.Image):
            self.image = image
        else:
            self.image = await image.fetch_async()

        self.styles.width = Scalar.parse("auto")
        self.styles.height = self.img_height

        self.loading = False


@final
class YoutubeVideoView(ListItem):
    item_size = 6

    def __init__(self, video: YoutubeVideo) -> None:
        super().__init__()

        self.video = video

    async def on_mount(self) -> None:
        _ = self.query_one(ImageView).update_image(self.video.thumbnails[0])

    @override
    def compose(self) -> ComposeResult:
        with HorizontalGroup():
            yield ImageView(self.item_size)
            yield Label(classes="gap")
            with VerticalGroup():
                yield Label()
                yield Label(f"{self.video.title}", classes="yt-maintext")
                with HorizontalGroup():
                    yield Link(
                        self.video.channel,
                        url=f"https://youtube.com/{self.video.channel_id}",
                        tooltip=self.video.uploader_id,
                        classes="yt-subtext",
                    )
                    if self.video.channel_is_verified:
                        yield Label(" [green]✓[/]")

                yield Label()
                if self.video.live == YoutubeVideo.Status.IS_LIVE:
                    yield Label(
                        f"{format_number(self.video.view_count)} views @ 🔴 LIVE",
                        classes="yt-subtext",
                    )
                elif self.video.live == YoutubeVideo.Status.WAS_LIVE:
                    yield Label(
                        f"{format_number(self.video.view_count)} views @ {format_time(self.video.duration)} ⬤  WAS LIVE",
                        classes="yt-subtext",
                    )
                else:
                    yield Label(
                        f"{format_number(self.video.view_count)} views @ {format_time(self.video.duration)}",
                        classes="yt-subtext",
                    )


@final
class YoutubeProgress(Widget):
    DEFAULT_CSS = """
    .meter-val {
        margin-right: 1;
    }

    .meter-max {
        margin-left: 1;
    }

    Meter {
        width: 90%;
    }

    YoutubeProgress {
        height: 1;
    }
    """

    value = Reactive(0.0)
    max = Reactive(0.0)

    def __init__(self) -> None:
        super().__init__()
        self.meter = Meter()

    @override
    def compose(self) -> ComposeResult:
        with HorizontalGroup(classes="center"):
            yield Label(classes="meter-val")
            yield self.meter
            yield Label(classes="meter-max")

    def watch_value(self, value: float) -> None:
        self.meter.value = value
        try:
            meter = self.query_one(".meter-val", Label)
        except NoMatches:
            return

        meter.update(format_time(value))

    def watch_max(self, max: float) -> None:
        self.meter.max = max
        indicator = self.query_one(".meter-max", Label)
        if self.max != float("inf"):
            indicator.update(format_time(max))
        else:
            indicator.update("--:--")


@final
class YoutubePlayer(Widget):
    DEFAULT_CSS = """
    #buffered {
        dock: right;
    }
    """

    video: Reactive[YoutubeVideo | None] = Reactive(None)

    def __init__(self) -> None:
        super().__init__()

        self.player = AudioPlayer()

    @override
    def compose(self) -> ComposeResult:
        with HorizontalGroup():
            yield Label("", id="title")
            yield Label("", id="buffered")
        yield YoutubeProgress()
        with HorizontalGroup(classes="center"):
            yield Button("⏮", id="prev")
            yield Button("-5", id="left")
            yield Button("⏸", id="playback")
            yield Button("+5", id="right")
            yield Button("⏭", id="next")

    @on(Button.Pressed)
    def handle_press(self, ev: Button.Pressed) -> None:
        if ev.button.id == "left":
            self.seek(-5)
        elif ev.button.id == "right":
            self.seek(5)
        elif ev.button.id == "playback":
            self.toggle_playback()

    def seek(self, s: int) -> None:
        self.player.seek(s)

    def toggle_playback(self) -> None:
        paused = self.player.toggle_playback()
        if paused:
            self.query_one("#playback", Button).label = "⏸"
        else:
            self.query_one("#playback", Button).label = "⏵"

    @work(thread=True, exclusive=True)
    def watch_video(self, video: YoutubeVideo | None) -> None:
        if video is None:
            return

        self.player.pause()
        self.query_one("#title", Label).update(f"[#aaaaaa]Playing:[/] {video.title}")

        self.player.update(f"https://youtube.com/watch?v={video.id}")

        progress = self.query_one(YoutubeProgress)
        buffer_indicator = self.query_one("#buffered", Label)

        def update_progress(time: float) -> None:
            if not time:
                return
            progress.value = time

        def update_duration(duration: float) -> None:
            progress.max = duration or float("inf")

        def update_cache(cache: dict[str, float]) -> None:
            buffer_indicator.update(
                f"{cache['fw-bytes']:,} bytes buffered ({cache['cache-duration']:.2f}s)"
            )

        self.player.register_callback(
            "time-pos", fn=lambda value: update_progress(expect(value, float))
        )
        self.player.register_callback(
            "duration", fn=lambda value: update_duration(expect(value, float))
        )
        self.player.register_callback(
            "demuxer-cache-state",
            fn=lambda value: update_cache(value),  # pyright: ignore[reportArgumentType]
        )

        self.player.play()


# TODO: factor out label-input setting
@final
class SettingPopup(ModalScreen[None]):
    DEFAULT_CSS = """
    SettingPopup {
        align: center middle;
    }
    """

    BINDINGS = [Binding("escape", "dismiss()"), Binding("q", "dismiss()")]

    @override
    def compose(self) -> ComposeResult:
        with VerticalScroll(classes="yt-setting-container", can_focus=False):
            yield Label("Setting", classes="setting-title")
            yield Label("YouTube max search")
            yield Input(
                id="yt-maxsearch",
                classes="yt-setting",
                validators=[Number(0)],
                restrict=r"\d*",
                placeholder="Youtube max search",
                value=f"{shared_db.get("max_search", 0)}",
                select_on_focus=False,
            )

            yield Label("yt-dlp output dir")
            yield PathInput(
                id="ytdlp-outdir",
                classes="yt-setting",
                file_okay=False,
                value=shared_db.get("outdir", ""),
            )

            yield Label("yt-dlp format")
            yield Input(
                id="ytdlp-format",
                classes="yt-setting",
                value=shared_db.get("format", ""),
                select_on_focus=False,
            )

    def set(self, k: str, v: object) -> None:
        self.notify(f"set {k!r} to {v!r}", title="Setting set")
        shared_db.set(k, v)

    @on(Input.Submitted, "#ytdlp-format")
    def handle_format(self, ev: Input.Submitted) -> None:
        self.set("format", ev.value)

    @on(PathInput.Submitted, "#ytdlp-outdir")
    def handle_outdir(self, ev: Input.Submitted) -> None:
        if ev.validation_result and not ev.validation_result.is_valid:
            desc = ""
            if ev.validation_result.failure_descriptions:
                desc = ev.validation_result.failure_descriptions[0]

            self.notify(
                title=f"Path '{ev.value}' is not valid",
                message=desc,
                severity="warning",
            )
            return

        self.set("outdir", ev.value)

    @on(Input.Submitted, "#yt-maxsearch")
    def handle_search(self, ev: Input.Submitted) -> None:
        self.set("max_search", ev.value)

    @override
    def dismiss(self, result: object | None = None) -> AwaitComplete:
        def _set_if_changed(k: str, query: str) -> None:
            v = self.query_one(query, Input).value
            if k in shared_db and shared_db.get(k, "") == v:
                return

            self.set(k, self.query_one(query, Input).value)

        _set_if_changed("max_search", "#yt-maxsearch")
        _set_if_changed("outdir", "#ytdlp-outdir")
        _set_if_changed("format", "#ytdlp-format")
        return super().dismiss()
