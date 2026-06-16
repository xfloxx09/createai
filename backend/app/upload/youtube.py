import asyncio
import logging
import os
from typing import Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from app.config import settings

logger = logging.getLogger(__name__)


class YouTubeUploader:
    def __init__(self):
        self.api_key = settings.youtube_api_key
        self.client_id = settings.youtube_client_id
        self.client_secret = settings.youtube_client_secret
        self.refresh_token = settings.youtube_refresh_token

    async def upload_short(self, video_path: str, caption: str) -> dict:
        if not self._is_configured():
            return {"status": "skipped", "error": "YouTube API not configured"}

        try:
            result = await asyncio.to_thread(
                self._upload_sync, video_path, caption
            )
            return result
        except Exception as e:
            logger.error(f"YouTube upload failed: {e}")
            return {"status": "failed", "error": str(e)}

    def _is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret and self.refresh_token)

    def _upload_sync(self, video_path: str, caption: str) -> dict:
        creds = Credentials(
            token=None,
            refresh_token=self.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=["https://www.googleapis.com/auth/youtube.upload"],
        )

        youtube = build("youtube", "v3", credentials=creds)

        title = caption.split("\n")[0][:100] if caption else "Short Video"
        description = caption[:5000] if caption else ""

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": ["shorts", "viral", "trending"],
                "categoryId": "22",
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False,
            },
        }

        media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")

        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        response = request.execute()
        video_id = response.get("id")

        return {
            "status": "success" if video_id else "failed",
            "platform_post_url": f"https://youtu.be/{video_id}" if video_id else None,
            "platform_post_id": video_id,
            "platform": "youtube",
        }
