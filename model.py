from dataclasses import dataclass
from enum import Enum, auto

from image import NetworkImage


@dataclass
class YoutubeVideo:
    class Status(Enum):
        NOT_LIVE = auto()
        IS_LIVE = auto()
        WAS_LIVE = auto()

    title: str
    id: str
    channel: str
    channel_id: str
    uploader_id: str
    channel_is_verified: bool
    view_count: int
    live: Status
    duration: int
    thumbnails: list[NetworkImage]
