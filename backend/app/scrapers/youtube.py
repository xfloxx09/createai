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
                    if v.video_url not in seen:
                        seen[v.video_url] = v
            except Exception:
                continue
            if len(seen) >= max_results * 2:
                break

        unique = list(seen.values())[:max_results]
        return unique

    def _fetch_batch(self, query: str, max_results: int) -> list[ScrapedVideoData]:
        cmd = [
            "yt-dlp", "--dump-json", "--no-download", "--no-warnings",
            "--flat-playlist", "--ignore-no-formats-error",
            "--playlist-end", str(max_results), query,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
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

        return ScrapedVideoData(
            platform="youtube",
            video_url=f"https://www.youtube.com/watch?v={data.get('id', '')}",
            likes=int(data.get("view_count", 0)),
            views=int(data.get("view_count", 0)),
            caption=data.get("title", ""),
            duration=duration,
            upload_timestamp=upload_ts,
            thumbnail_url=data.get("thumbnail"),
            raw_data=data,
        )
