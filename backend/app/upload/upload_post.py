import asyncio
import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


class UploadPostClient:
    def __init__(self):
        self.api_key = settings.upload_post_api_key
        self._client = None

    async def upload(
        self, video_path: str, caption: str, platforms: list[str]
    ) -> dict:
        if not self.api_key:
            return {"status": "skipped", "error": "Upload-Post API key not set"}

        try:
            return await self._upload_via_sdk(video_path, caption, platforms)
        except ImportError:
            return await self._upload_via_http(video_path, caption, platforms)
        except Exception as e:
            logger.error(f"Upload-Post failed: {e}")
            return {"status": "failed", "error": str(e)}

    async def _upload_via_sdk(
        self, video_path: str, caption: str, platforms: list[str]
    ) -> dict:
        from upload_post import UploadPostClient as UPClient

        client = UPClient(self.api_key)
        platform_map = {
            "tiktok": "tiktok",
            "youtube": "youtube",
            "instagram": "instagram",
            "facebook": "facebook",
        }
        up_platforms = [
            platform_map.get(p) for p in platforms if platform_map.get(p)
        ]
        if not up_platforms:
            return {"status": "failed", "error": "No supported platforms"}

        result = await asyncio.to_thread(
            client.upload_video,
            video_path,
            title=caption[:100],
            user="default",
            platforms=up_platforms,
        )

        return {
            "status": "success",
            "data": result,
            "platforms": platforms,
        }

    async def _upload_via_http(
        self, video_path: str, caption: str, platforms: list[str]
    ) -> dict:
        import aiofiles
        import httpx

        async with aiofiles.open(video_path, "rb") as f:
            file_data = await f.read()

        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(
                "https://api.upload-post.com/api/upload",
                headers={"X-API-Key": self.api_key},
                files={"file": ("video.mp4", file_data, "video/mp4")},
                data={
                    "title": caption[:100],
                    "platforms": ",".join(platforms),
                    "caption": caption,
                },
            )

            if resp.status_code != 200:
                return {
                    "status": "failed",
                    "error": f"HTTP {resp.status_code}: {resp.text}",
                }

            result = resp.json()
            return {
                "status": "success" if result.get("success") else "failed",
                "data": result,
                "platforms": platforms,
            }
