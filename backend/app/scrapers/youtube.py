import asyncio
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional

from app.scrapers.base import BaseScraper, ScrapedVideoData


class YouTubeScraper(BaseScraper):
    platform = "youtube"
    _trending_shorts = "https://www.youtube.com/feed/trending?bp=4gINGgt5dG91dGJlX3Nob3J0cw%3D%3D"

    async def scrape(self, max_results: int = 200) -> list[ScrapedVideoData]:
        try:
            return await asyncio.to_thread(self._scrape_sync, max_results)
        except Exception as e:
            raise RuntimeError(f"YouTube scrape failed: {e}")

    def _scrape_sync(self, max_results: int) -> list[ScrapedVideoData]:
        ids = self._collect_ids(max_results * 2)
        if not ids:
            return []
        return self._fetch_metadata_parallel(ids[:max_results])

    def _collect_ids(self, limit: int) -> list[str]:
        queries = [
            "ytsearch50:shorts",
            "ytsearch50:viral shorts",
            self._trending_shorts,
        ]
        seen = set()
        collected = []
        for q in queries:
            try:
                ids = self._extract_ids(q)
                for vid in ids:
                    if vid not in seen:
                        seen.add(vid)
                        collected.append(vid)
            except Exception:
                continue
            if len(collected) >= limit:
                break
        return collected[:limit]

    def _extract_ids(self, query: str) -> list[str]:
        cmd = [
            "yt-dlp", "--dump-json", "--no-download", "--no-warnings",
            "--flat-playlist", "--ignore-no-formats-error",
            "--playlist-end", "50", query,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0 and not result.stdout.strip():
            return []
        ids = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                dur = float(data.get("duration") or 0)
                if dur > 0 and dur <= 90:
                    ids.append(data["id"])
            except (json.JSONDecodeError, KeyError):
                continue
        return ids

    def _fetch_metadata_parallel(self, ids: list[str], workers: int = 10) -> list[ScrapedVideoData]:
        results = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            fut_map = {pool.submit(self._fetch_one, vid): vid for vid in ids}
            for fut in as_completed(fut_map):
                try:
                    data = fut.result()
                    if data:
                        v = self._parse_item(data)
                        if v:
                            results.append(v)
                except Exception:
                    continue
        return results

    def _fetch_one(self, vid: str) -> Optional[dict]:
        cmd = [
            "yt-dlp", "--dump-json", "--no-download", "--no-warnings",
            "--ignore-no-formats-error", "--skip-download",
            f"https://www.youtube.com/watch?v={vid}",
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and result.stdout.strip():
                return json.loads(result.stdout)
        except Exception:
            pass
        return None

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
        hashtags = [t.lstrip("#") for t in tags if t.startswith("#")] if tags else []
        if not hashtags and data.get("description"):
            hashtags = [w.lstrip("#") for w in data["description"].split() if w.startswith("#")]

        return ScrapedVideoData(
            platform="youtube",
            video_url=f"https://www.youtube.com/watch?v={data.get('id', '')}",
            likes=int(data.get("like_count", 0)),
            comments=int(data.get("comment_count", 0)),
            shares=0,
            views=int(data.get("view_count", 0)),
            caption=data.get("description", "") or "",
            hashtags=hashtags[:20],
            music=None,
            duration=duration,
            author_follower_count=int(data.get("channel_follower_count", 0) or 0),
            upload_timestamp=upload_ts,
            thumbnail_url=data.get("thumbnail"),
            raw_data=data,
        )
