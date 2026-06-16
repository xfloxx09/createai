import asyncio
import json
import subprocess
from datetime import datetime
from typing import Optional

from app.scrapers.base import BaseScraper, ScrapedVideoData


class YouTubeScraper(BaseScraper):
    platform = "youtube"
    _trending_url = "https://www.youtube.com/feed/trending?bp=4gINGgt5dG91dGJlX3Nob3J0cw%3D%3D"

    async def scrape(self, max_results: int = 50) -> list[ScrapedVideoData]:
        try:
            return await asyncio.to_thread(self._scrape_sync, max_results)
        except Exception as e:
            raise RuntimeError(f"YouTube scrape failed: {e}")

    def _scrape_sync(self, max_results: int) -> list[ScrapedVideoData]:
        cmd = [
            "yt-dlp",
            "--dump-json",
            "--no-download",
            "--no-warnings",
            "--flat-playlist",
            "--playlist-end", str(max_results),
            self._trending_url,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"yt-dlp failed: {result.stderr}")

        videos = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            videos.append(self._parse_item(data))

        if not videos:
            videos = self._scrape_trending_shorts_direct(max_results)
        return videos

    def _scrape_trending_shorts_direct(self, max_results: int) -> list[ScrapedVideoData]:
        import requests
        import re

        html = requests.get("https://www.youtube.com/feed/trending", timeout=30).text
        video_ids = re.findall(r'\/shorts\/([a-zA-Z0-9_-]{11})', html)
        video_ids = list(dict.fromkeys(video_ids))[:max_results]

        videos = []
        for vid in video_ids:
            url = f"https://www.youtube.com/shorts/{vid}"
            try:
                cmd = [
                    "yt-dlp", "--dump-json", "--no-download", "--no-warnings", url,
                ]
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if res.returncode == 0 and res.stdout.strip():
                    data = json.loads(res.stdout)
                    videos.append(self._parse_item(data))
            except (subprocess.TimeoutExpired, json.JSONDecodeError, RuntimeError):
                continue
        return videos

    def _parse_item(self, data: dict) -> ScrapedVideoData:
        upload_ts = None
        upload_date = data.get("upload_date")
        if upload_date and len(upload_date) == 8:
            try:
                upload_ts = datetime.strptime(upload_date, "%Y%m%d")
            except ValueError:
                pass

        tags = data.get("tags") or []
        hashtags = [t for t in tags if t.startswith("#")] if tags else []
        if not hashtags and data.get("description"):
            hashtags = [
                w.strip("#") for w in data["description"].split()
                if w.startswith("#")
            ]

        return ScrapedVideoData(
            platform="youtube",
            video_url=f"https://www.youtube.com/watch?v={data.get('id', '')}",
            download_url=None,
            likes=int(data.get("like_count", 0)),
            comments=int(data.get("comment_count", 0)),
            shares=0,
            views=int(data.get("view_count", 0)),
            caption=data.get("description", ""),
            hashtags=hashtags[:20],
            music=None,
            duration=float(data.get("duration", 0)),
            author_follower_count=int(data.get("channel_follower_count", 0) or 0),
            upload_timestamp=upload_ts,
            thumbnail_url=data.get("thumbnail"),
            resolution_height=data.get("height"),
            raw_data=data,
        )
