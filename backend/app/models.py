from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class ScrapedVideo(Base):
    __tablename__ = "scraped_videos"

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String(50), nullable=False, index=True)
    video_url = Column(Text, nullable=False)
    download_url = Column(Text, nullable=True)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    shares = Column(Integer, default=0)
    views = Column(Integer, default=0)
    saves = Column(Integer, default=0)
    caption = Column(Text, nullable=True)
    hashtags = Column(JSON, default=list)
    music = Column(String(500), nullable=True)
    duration = Column(Float, default=0.0)
    author_follower_count = Column(Integer, default=0)
    upload_timestamp = Column(DateTime, nullable=True)
    thumbnail_url = Column(Text, nullable=True)
    resolution_height = Column(Integer, nullable=True)
    raw_data = Column(JSON, nullable=True)
    scraped_at = Column(DateTime, server_default=func.now(), index=True)


class ScoredVideo(Base):
    __tablename__ = "scored_videos"

    id = Column(Integer, primary_key=True, index=True)
    scraped_video_id = Column(Integer, ForeignKey("scraped_videos.id", ondelete="CASCADE"), nullable=False)
    virality_score = Column(Float, nullable=False, index=True)
    engagement_rate = Column(Float, default=0.0)
    growth_velocity = Column(Float, default=0.0)
    sound_trend_score = Column(Float, default=0.0)
    hashtag_score = Column(Float, default=0.0)
    retention_estimate = Column(Float, default=0.0)
    author_authority = Column(Float, default=0.0)
    visual_quality_estimate = Column(Float, default=0.0)
    score_breakdown = Column(JSON, nullable=True)
    scored_at = Column(DateTime, server_default=func.now())

    scraped_video = relationship("ScrapedVideo")


class GeneratedVideo(Base):
    __tablename__ = "generated_videos"

    id = Column(Integer, primary_key=True, index=True)
    source_video_ids = Column(JSON, default=list)
    hook_text = Column(String(500), nullable=False)
    caption = Column(Text, nullable=False)
    music_url = Column(Text, nullable=True)
    stock_clip_url = Column(Text, nullable=True)
    output_path = Column(Text, nullable=False)
    thumbnail_path = Column(Text, nullable=True)
    duration = Column(Float, default=0.0)
    pattern_breakdown = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class UploadLog(Base):
    __tablename__ = "upload_logs"

    id = Column(Integer, primary_key=True, index=True)
    generated_video_id = Column(Integer, ForeignKey("generated_videos.id", ondelete="SET NULL"), nullable=True)
    platform = Column(String(50), nullable=False)
    status = Column(String(20), default="pending", index=True)
    error_message = Column(Text, nullable=True)
    platform_post_url = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)

    generated_video = relationship("GeneratedVideo")


class ScheduleConfig(Base):
    __tablename__ = "schedule_config"

    id = Column(Integer, primary_key=True, index=True)
    interval_hours = Column(Integer, default=24, nullable=False)
    active = Column(Boolean, default=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class AppConfig(Base):
    __tablename__ = "app_config"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(50), unique=True, nullable=False, index=True)
    value = Column(JSON, nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
