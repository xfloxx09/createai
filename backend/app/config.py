from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@postgres:5432/createai"
    database_url_sync: str = "postgresql://postgres:postgres@postgres:5432/createai"
    redis_url: str = "redis://redis:6379/0"

    apify_token: Optional[str] = None
    pexels_api_key: Optional[str] = None

    meta_app_id: Optional[str] = None
    meta_app_secret: Optional[str] = None
    meta_page_access_token: Optional[str] = None
    meta_ig_user_id: Optional[str] = None

    youtube_api_key: Optional[str] = None
    youtube_client_id: Optional[str] = None
    youtube_client_secret: Optional[str] = None
    youtube_refresh_token: Optional[str] = None

    upload_post_api_key: Optional[str] = None

    celery_broker_url: str = ""
    celery_result_backend: str = ""

    temp_dir: str = "/tmp/createai"
    max_scrape_per_platform: int = 200
    whisper_model: str = "base"
    debug: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    def model_post_init(self, __context):
        if not self.celery_broker_url:
            self.celery_broker_url = self.redis_url
        if not self.celery_result_backend:
            self.celery_result_backend = self.redis_url


settings = Settings()
