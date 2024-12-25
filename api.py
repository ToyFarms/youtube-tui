from yt_dlp import YoutubeDL

import asyncio

from model import YoutubeVideo
from image import NetworkImage


class YoutubeAPI:
    @staticmethod
    def get_media_url(url_or_id: str) -> None:
        ydl_opts = {
            "format": "bestaudio",
            "quiet": True,
            "noplaylist": True,
        }

        with YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url_or_id, download=False)
            return info_dict["url"]

    @staticmethod
    async def search_async(query: str, max_results: int = 5) -> list[YoutubeVideo]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, YoutubeAPI.search, query, max_results)

    @staticmethod
    def search(query: str, max_results: int = 5) -> list[YoutubeVideo]:
        if not query:
            return []

        search_query = f"ytsearch{max_results}:{query}"
        options = {
            "quiet": True,
            "extract_flat": True,
        }

        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(search_query, download=False)

        videos: list[YoutubeVideo] = []

        if isinstance(info, dict):
            entries = info.get("entries", [])
            print(entries)
            for entry in entries:
                status = {
                    "is_live": YoutubeVideo.Status.IS_LIVE,
                    "was_live": YoutubeVideo.Status.WAS_LIVE,
                }.get(entry.get("live_status"), YoutubeVideo.Status.NOT_LIVE)

                nb_views = 0
                if status == YoutubeVideo.Status.IS_LIVE:
                    nb_views = entry.get("concurrent_view_count", 0)
                else:
                    nb_views = entry.get("view_count", 0)

                thumbnails: list[NetworkImage] = []
                for thumbnail in entry.get("thumbnails", []):
                    if not (url := thumbnail.get("url")):
                        continue

                    thumbnails.append(
                        NetworkImage(
                            url=url,
                            width=thumbnail.get("width", 0),
                            height=thumbnail.get("height", 0),
                        )
                    )

                videos.append(
                    YoutubeVideo(
                        title=entry.get("title", ""),
                        id=entry.get("id", ""),
                        channel=entry.get("channel", ""),
                        channel_id=entry.get("channel_id", ""),
                        uploader_id=entry.get("uploader_id", ""),
                        channel_is_verified=entry.get("channel_is_verified", False),
                        view_count=nb_views,
                        live=status,
                        duration=entry.get("duration") or 0,
                        thumbnails=thumbnails,
                    )
                )

        return videos
