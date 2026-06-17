import asyncio
import json
import re
from datetime import datetime
from typing import Optional

import requests

from app.scrapers.base import BaseScraper, ScrapedVideoData


class TikTokScraper(BaseScraper):
    platform = "tiktok"

    async def scrape(self, max_results: int = 50) -> list[ScrapedVideoData]:
        try:
            return await asyncio.to_thread(self._scrape_sync, max_results)
        except Exception as e:
            raise RuntimeError(f"TikTok scrape failed: {e}")

    def _scrape_sync(self, max_results: int) -> list[ScrapedVideoData]:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.tiktok.com/",
        }

        try:
            return self._scrape_via_web_feed(headers, max_results)
        except Exception:
            try:
                return self._scrape_via_trending_page(headers, max_results)
            except Exception:
                return self._scrape_via_discover_page(headers, max_results)

    def _scrape_via_web_feed(self, headers: dict, max_results: int) -> list[ScrapedVideoData]:
        session = requests.Session()
        session.get("https://www.tiktok.com/", headers=headers, timeout=15)
        resp = session.get(
            "https://www.tiktok.com/api/recommend/item_list/",
            params={
                "aid": 1988,
                "app_name": "tiktok_web",
                "device_platform": "web_pc",
                "count": min(max_results, 30),
            },
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        items = data.get("itemList", [])
        return [self._parse_item(item) for item in items[:max_results]]

    def _scrape_via_trending_page(self, headers: dict, max_results: int) -> list[ScrapedVideoData]:
        resp = requests.get(
            "https://www.tiktok.com/trending",
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        script_match = re.search(
            r'<script id="__UNIVERSAL_DATA_FOR_VIEW_CONTAINER_TEXT"[^>]*type="application/json"[^>]*>(.*?)</script>',
            resp.text,
            re.DOTALL,
        )
        if not script_match:
            raise RuntimeError("Could not find trending data in TikTok page")

        raw = json.loads(script_match.group(1))
        default_scope = raw.get("__DEFAULT_SCOPE__", {})
        video_data = (
            default_scope.get("webapp.trending", {})
            .get("trending", {})
            .get("itemList", [])
        )
        if not video_data:
            module = default_scope.get("webapp.video-feed", {})
            for key in module:
                items = module[key].get("itemList", [])
                if items:
                    video_data = items
                    break

        return [self._parse_item(item) for item in video_data[:max_results]]

    def _scrape_via_discover_page(self, headers: dict, max_results: int) -> list[ScrapedVideoData]:
        resp = requests.get(
            "https://www.tiktok.com/discover",
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        ids = set()
        for match in re.finditer(r'data-video-id="([^"]+)"', resp.text):
            ids.add(match.group(1))
        for match in re.finditer(r'/video/(\d+)', resp.text):
            ids.add(match.group(1))
        results = []
        for vid in list(ids)[:max_results]:
            try:
                detail_resp = requests.get(
                    f"https://www.tiktok.com/api/item/detail/?itemId={vid}",
                    headers=headers,
                    timeout=15,
                )
                if detail_resp.ok:
                    detail_data = detail_resp.json()
                    if detail_data.get("itemInfo", {}).get("item"):
                        results.append(self._parse_item(detail_data["itemInfo"]["item"]))
            except Exception:
                continue
        return results

    def _parse_item(self, item: dict) -> ScrapedVideoData:
        author = item.get("author", {})
        stats = item.get("stats", {})
        music_info = item.get("music", item.get("sound", {}))
        video = item.get("video", {})

        upload_ts = None
        create_time = item.get("createTime")
        if create_time:
            try:
                upload_ts = datetime.fromtimestamp(int(create_time))
            except (ValueError, TypeError):
                pass

        desc = item.get("desc", "") or item.get("description", "")
        hashtags = []
        for ht in item.get("textExtra", []):
            tag = ht.get("hashtagName")
            if tag:
                hashtags.append(tag)

        return ScrapedVideoData(
            platform="tiktok",
            video_url=f"https://www.tiktok.com/@{author.get('uniqueId', '')}/video/{item.get('id', '')}",
            download_url=video.get("downloadAddr"),
            likes=int(stats.get("diggCount", 0)),
            comments=int(stats.get("commentCount", 0)),
            shares=int(stats.get("shareCount", 0)),
            views=int(stats.get("playCount", 0)),
            caption=desc,
            hashtags=hashtags,
            music=music_info.get("title"),
            duration=float(video.get("duration", 0)),
            author_follower_count=int(author.get("followerCount", 0)),
            upload_timestamp=upload_ts,
            thumbnail_url=video.get("cover"),
            resolution_height=video.get("height"),
            raw_data=item,
        )
