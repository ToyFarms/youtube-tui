import asyncio
from concurrent.futures import ThreadPoolExecutor

from model import YoutubeModel
from api import YoutubeAPI


class YoutubeController:
    def __init__(self, model: YoutubeModel) -> None:
        self.model = model

    def search(self, query: str, max_results: int = 5) -> None:
        self.model.search_results = YoutubeAPI.search(query, max_results)

    async def search_async(self, query: str, max_results: int = 5) -> None:
        loop = asyncio.get_running_loop()

        with ThreadPoolExecutor() as pool:
            await loop.run_in_executor(pool, self.search, query, max_results)
