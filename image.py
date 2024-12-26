# pyright: reportUnknownArgumentType=false, reportUnknownMemberType=false

import sqlite3
import requests
import io
import hashlib
import aiohttp

from PIL import Image
from datetime import datetime
from dataclasses import dataclass
from typing import final, TypedDict

from utils import expect


@dataclass
class NetworkImage:
    url: str
    width: int
    height: int

    async def fetch_async(self, ignore_cache: bool = False) -> Image.Image:
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
                    async with aiohttp.ClientSession() as session:
                        async with session.head(
                            self.url, headers=headers
                        ) as head_response:
                            if head_response.status == 304:
                                return Image.open(io.BytesIO(image_data))
                except aiohttp.ClientError:
                    return Image.open(io.BytesIO(image_data))

        async with aiohttp.ClientSession() as session:
            async with session.get(self.url) as response:
                response.raise_for_status()
                image_data = await response.read()

        img = Image.open(io.BytesIO(image_data))
        if img.size != (self.width, self.height):
            raise ValueError(
                (
                    f"Image dimensions mismatch. Expected {self.width}x{self.height}, "
                    f"got {img.size[0]}x{img.size[1]}"
                )
            )

        cache_manager.update_cache(
            self,
            image_data,
            response.headers.get("ETag"),
            response.headers.get("Last-Modified"),
        )

        return img

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
                (
                    f"Image dimensions mismatch. Expected {self.width}x{self.height}, "
                    f"got {img.size[0]}x{img.size[1]}"
                )
            )

        cache_manager.update_cache(
            self,
            image_data,
            response.headers.get("ETag"),
            response.headers.get("Last-Modified"),
        )

        return img


@final
class ImageCache:
    def __init__(self, db_path: str = "image_cache.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            _ = conn.execute(
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

    def get_cached_image(self, url: str) -> tuple[bytes, str, str] | None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT image_data, etag, last_modified FROM images WHERE url = ?",
                (url,),
            )
            result = expect(cursor.fetchone(), list[object])
            if result:
                return (
                    expect(result[0], bytes),
                    expect(result[1], str),
                    expect(result[2], str),
                )
        return None

    def update_cache(
        self,
        network_image: NetworkImage,
        image_data: bytes,
        etag: str | None,
        last_modified: str | None,
    ) -> None:
        image_hash = hashlib.md5(image_data).hexdigest()

        with sqlite3.connect(self.db_path) as conn:
            _ = conn.execute(
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
            _ = conn.execute("DELETE FROM images")
            conn.commit()

    class CacheStats(TypedDict):
        total_images: int
        total_size_bytes: int
        oldest_image: str
        newest_image: str

    def get_cache_stats(self) -> CacheStats:
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
            stats = expect(cursor.fetchone(), list[object])
            return {
                "total_images": expect(stats[0], int),
                "total_size_bytes": expect(stats[1], int),
                "oldest_image": expect(stats[2], str),
                "newest_image": expect(stats[3], str),
            }
