import asyncio
from datetime import datetime
from typing import Optional

from app.scrapers.base import BaseScraper, ScrapedVideoData


class TikTokScraper(BaseScraper):
    platform = "tiktok"

    async def scrape(self, max_results: int = 50) -> list[ScrapedVideoData]:
        try:
            return await self._scrape_via_tiktokapi(max_results)
        except ImportError:
            raise RuntimeError(
                "TikTokApi not installed. Run: pip install TikTokApi && playwright install chromium"
            )
        except Exception as e:
            raise RuntimeError(f"TikTok scrape failed: {e}")

    async def _scrape_via_tiktokapi(self, max_results: int) -> list[ScrapedVideoData]:
        from TikTokApi import TikTokApi

        results = []
        async with TikTokApi() as api:
            await api.create_sessions(headless=True, num_sessions=1)
            async for video in api.trending.videos(count=max_results):
                item = video.as_dict
                results.append(self._parse_item(item))
                if len(results) >= max_results:
                    break
        return results

    def _parse_item(self, item: dict) -> ScrapedVideoData:
        stats = item.get("stats", {})
        author = item.get("author", {})
        music_info = item.get("music", {})
        video = item.get("video", {})

        upload_ts = None
        create_time = item.get("createTime")
        if create_time:
            try:
                upload_ts = datetime.fromtimestamp(int(create_time))
            except (ValueError, TypeError):
                pass

        desc = item.get("desc", "")
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
