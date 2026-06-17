import asyncio
import json
import subprocess
from datetime import datetime

from app.scrapers.base import BaseScraper, ScrapedVideoData


class YouTubeScraper(BaseScraper):
    platform = "youtube"

    async def scrape(self, max_results: int = 200) -> list[ScrapedVideoData]:
        try:
            return await asyncio.to_thread(self._scrape_sync, max_results)
        except Exception as e:
            raise RuntimeError(f"YouTube scrape failed: {e}")

    def _scrape_sync(self, max_results: int) -> list[ScrapedVideoData]:
        queries = [
            "ytsearch100:shorts",
            "ytsearch100:trending shorts",
            "ytsearch100:viral shorts",
            "ytsearch100:#shorts",
            "https://www.youtube.com/feed/trending?bp=4gINGgt5dG91dGJlX3Nob3J0cw%3D%3D",
        ]
        seen = {}
        for query in queries:
            try:
                results = self._fetch_batch(query, max_results)
                for v in results:
                    if v.video_url not in seen and 0 < v.duration <= 90:
                        seen[v.video_url] = v
            except Exception:
                continue
            if len(seen) >= max_results:
                break
        return list(seen.values())[:max_results]

    def _fetch_batch(self, query: str, max_results: int) -> list[ScrapedVideoData]:
        cmd = [
            "yt-dlp", "--dump-json", "--no-download", "--no-warnings",
            "--ignore-no-formats-error", "--playlist-end", str(max_results),
            query,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0 and not result.stdout.strip():
            raise RuntimeError(f"yt-dlp failed: {result.stderr[:200]}")

        videos = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                v = self._parse_item(data)
                if v:
                    videos.append(v)
            except json.JSONDecodeError:
                continue
        return videos

    def _parse_item(self, data: dict):
        duration = float(data.get("duration") or 0)
        if duration <= 0 or duration > 90:
            return None

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
            hashtags = [w.strip("#") for w in data["description"].split() if w.startswith("#")]

        return ScrapedVideoData(
            platform="youtube",
            video_url=f"https://www.youtube.com/watch?v={data.get('id', '')}",
            download_url=None,
            likes=int(data.get("like_count", 0)),
            comments=int(data.get("comment_count", 0)),
            shares=0,
            views=int(data.get("view_count", 0)),
            caption=data.get("description", "").strip(),
            hashtags=hashtags[:20],
            music=None,
            duration=duration,
            author_follower_count=int(data.get("channel_follower_count", 0) or 0),
            upload_timestamp=upload_ts,
            thumbnail_url=data.get("thumbnail"),
            resolution_height=data.get("height"),
            raw_data=data,
        )
