import sqlite3
import requests
import io
import hashlib

from PIL import Image
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class NetworkImage:
    url: str
    width: int
    height: int

    def fetch(self, ignore_cache: bool = False) -> Image.Image:
        cache_manager = ImageCache()

        if not ignore_cache:
            cached_data = cache_manager.get_cached_image(self.url)
            if cached_data:
                image_data, etag, last_modified = cached_data

                headers = {}
                if etag:
                    headers["If-None-Match"] = etag
                if last_modified:
                    headers["If-Modified-Since"] = last_modified

                try:
                    head_response = requests.head(self.url, headers=headers)
                    head_response.raise_for_status()

                    if head_response.status_code == 304:
                        return Image.open(io.BytesIO(image_data))
                except requests.RequestException:
                    return Image.open(io.BytesIO(image_data))

        response = requests.get(self.url)
        response.raise_for_status()
        image_data = response.content

        img = Image.open(io.BytesIO(image_data))
        if img.size != (self.width, self.height):
            raise ValueError(
                f"Image dimensions mismatch. Expected {self.width}x{self.height}, "
                f"got {img.size[0]}x{img.size[1]}"
            )

        cache_manager.update_cache(
            self,
            image_data,
            response.headers.get("ETag"),
            response.headers.get("Last-Modified"),
        )

        return img


class ImageCache:
    def __init__(self, db_path: str = "image_cache.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS images (
                    url TEXT PRIMARY KEY,
                    etag TEXT,
                    last_modified TEXT,
                    width INTEGER,
                    height INTEGER,
                    image_data BLOB,
                    downloaded_at TIMESTAMP,
                    hash TEXT
                )
            """
            )
            conn.commit()

    def get_cached_image(self, url: str) -> Optional[Tuple[bytes, str, str]]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT image_data, etag, last_modified FROM images WHERE url = ?",
                (url,),
            )
            result = cursor.fetchone()
            if result:
                return result[0], result[1], result[2]
        return None

    def update_cache(
        self,
        network_image: NetworkImage,
        image_data: bytes,
        etag: Optional[str],
        last_modified: Optional[str],
    ) -> None:
        image_hash = hashlib.md5(image_data).hexdigest()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO images 
                (url, etag, last_modified, width, height, image_data, downloaded_at, hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    network_image.url,
                    etag,
                    last_modified,
                    network_image.width,
                    network_image.height,
                    image_data,
                    datetime.now().isoformat(),
                    image_hash,
                ),
            )
            conn.commit()

    def clear_cache(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM images")
            conn.commit()

    def get_cache_stats(self) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT 
                    COUNT(*) as total_images,
                    SUM(LENGTH(image_data)) as total_size,
                    MIN(downloaded_at) as oldest_image,
                    MAX(downloaded_at) as newest_image
                FROM images
            """
            )
            stats = cursor.fetchone()
            return {
                "total_images": stats[0],
                "total_size_bytes": stats[1],
                "oldest_image": stats[2],
                "newest_image": stats[3],
            }
