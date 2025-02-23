# pyright: reportUnknownMemberType=false, reportUnknownLambdaType=false, reportUnknownArgumentType=false
# mypy: ignore-errors

from typing import final, override
from rich.markup import escape
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
from textual_image.widget import Image as TexImage
from PIL import Image as PILImage

try:
    from pykakasi import kakasi

    kks = kakasi()

    kks.setMode("J", "aF")
    kks.setMode("H", "aF")
    kks.setMode("K", "aF")
    conv = kks.getConverter()
except ModuleNotFoundError:
    kks = None


def jp_romanize(text: str) -> str | None:
    if not kks:
        return None

    final: list[str] = []
    parts = kks.convert(text)
    for part in parts:
        final.append(f"{part["hepburn"]}")

    return "".join(final)


def to_furigana(text: str) -> str | None:
    if not kks:
        return

    return conv.do(text)


from api import YoutubeAPI
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
        Binding("d", "download", "Download selected video"),
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

    def action_download(self) -> None:
        selected = expect(self.highlighted_child, YoutubeVideoView)
        if not selected:
            self.notify("Nothing is selected", severity="warning")
            return

        _ = selected.action_download()

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
    def __init__(
        self,
        height: int = 10,
    ) -> None:
        super().__init__()

        self.img_height = height

    @work
    async def update_image(self, image: PILImage.Image | NetworkImage) -> None:
        i = image if isinstance(image, PILImage.Image) else await image.fetch_async()
        self.image = i

        self.styles.width = Scalar.parse("auto")
        self.styles.height = self.img_height

        _ = self.refresh(recompose=True)

    @override
    def compose(self) -> ComposeResult:
        yield TexImage(self.image)


@final
class YoutubeVideoView(ListItem):
    item_size = 6

    DOWNLOAD_IDLE = 0
    DOWNLOAD_PROCESS = 1
    DOWNLOAD_COMPLETED = 2

    download_status = Reactive(DOWNLOAD_IDLE)

    def __init__(self, video: YoutubeVideo) -> None:
        super().__init__()

        self.video = video

    async def on_mount(self) -> None:
        _ = self.query_one(ImageView).update_image(self.video.thumbnails[0])

    @work
    async def action_download(self) -> None:
        if self.download_status == self.DOWNLOAD_PROCESS:
            self.notify(
                f"Video {self.video.title!r} is still downloading", severity="warning"
            )
            return

        # TODO: create a download queue, with the ui
        # TODO: allow to download multiple time, if the output path changed, or the target file doesnt exists
        if self.download_status == self.DOWNLOAD_COMPLETED:
            self.notify(
                f"Video {self.video.title!r} is already downloaded", severity="warning"
            )
            return

        self.download_status = self.DOWNLOAD_PROCESS

        await YoutubeAPI.download_async(
            self.video.id,
            shared_db.get("format", "bestaudio[ext=m4a]"),
            shared_db.get("outdir", "."),
        )

        self.download_status = self.DOWNLOAD_COMPLETED

    def watch_download_status(self, status: int) -> None:
        indicator = self.query_one(".download-status", Label)
        if status == self.DOWNLOAD_IDLE:
            indicator.styles.background = "#AAAAAA"
        elif status == self.DOWNLOAD_PROCESS:
            indicator.styles.background = "#FFFF00"
        elif status == self.DOWNLOAD_COMPLETED:
            indicator.styles.background = "#00AA00"

    @override
    def compose(self) -> ComposeResult:
        with HorizontalGroup():
            yield ImageView(self.item_size)
            yield Label(classes="gap")
            with VerticalGroup():
                furigana_txt = to_furigana(self.video.title)
                if furigana_txt:
                    yield Label(f"{escape(furigana_txt)}", classes="yt-subtext")
                yield Label(f"{escape(self.video.title)}", classes="yt-maintext")
                with HorizontalGroup():
                    yield Link(
                        escape(self.video.channel),
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
            yield Label(classes="download-status")


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
            if not cache:
                return

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
