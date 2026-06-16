import asyncio
from datetime import datetime
from typing import Optional

from app.config import settings
from app.scrapers.base import BaseScraper, ScrapedVideoData


class InstagramScraper(BaseScraper):
    platform = "instagram"

    async def scrape(self, max_results: int = 50) -> list[ScrapedVideoData]:
        if not settings.apify_token:
            raise ValueError("APIFY_TOKEN not set")

        try:
            return await self._scrape_via_apify(max_results)
        except Exception as e:
            raise RuntimeError(f"Instagram scrape failed: {e}")

    async def _scrape_via_apify(self, max_results: int) -> list[ScrapedVideoData]:
        from apify_client import ApifyClient

        client = ApifyClient(settings.apify_token)
        run_input = {
            "searchType": "hashtag",
            "searchValue": "trending",
            "resultsLimit": max_results,
            "proxyConfiguration": {"useApifyProxy": True},
        }

        run = client.actor("vulnv~instagram-reels-scraper").call(run_input=run_input)
        results = []
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            results.append(self._parse_item(item))
            if len(results) >= max_results:
                break
        return results

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
