# mypy: disable-error-code="import-untyped"
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false

from yt_dlp import YoutubeDL

import asyncio

from model import YoutubeVideo
from image import NetworkImage
import utils


class YoutubeAPI:
    @staticmethod
    def get_media_url(url_or_id: str) -> str:
        ydl_opts = {
            "format": "bestaudio",
            "quiet": True,
            "noplaylist": True,
        }

        with YoutubeDL(ydl_opts) as ydl:
            info_dict = utils.expect(
                ydl.extract_info(url_or_id, download=False), dict[str, object]
            )
            return utils.expect(info_dict.get("url", ""), str)

    @staticmethod
    async def search_async(query: str, max_results: int = 5) -> list[YoutubeVideo]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, YoutubeAPI.search, query, max_results)

    @staticmethod
    def search(query: str, max_results: int = 5) -> list[YoutubeVideo]:
        x = utils.expect
        if not query:
            return []

        search_query = f"ytsearch{max_results}:{query}"
        options = {
            "quiet": True,
            "extract_flat": True,
        }

        with YoutubeDL(options) as ydl:
            info = x(ydl.extract_info(search_query, download=False), dict[str, object])

        videos: list[YoutubeVideo] = []

        entries = x(info.get("entries", []), list[dict[str, object]])
        for entry in entries:
            status = YoutubeVideo.Status.NOT_LIVE
            status_str = entry.get("live_status")

            if status_str == "is_live":
                status = YoutubeVideo.Status.IS_LIVE
            elif status_str == "was_live":
                status = YoutubeVideo.Status.WAS_LIVE

            nb_views = 0
            if status == YoutubeVideo.Status.IS_LIVE:
                nb_views = x(entry.get("concurrent_view_count", 0), int)
            else:
                nb_views = x(entry.get("view_count", 0), int)

            thumbnails: list[NetworkImage] = []
            for thumbnail in x(entry.get("thumbnails", []), list[dict[str, int | str]]):
                if not (url := x(thumbnail.get("url"), str)):
                    continue

                thumbnails.append(
                    NetworkImage(
                        url=url,
                        width=x(thumbnail.get("width", 0), int),
                        height=x(thumbnail.get("height", 0), int),
                    )
                )

            videos.append(
                YoutubeVideo(
                    title=x(entry.get("title", ""), str),
                    id=x(entry.get("id", ""), str),
                    channel=x(entry.get("channel", ""), str),
                    channel_id=x(entry.get("channel_id", ""), str),
                    uploader_id=x(entry.get("uploader_id", ""), str),
                    channel_is_verified=x(
                        entry.get("channel_is_verified", False), bool
                    ),
                    view_count=x(nb_views, int),
                    live=status,
                    duration=x(entry.get("duration") or 0, int),
                    thumbnails=thumbnails,
                )
            )

        return videos
