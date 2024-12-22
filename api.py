from yt_dlp import YoutubeDL

from model import YoutubeVideo
from image import NetworkImage


class YoutubeAPI:
    @staticmethod
    def search(query: str, max_results: int = 5) -> list[YoutubeVideo]:
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
            for entry in entries:
                status = {
                    "is_live": YoutubeVideo.Status.IS_LIVE,
                    "was_live": YoutubeVideo.Status.WAS_LIVE,
                }.get(entry.get("live"), YoutubeVideo.Status.NOT_LIVE)

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
