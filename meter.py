from textual.reactive import Reactive
from textual.widget import Widget
from typing import Literal, final
from rich.segment import Segment, Segments
from rich.console import RenderResult, RenderableType, Console, ConsoleOptions
from rich.style import Style
from rich.color import Color

@final
class MeterRenderable:
    HBLOCKS = "█▉▊▋▌▍▎ "
    BLOCK_RESOLUTION = 8

    def __init__(
        self,
        value: float = 0.0,
        max: float = 100.0,
        barcolor: Color | None = None,
        bgcolor: Color | None = None,
    ) -> None:
        self.value = value
        self.max = max
        self.barcolor = barcolor
        self.bgcolor = bgcolor

        self._prev_fill = 0.0
        self.segments: list[Segment] = []

    def __rich_console__(
        self,
        console: Console,
        options: ConsoleOptions,
    ) -> RenderResult:
        width = options.max_width or console.width

        if self.max == float("inf"):
            yield Segment(" " * width, style=Style(color=self.barcolor, reverse=True))

        fill = 0 if self.max == 0 else (self.value / self.max) * width
        fraction = fill - int(fill)

        diff = fill - self._prev_fill
        if diff <= 1 / self.BLOCK_RESOLUTION:
            yield Segments(self.segments)

        self._prev_fill = fill

        self.segments = []
        self.segments.append(
            Segment(
                " " * int(fill),
                style=Style(color=self.barcolor, reverse=True),
            )
        )
        self.segments.append(
            Segment(
                self.block_from_value(fraction, "h"),
                style=Style(color=self.barcolor, bgcolor=self.bgcolor),
            )
        )
        self.segments.append(
            Segment(
                " " * (width - int(fill)),
                style=Style(color=self.bgcolor, reverse=True),
            )
        )

        yield Segments(self.segments)

    def block_from_value(self, v: float, type: Literal["h"]) -> str:
        v = min(max(v, 0), 1)
        if type == "h":
            return self.HBLOCKS[
                (self.BLOCK_RESOLUTION - int(v * self.BLOCK_RESOLUTION)) - 1
            ]
        else:
            return ""

    def update_value(
        self,
        value: float | None = None,
        max: float | None = None,
    ) -> None:
        self.value = value or self.value
        self.max = max or self.max


class Meter(Widget):
    DEFAULT_CSS = """
    Meter {
        height: 1;
    }
    """

    value = Reactive(0.0)
    max = Reactive(0.0)

    def __init__(self, value: float = 0.0, max: float = 100.0) -> None:
        super().__init__()

        self.renderable = MeterRenderable()
        self.value = value
        self.max = max

    def watch_value(self, value: float) -> None:
        self.renderable.update_value(value=value)

    def watch_max(self, max: float) -> None:
        self.renderable.update_value(max=max)

    def render(self) -> RenderableType:
        self.renderable.barcolor = Color.from_rgb(*self.styles.color.rgb)
        self.renderable.bgcolor = Color.from_rgb(*self.styles.background.rgb)
        return self.renderable
