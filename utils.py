# pyright: reportExplicitAny=false, reportAny=false

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any
from PIL import Image

import os
import sys


def format_time(seconds: float) -> str:
    """
    Format seconds into DD:HH:MM:SS, HH:MM:SS, MM:SS, or M:SS depending on the duration.

    Args:
        seconds (int): Number of seconds to format

    Returns:
        str: Formatted time string

    Examples:
        >>> format_time(30)        # '0:30'
        >>> format_time(65)        # '1:05'
        >>> format_time(3665)      # '1:01:05'
        >>> format_time(90061)     # '1:01:01:01'
    """
    seconds = int(seconds)

    if seconds < 0:
        return "0:00"

    minutes, secs = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)

    parts: list[str] = []

    if days > 0:
        parts.extend([str(days), f"{hours:02d}", f"{minutes:02d}", f"{secs:02d}"])
    elif hours > 0:
        parts.extend([str(hours), f"{minutes:02d}", f"{secs:02d}"])
    elif minutes > 0:
        if minutes < 10:
            parts.extend([str(minutes), f"{secs:02d}"])
        else:
            parts.extend([f"{minutes:02d}", f"{secs:02d}"])
    else:
        parts.extend(["0", f"{secs:02d}"])

    return ":".join(parts)


def format_number(number: float) -> str:
    """
    Format number with K/M/B suffixes and appropriate decimal places.

    Args:
        number (int/float): Number to format

    Returns:
        str: Formatted number string with suffix

    Examples:
        >>> format_number(999)      # '999'
        >>> format_number(1000)     # '1K'
        >>> format_number(1500)     # '1.5K'
        >>> format_number(1100000)  # '1.1M'
    """
    if number < 1000:
        return str(number)

    if number < 1000000:  # Less than 1M
        formatted = number / 1000
        if formatted >= 100:  # No decimals for 100K+
            return f"{int(formatted)}K"
        elif formatted.is_integer():
            return f"{int(formatted)}K"
        else:
            return f"{formatted:.1f}K"

    if number < 1000000000:  # Less than 1B
        formatted = number / 1000000
        return f"{formatted:.1f}M"

    # Billion+
    formatted = number / 1000000000
    return f"{formatted:.1f}B"


# https://github.com/spatialaudio/python-sounddevice/issues/11
@contextmanager
def suppress_portaudio_error() -> Generator[None, None, None]:
    devnull = os.open(os.devnull, os.O_WRONLY)
    old_stderr = os.dup(2)
    _ = sys.stderr.flush()
    _ = os.dup2(devnull, 2)
    os.close(devnull)

    try:
        yield
    finally:
        _ = os.dup2(old_stderr, 2)
        os.close(old_stderr)


# shuts pyright
def expect[T](value: Any, _: type[T]) -> T:
    return value


# pyright: reportUnknownMemberType=false
def resize_image(
    image: Image.Image,
    target_width: int | None = None,
    target_height: int | None = None,
) -> Image.Image:
    if target_width is None and target_height is None:
        raise ValueError(
            "At least one of target_width or target_height must be specified"
        )

    orig_width, orig_height = image.size
    aspect_ratio = orig_width / orig_height

    if target_width and target_height:
        new_size = (target_width, target_height)
        resized = image.resize(new_size, Image.Resampling.LANCZOS)
        return resized

    elif target_width:
        new_width = target_width
        new_height = int(new_width / aspect_ratio)
        resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        if new_height < target_width:
            padded = Image.new("RGB", (new_width, target_width), (0, 0, 0))
            y_offset = (target_width - new_height) // 2
            padded.paste(resized, (0, y_offset))
            return padded
        return resized

    elif target_height:
        new_height = target_height
        new_width = int(new_height * aspect_ratio)
        resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        if new_width < target_height:
            padded = Image.new("RGB", (target_height, new_height), (0, 0, 0))
            x_offset = (target_height - new_width) // 2
            padded.paste(resized, (x_offset, 0))
            return padded
        return resized

    return image
