from datetime import datetime
from typing import Optional

from app.config import settings
from app.scrapers.base import BaseScraper, ScrapedVideoData
from app.config_helper import get_config_value


class FacebookScraper(BaseScraper):
    platform = "facebook"

    async def scrape(self, max_results: int = 50) -> list[ScrapedVideoData]:
        token = await get_config_value("scrape", "apify_token")
        if not token:
            raise ValueError("APIFY_TOKEN not set — add it in Admin > Scrape tab")
        self._token = token

        try:
            return await self._scrape_via_apify(max_results)
        except Exception as e:
            raise RuntimeError(f"Facebook scrape failed: {e}")

    async def _scrape_via_apify(self, max_results: int) -> list[ScrapedVideoData]:
        from apify_client import ApifyClient

        client = ApifyClient(self._token)
        run_input = {
            "startUrls": [{"url": "https://www.facebook.com/reel/"}],
            "resultsLimit": max_results,
            "proxyConfiguration": {
                "useApifyProxy": True,
                "apifyProxyGroups": ["RESIDENTIAL"],
            },
        }

        run = client.actor("scrapers-hub~facebook-reels-scraper").call(run_input=run_input)
        results = []
        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            results.append(self._parse_item(item))
            if len(results) >= max_results:
                break
        return results

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
