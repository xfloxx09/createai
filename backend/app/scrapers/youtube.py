import asyncio
import json
import subprocess
import re
from datetime import datetime
from typing import Optional

import requests

from app.scrapers.base import BaseScraper, ScrapedVideoData


class YouTubeScraper(BaseScraper):
    platform = "youtube"

    async def scrape(self, max_results: int = 200) -> list[ScrapedVideoData]:
        try:
            return await asyncio.to_thread(self._scrape_sync, max_results)
        except Exception as e:
            raise RuntimeError(f"YouTube scrape failed: {e}")

    def _scrape_sync(self, max_results: int) -> list[ScrapedVideoData]:
        seen_ids = set()
        all_videos = []

        feeds = [
            "https://www.youtube.com/feed/trending",
            "https://www.youtube.com/feed/explore",
        ]

        for feed_url in feeds:
            ids = self._extract_shorts_ids(feed_url)
            for vid_id in ids:
                if vid_id in seen_ids:
                    continue
                seen_ids.add(vid_id)
                try:
                    data = self._fetch_video_data(vid_id)
                    if data:
                        all_videos.append(self._parse_item(data))
                except Exception:
                    continue
                if len(all_videos) >= max_results:
                    return all_videos

        if all_videos:
            return all_videos

        ids = self._fetch_from_search(max_results)
        for vid_id in ids:
            if vid_id in seen_ids:
                continue
            seen_ids.add(vid_id)
            try:
                data = self._fetch_video_data(vid_id)
                if data:
                    all_videos.append(self._parse_item(data))
            except Exception:
                continue
            if len(all_videos) >= max_results:
                break

        return all_videos

    def _extract_shorts_ids(self, url: str) -> list[str]:
        try:
            html = requests.get(url, timeout=30).text
            ids = re.findall(r'\/shorts\/([a-zA-Z0-9_-]{11})', html)
            return list(dict.fromkeys(ids))
        except Exception:
            return []

    def _fetch_from_search(self, max_results: int) -> list[str]:
        try:
            cmd = [
                "yt-dlp", "--dump-json", "--no-download", "--no-warnings",
                "--flat-playlist", "--playlist-end", str(max_results * 2),
                "ytsearch:shorts",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                return []
            ids = []
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                    vid = data.get("id")
                    if vid:
                        ids.append(vid)
                except json.JSONDecodeError:
                    continue
            return ids
        except Exception:
            return []

    def _fetch_video_data(self, vid: str) -> Optional[dict]:
        try:
            cmd = [
                "yt-dlp", "--dump-json", "--no-download", "--no-warnings",
                "--skip-download", f"https://www.youtube.com/shorts/{vid}",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and result.stdout.strip():
                return json.loads(result.stdout)
            cmd = [
                "yt-dlp", "--dump-json", "--no-download", "--no-warnings",
                "--skip-download", f"https://www.youtube.com/watch?v={vid}",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and result.stdout.strip():
                return json.loads(result.stdout)
        except Exception:
            pass
        return None

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
