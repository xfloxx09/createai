import asyncio
import json
import logging
from typing import Optional

from app.config import settings
from app.upload.meta import MetaUploader
from app.upload.upload_post import UploadPostClient

logger = logging.getLogger(__name__)


class UploadManager:
    def __init__(self):
        self._meta = MetaUploader() if settings.meta_page_access_token else None
        self._upload_post = UploadPostClient() if settings.upload_post_api_key else None

    async def upload_to_platforms(
        self,
        video_path: str,
        caption: str,
        platforms: list[str],
        thumbnail_path: Optional[str] = None,
    ) -> dict[str, dict]:
        results = {}
        tasks = []

        for platform in platforms:
            platform = platform.strip().lower()
            if platform in ("instagram", "facebook") and self._meta:
                tasks.append(self._upload_to_meta(platform, video_path, caption))
            elif platform in ("tiktok", "youtube") and self._upload_post:
                tasks.append(
                    self._upload_via_upload_post(
                        platform, video_path, caption, thumbnail_path
                    )
                )
            elif platform == "youtube":
                tasks.append(self._upload_to_youtube(video_path, caption))
            else:
                results[platform] = {
                    "status": "skipped",
                    "error": f"No uploader configured for {platform}",
                }

        if tasks:
            task_results = await asyncio.gather(*tasks, return_exceptions=True)
            for platform in [p for p in platforms if p.strip().lower() not in results]:
                idx = [p for p in platforms if p.strip().lower() not in list(results.keys())].index(platform) if platform in [p for p in platforms if p.strip().lower() not in list(results.keys())] else -1
            _idx = 0
            for platform in platforms:
                p = platform.strip().lower()
                if p in results:
                    continue
                result = task_results[_idx] if _idx < len(task_results) else None
                if isinstance(result, Exception):
                    results[p] = {"status": "failed", "error": str(result)}
                elif result:
                    results[p] = result
                else:
                    results[p] = {"status": "failed", "error": "Unknown error"}
                _idx += 1

        return results

    async def _upload_to_meta(self, platform: str, video_path: str, caption: str) -> dict:
        if not self._meta:
            return {"status": "skipped", "error": "Meta uploader not configured"}
        return await self._meta.post_reel(video_path, caption, platform)

    async def _upload_via_upload_post(
        self, platform: str, video_path: str, caption: str, thumbnail_path: Optional[str] = None
    ) -> dict:
        if not self._upload_post:
            return {"status": "skipped", "error": "Upload-Post not configured"}
        return await self._upload_post.upload(video_path, caption, [platform])

    async def _upload_to_youtube(self, video_path: str, caption: str) -> dict:
        from app.upload.youtube import YouTubeUploader
        uploader = YouTubeUploader()
        return await uploader.upload_short(video_path, caption)
