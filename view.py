from textual import work, on
from textual.message import Message
from textual.reactive import Reactive
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import HorizontalGroup, VerticalGroup
from textual.css.scalar import Scalar
from textual.widget import Widget
from textual.widgets import Link, ListView, ListItem, Label, ProgressBar, Button
from textual_image.renderable import Image as AutoRenderable
from textual_image.widget._base import Image
from PIL import Image as PILImage

import numpy as np

from image import NetworkImage
from model import YoutubeVideo
from audio import AudioPlayer
from meter import Meter
from api import YoutubeAPI

import utils


class YoutubeVideosView(ListView):
    BINDINGS = [
        Binding("enter", "select_cursor", "Select"),
        Binding("k", "cursor_up", "Cursor up"),
        Binding("j", "cursor_down", "Cursor down"),
        Binding("g", "cursor_top", "Cursor to top"),
        Binding("G", "cursor_bot", "Cursor to bottom"),
    ]
    videos: Reactive[list[YoutubeVideo]] = Reactive([])

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
            self.append(YoutubeVideoView(video))

    @on(ListView.Selected)
    def handle_play(self, ev: ListView.Selected) -> None:
        item = ev.item
        if isinstance(item, YoutubeVideoView):
            self.post_message(YoutubeVideosView.RequestPlay(item.video))


type SupportedImage = PILImage.Image | NetworkImage


class ImageView(Image, Renderable=AutoRenderable):
    def __init__(self, height: int) -> None:
        super().__init__()

        self.img_height = height
        self.styles.height = height

    @work
    async def update_image(self, image: SupportedImage) -> None:
        self.loading = True

        if isinstance(image, PILImage.Image):
            self.image = image
        elif isinstance(image, NetworkImage):
            self.image = await image.fetch_async()

        self.styles.width = Scalar.parse("auto")
        self.styles.height = self.img_height

        self.loading = False


class YoutubeVideoView(ListItem):
    item_size = 6

    def __init__(self, video: YoutubeVideo) -> None:
        super().__init__()

        self.video = video

    async def on_mount(self) -> None:
        self.query_one(ImageView).update_image(self.video.thumbnails[0])

    def compose(self) -> ComposeResult:
        with HorizontalGroup():
            yield ImageView(self.item_size)
            yield Label(classes="gap")
            with VerticalGroup():
                yield Label()
                yield Label(f"[bold]{self.video.title}[/]", classes="yt-maintext")
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
                        f"{utils.format_number(self.video.view_count)} views @ 🔴 LIVE",
                        classes="yt-subtext",
                    )
                elif self.video.live == YoutubeVideo.Status.WAS_LIVE:
                    yield Label(
                        f"{utils.format_number(self.video.view_count)} views @ {utils.format_time(self.video.duration)} ⬤  WAS LIVE",
                        classes="yt-subtext",
                    )
                else:
                    yield Label(
                        f"{utils.format_number(self.video.view_count)} views @ {utils.format_time(self.video.duration)}",
                        classes="yt-subtext",
                    )


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

    def compose(self) -> ComposeResult:
        with HorizontalGroup(classes="center"):
            yield Label(classes="meter-val")
            yield self.meter
            yield Label(classes="meter-max")

    def watch_value(self, value: float) -> None:
        self.meter.value = value
        self.query_one(".meter-val").update(utils.format_time(value))

    def watch_max(self, max: float) -> None:
        self.meter.max = max
        indicator = self.query_one(".meter-max")
        if self.max != float("inf"):
            indicator.update(utils.format_time(max))
        else:
            indicator.update("--:--")


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

    def compose(self) -> ComposeResult:
        with HorizontalGroup():
            yield Label("", id="title")
            yield Label("", id="buffered")
        yield YoutubeProgress()
        with HorizontalGroup(classes="center"):
            yield Button("⏮", id="prev")
            yield Button("+5", id="left")
            yield Button("⏸", id="playback")
            yield Button("-5", id="right")
            yield Button("⏭", id="next")

    @on(Button.Pressed)
    def handle_press(self, ev: Button.Pressed) -> None:
        if ev.button.id == "left":
            self.seek(-5)
        elif ev.button.id == "right":
            self.seek(100)
        elif ev.button.id == "playback":
            self.toggle_playback()

    def seek(self, s: int) -> None:
        self.player.seek(s)

    def toggle_playback(self) -> None:
        paused = self.player.toggle_playback()
        if paused:
            self.query_one("#playback").label = "⏸"
        else:
            self.query_one("#playback").label = "⏵"

    @work(thread=True, exclusive=True)
    def watch_video(self, video: YoutubeVideo | None) -> None:
        if video is None:
            return

        self.player.pause()
        self.query_one("#title").update(f"[#aaaaaa]Playing:[/] {video.title}")
        self.player.update(YoutubeAPI.get_media_url(video.id))

        progress = self.query_one(YoutubeProgress)
        buffer_indicator = self.query_one("#buffered")

        def update_progress(time: float) -> None:
            if not time:
                return
            progress.value = time

        def update_duration(duration: float) -> None:

            progress.max = duration or float("inf")

        def update_cache(cache: float) -> None:
            buffer_indicator.update(
                f"{cache['fw-bytes']:,} bytes buffered ({cache['cache-duration']:.2f}s)"
            )

        self.player.register_callback(
            "time-pos", fn=lambda name, value: update_progress(value)
        )
        self.player.register_callback(
            "duration", fn=lambda name, value: update_duration(value)
        )
        self.player.register_callback(
            "demuxer-cache-state", fn=lambda name, value: update_cache(value)
        )

        self.player.play()
