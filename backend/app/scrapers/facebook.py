import asyncio
import time
from datetime import datetime
from typing import Optional

import requests

from app.scrapers.base import BaseScraper, ScrapedVideoData
from app.config_helper import get_config_value

APIFY_API = "https://api.apify.com/v2"


class FacebookScraper(BaseScraper):
    platform = "facebook"

    async def scrape(self, max_results: int = 50) -> list[ScrapedVideoData]:
        token = await get_config_value("scrape", "apify_token")
        if not token:
            raise ValueError("APIFY_TOKEN not set — add it in Admin > Scrape tab")
        self._token = token

        try:
            return await asyncio.to_thread(self._scrape_via_apify, max_results)
        except Exception as e:
            raise RuntimeError(f"Facebook scrape failed: {e}")

    def _scrape_via_apify(self, max_results: int) -> list[ScrapedVideoData]:
        headers = {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}
        run_resp = requests.post(
            f"{APIFY_API}/acts/bernardo~facebook-reels-scraper/runs",
            headers=headers,
            json={
                "startUrls": [{"url": "https://www.facebook.com/reel/"}],
                "resultsLimit": max_results,
                "proxyConfiguration": {
                    "useApifyProxy": True,
                    "apifyProxyGroups": ["RESIDENTIAL"],
                },
            },
            timeout=30,
        )
        run_resp.raise_for_status()
        run_data = run_resp.json()
        run_id = run_data.get("data", {}).get("id")
        if not run_id:
            raise RuntimeError("Failed to start Apify Facebook run")

        dataset_id = self._wait_for_run(headers, run_id)
        return self._fetch_results(headers, dataset_id, max_results)

    def _wait_for_run(self, headers: dict, run_id: str) -> str:
        for _ in range(60):
            resp = requests.get(f"{APIFY_API}/actor-runs/{run_id}", headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json().get("data", {})
            status = data.get("status")
            if status == "SUCCEEDED":
                dataset_id = data.get("defaultDatasetId")
                if dataset_id:
                    return dataset_id
                raise RuntimeError("Run succeeded but no dataset ID")
            if status in ("FAILED", "ABORTED", "TIMED-OUT"):
                raise RuntimeError(f"Apify run {status}")
            time.sleep(5)
        raise RuntimeError("Apify run timed out")

    def _fetch_results(self, headers: dict, dataset_id: str, max_results: int) -> list[ScrapedVideoData]:
        resp = requests.get(
            f"{APIFY_API}/datasets/{dataset_id}/items",
            headers=headers,
            params={"limit": max_results},
            timeout=30,
        )
        resp.raise_for_status()
        items = resp.json()
        return [self._parse_item(item) for item in items]

    def _parse_item(self, item: dict) -> ScrapedVideoData:
        upload_ts = None
        raw_ts = item.get("timestamp") or item.get("createdTime") or item.get("publishTime")
        if raw_ts:
            try:
                upload_ts = datetime.fromisoformat(str(raw_ts).replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        hashtags = item.get("hashtags") or []
        if isinstance(hashtags, str):
            hashtags = [h.strip() for h in hashtags.split(",") if h.strip()]

        return ScrapedVideoData(
            platform="facebook",
            video_url=item.get("url") or item.get("videoUrl", ""),
            download_url=item.get("downloadUrl"),
            likes=int(item.get("likeCount", 0) or item.get("likes", 0)),
            comments=int(item.get("commentCount", 0) or item.get("comments", 0)),
            shares=int(item.get("shareCount", 0) or item.get("shares", 0)),
            views=int(item.get("playCount", 0) or item.get("views", 0)),
            caption=item.get("caption") or item.get("description", ""),
            hashtags=hashtags,
            music=item.get("music") or item.get("audioTitle"),
            duration=float(item.get("duration", 0) or 0),
            author_follower_count=int(item.get("followerCount", 0) or item.get("pageFollowerCount", 0)),
            upload_timestamp=upload_ts,
            thumbnail_url=item.get("thumbnailUrl"),
            resolution_height=item.get("videoHeight"),
            raw_data=item,
        )
