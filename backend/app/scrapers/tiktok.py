import asyncio
import json
import re
import requests
from datetime import datetime
from typing import Optional

from app.scrapers.base import BaseScraper, ScrapedVideoData


class TikTokScraper(BaseScraper):
    platform = "tiktok"

    async def scrape(self, max_results: int = 200) -> list[ScrapedVideoData]:
        try:
            return await asyncio.to_thread(self._scrape_sync, max_results)
        except Exception as e:
            raise RuntimeError(f"TikTok scrape failed: {e}")

    def _scrape_sync(self, max_results: int) -> list[ScrapedVideoData]:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.tiktok.com/",
            "Origin": "https://www.tiktok.com",
        }

        all_videos = {}
        seen_ids = set()
        errors = []

        methods = [
            ("recommend API", lambda: self._fetch_recommend_api(headers, max_results)),
            ("trending page", lambda: self._fetch_trending_page(headers, max_results)),
            ("discover page", lambda: self._fetch_discover_page(headers, max_results)),
        ]

        for name, method in methods:
            try:
                videos = method()
                for v in videos:
                    vid = v.video_url
                    if vid not in seen_ids:
                        seen_ids.add(vid)
                        all_videos[vid] = v
            except Exception as e:
                errors.append(f"{name}: {e}")
                continue
            if len(all_videos) >= max_results:
                break

        return list(all_videos.values())[:max_results]

    def _fetch_recommend_api(self, headers: dict, max_results: int) -> list[ScrapedVideoData]:
        session = requests.Session()
        session.headers.update(headers)
        session.get("https://www.tiktok.com/foryou", timeout=15)

        results = []
        count = min(30, max_results)
        url = (
            "https://www.tiktok.com/api/recommend/item_list/"
            f"?aid=1988&app_language=en&app_name=tiktok_web&browser_language=en-US"
            f"&browser_name=Mozilla&browser_version=5.0&channel=tiktok_web"
            f"&device_platform=web&focus_state=true&is_fullscreen=false"
            f"&is_page_visible=true&os=windows&priority_region=US"
            f"&region=US&screen_height=1080&screen_width=1920"
            f"&tz_name=America/New_York&count={count}"
        )
        resp = session.get(url, headers=headers, timeout=30)
        if not resp.ok:
            raise RuntimeError(f"API returned {resp.status_code}")

        data = resp.json()
        items = data.get("itemList", [])
        if not items:
            items = data.get("items", [])

        for item in items:
            try:
                results.append(self._parse_item(item))
            except Exception:
                continue
        return results

    def _fetch_trending_page(self, headers: dict, max_results: int) -> list[ScrapedVideoData]:
        resp = requests.get("https://www.tiktok.com/trending", headers=headers, timeout=30)
        resp.raise_for_status()
        script_match = re.search(
            r'<script id="__UNIVERSAL_DATA_FOR_VIEW_CONTAINER_TEXT"[^>]*>(.*?)</script>',
            resp.text,
            re.DOTALL,
        )
        if not script_match:
            raise RuntimeError("No universal data script found")
        raw = json.loads(script_match.group(1))
        default_scope = raw.get("__DEFAULT_SCOPE__", {}) or raw

        video_data = []
        keys_to_check = [
            ["webapp.trending"],
            ["webapp.video-feed"],
            ["webapp.trending-feed"],
            ["SIGI_STATE", "ItemModule"],
            ["SIGI_STATE", "VideoModule"],
        ]
        for path in keys_to_check:
            section = default_scope
            for part in path:
                section = section.get(part, {})
            if isinstance(section, dict):
                for val in section.values():
                    items = val if isinstance(val, list) else val.get("itemList", [])
                    if isinstance(items, list):
                        video_data.extend(items)
        return [self._parse_item(item) for item in video_data[:max_results]]

    def _fetch_discover_page(self, headers: dict, max_results: int) -> list[ScrapedVideoData]:
        resp = requests.get("https://www.tiktok.com/discover", headers=headers, timeout=30)
        resp.raise_for_status()
        ids = set()
        for match in re.finditer(r'/video/(\d+)', resp.text):
            ids.add(match.group(1))

        results = []
        detail_headers = {**headers, "Accept": "application/json"}
        for vid in list(ids)[:max_results]:
            try:
                detail_resp = requests.get(
                    f"https://www.tiktok.com/api/item/detail/?itemId={vid}",
                    headers=detail_headers,
                    timeout=15,
                )
                if detail_resp.ok:
                    detail_data = detail_resp.json()
                    item = detail_data.get("itemInfo", {}).get("item")
                    if item:
                        results.append(self._parse_item(item))
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

        unique_id = author.get("uniqueId", "") or item.get("authorId", "")
        item_id = item.get("id", "") or item.get("video_id", "")
        if unique_id and item_id:
            video_url = f"https://www.tiktok.com/@{unique_id}/video/{item_id}"
        elif item_id:
            video_url = f"https://www.tiktok.com/video/{item_id}"
        else:
            video_url = ""

        return ScrapedVideoData(
            platform="tiktok",
            video_url=video_url,
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
