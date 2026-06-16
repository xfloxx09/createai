from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class ScrapedVideoData:
    platform: str
    video_url: str
    download_url: Optional[str] = None
    likes: int = 0
    comments: int = 0
    shares: int = 0
    views: int = 0
    saves: int = 0
    caption: Optional[str] = None
    hashtags: list = field(default_factory=list)
    music: Optional[str] = None
    duration: float = 0.0
    author_follower_count: int = 0
    upload_timestamp: Optional[datetime] = None
    thumbnail_url: Optional[str] = None
    resolution_height: Optional[int] = None
    raw_data: Optional[dict] = None


class BaseScraper(ABC):
    platform: str = ""

    @abstractmethod
    async def scrape(self, max_results: int = 50) -> list[ScrapedVideoData]:
        ...
