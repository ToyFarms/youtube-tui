import math

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import HorizontalGroup, VerticalGroup
from textual.css.scalar import Scalar
from textual.reactive import Reactive
from textual.widget import Widget
from textual.widgets import Link, ListView, ListItem, Label
from textual_image.widget import AutoImage
from textual_image.renderable import Image as AutoRenderable
from textual_image.widget._base import Image
from PIL import Image as PILImage

from image import NetworkImage
from model import YoutubeVideo
import utils


class YoutubeVideosView(ListView):
    BINDINGS = [
        Binding("enter", "select_cursor", "Select"),
        Binding("k", "cursor_up", "Cursor up"),
        Binding("j", "cursor_down", "Cursor down"),
    ]

    async def update_videos(self, videos: list[YoutubeVideo]) -> None:
        await self.clear()

        for video in videos:
            self.append(YoutubeVideoView(video))


type SupportedImage = PILImage.Image | NetworkImage


class ImageView(Image, Renderable=AutoRenderable):
    def __init__(self, height: int) -> None:
        super().__init__()

        self.img_height = height
        self.styles.height = height

    @work
    async def update_image(self, image: PILImage.Image | NetworkImage) -> None:
        self.loading = True

        im = PILImage.Image()
        if isinstance(image, PILImage.Image):
            im = image
        elif isinstance(image, NetworkImage):
            im = await image.fetch_async()
        self.image = im

        self.styles.width = Scalar.parse("auto")
        self.styles.height = self.img_height

        self.loading = False


class YoutubeVideoView(ListItem):
    item_size = 6

    def __init__(self, video: YoutubeVideo) -> None:
        super().__init__()

        self.video = video
        self.img = ImageView(self.item_size)
        self.img.update_image(self.video.thumbnails[0])

    def compose(self) -> ComposeResult:
        with HorizontalGroup():
            yield self.img
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
                yield Label(
                    f"{utils.format_number(self.video.view_count)} views @ {utils.format_time(self.video.duration)}",
                    classes="yt-subtext",
                )
