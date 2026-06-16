import asyncio
import logging
import os
import time
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class MetaUploader:
    def __init__(self):
        self.access_token = settings.meta_page_access_token
        self.ig_user_id = settings.meta_ig_user_id
        self.api_version = "v21.0"
        self.base_url = f"https://graph.facebook.com/{self.api_version}"

    async def post_reel(
        self, video_path: str, caption: str, platform: str = "instagram"
    ) -> dict:
        if not self.access_token or not self.ig_user_id:
            return {"status": "skipped", "error": "Meta API not configured"}

        video_url = await self._host_video_temporarily(video_path)
        if not video_url:
            return {"status": "failed", "error": "Could not host video publicly"}

        async with httpx.AsyncClient(timeout=120) as client:
            container_id = await self._create_container(client, video_url, caption)
            if not container_id:
                return {"status": "failed", "error": "Failed to create container"}

            poll_status = await self._poll_container(client, container_id)
            if poll_status != "FINISHED":
                return {"status": "failed", "error": f"Container processing failed: {poll_status}"}

            publish_result = await self._publish_container(client, container_id)
            if not publish_result:
                return {"status": "failed", "error": "Failed to publish container"}

        return {
            "status": "success",
            "platform_post_id": publish_result,
            "platform": platform,
        }

    async def _create_container(self, client: httpx.AsyncClient, video_url: str, caption: str) -> Optional[str]:
        data = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption[:2200],
            "share_to_feed": "true",
            "access_token": self.access_token,
        }
        resp = await client.post(
            f"{self.base_url}/{self.ig_user_id}/media",
            data=data,
        )
        if resp.status_code != 200:
            logger.error(f"Container creation failed: {resp.text}")
            return None
        result = resp.json()
        return result.get("id")

    async def _poll_container(self, client: httpx.AsyncClient, container_id: str, max_wait: int = 300) -> str:
        for _ in range(max_wait // 5):
            resp = await client.get(
                f"{self.base_url}/{container_id}",
                params={"fields": "status_code", "access_token": self.access_token},
            )
            if resp.status_code != 200:
                await asyncio.sleep(5)
                continue
            status = resp.json().get("status_code", "")
            if status == "FINISHED":
                return "FINISHED"
            if status in ("ERROR", "EXPIRED"):
                return status
            await asyncio.sleep(5)
        return "TIMEOUT"

    async def _publish_container(self, client: httpx.AsyncClient, container_id: str) -> Optional[str]:
        resp = await client.post(
            f"{self.base_url}/{self.ig_user_id}/media_publish",
            data={
                "creation_id": container_id,
                "access_token": self.access_token,
            },
        )
        if resp.status_code != 200:
            logger.error(f"Publish failed: {resp.text}")
            return None
        result = resp.json()
        return result.get("id")

    async def _host_video_temporarily(self, video_path: str) -> Optional[str]:
        import aiofiles

        if not os.path.exists(video_path):
            return None

        public_url = os.environ.get("PUBLIC_VIDEO_URL_BASE")
        if public_url:
            return f"{public_url.rstrip('/')}/{os.path.basename(video_path)}"

        return await self._upload_to_tmp_storage(video_path)

    async def _upload_to_tmp_storage(self, video_path: str) -> Optional[str]:
        try:
            async with aiofiles.open(video_path, "rb") as f:
                file_data = await f.read()

            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    "https://file.io/",
                    files={"file": ("video.mp4", file_data, "video/mp4")},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("success"):
                        return data.get("link")
        except Exception as e:
            logger.warning(f"Temp hosting failed: {e}")

        try:
            import subprocess
            local_ip = subprocess.run(
                ["hostname", "-I"], capture_output=True, text=True, timeout=5
            ).stdout.strip().split()[0]
            if local_ip:
                filename = os.path.basename(video_path)
                subprocess.Popen(
                    ["python", "-m", "http.server", "8899", "--directory", os.path.dirname(video_path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                await asyncio.sleep(1)
                return f"http://{local_ip}:8899/{filename}"
        except Exception:
            pass

        return None
