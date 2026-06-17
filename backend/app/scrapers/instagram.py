import asyncio
import concurrent.futures
import time
from datetime import datetime
from typing import Optional

import requests

from app.scrapers.base import BaseScraper, ScrapedVideoData
from app.config_helper import get_config_value

APIFY_API = "https://api.apify.com/v2"


class InstagramScraper(BaseScraper):
    platform = "instagram"

    async def scrape(self, max_results: int = 50) -> list[ScrapedVideoData]:
        token = await get_config_value("scrape", "apify_token")
        if not token:
            raise ValueError("APIFY_TOKEN not set — add it in Admin > Scrape tab")
        self._token = token
        self._max_results = max_results

        try:
            return await asyncio.to_thread(self._scrape_via_apify, max_results)
        except Exception as e:
            raise RuntimeError(f"Instagram scrape failed: {e}")

    def _scrape_via_apify(self, max_results: int) -> list[ScrapedVideoData]:
        headers = {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}
        hashtags = ["trending", "viral", "reels"]
        per_tag = max(1, max_results // len(hashtags))
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            futures = []
            for tag in hashtags:
                futures.append(pool.submit(self._run_single_tag, headers, tag, per_tag))
            all_results = []
            for f in futures:
                try:
                    all_results.extend(f.result(timeout=120))
                except Exception:
                    continue
        return all_results[:max_results]

    def _run_single_tag(self, headers: dict, tag: str, limit: int) -> list:
        run_resp = requests.post(
            f"{APIFY_API}/acts/apify~instagram-scraper/runs",
            headers=headers,
            json={
                "searchType": "hashtag",
                "searchValue": tag,
                "resultsLimit": limit,
                "proxyConfiguration": {"useApifyProxy": True},
            },
            timeout=30,
        )
        run_resp.raise_for_status()
        run_data = run_resp.json()
        run_id = run_data.get("data", {}).get("id")
        if not run_id:
            return []
        dataset_id = self._wait_for_run(headers, run_id)
        return self._fetch_results(headers, dataset_id, limit)

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
        likes = item.get("likeCount") or item.get("likesCount") or item.get("likes", 0)
        comments = item.get("commentsCount") or item.get("comments", 0)
        plays = item.get("playCount") or item.get("videoPlayCount") or 0
        duration = item.get("videoDuration") or item.get("duration", 0)
        if isinstance(duration, str):
            try:
                duration = float(duration)
            except (ValueError, TypeError):
                duration = 0.0

        upload_ts = None
        raw_ts = item.get("timestamp") or item.get("uploadDate") or item.get("takenAt")
        if raw_ts:
            try:
                upload_ts = datetime.fromisoformat(str(raw_ts).replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        hashtags = item.get("hashtags") or []
        if isinstance(hashtags, str):
            hashtags = [h.strip() for h in hashtags.split(",") if h.strip()]

        return ScrapedVideoData(
            platform="instagram",
            video_url=item.get("url") or item.get("videoUrl") or "",
            download_url=item.get("downloadUrl") or item.get("videoUrl"),
            likes=int(likes),
            comments=int(comments),
            shares=int(item.get("shareCount", 0)),
            views=int(plays),
            caption=item.get("caption") or item.get("text", ""),
            hashtags=hashtags,
            music=item.get("music") or item.get("audioTitle"),
            duration=float(duration),
            author_follower_count=int(item.get("ownerFollowerCount", 0) or item.get("followerCount", 0)),
            upload_timestamp=upload_ts,
            thumbnail_url=item.get("thumbnailUrl") or item.get("displayUrl"),
            resolution_height=item.get("videoHeight"),
            raw_data=item,
        )
