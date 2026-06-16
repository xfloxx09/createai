from datetime import datetime, timezone
from typing import Optional

from app.scrapers.base import ScrapedVideoData


def compute_virality_score(video: ScrapedVideoData, trending_hashtags: set = None) -> dict:
    if trending_hashtags is None:
        trending_hashtags = set()

    views = max(video.views, 1)
    hours_since_upload = _hours_since(video.upload_timestamp)
    total_engagement = video.likes + video.comments + video.shares + video.saves

    engagement_rate = (total_engagement / views) * 100
    growth_velocity = video.likes / max(hours_since_upload, 1)
    sound_trend_score = _compute_sound_trend(video)
    hashtag_score = _compute_hashtag_score(video.hashtags, trending_hashtags)
    retention_estimate = min(1.0, video.duration / 60.0) if video.duration > 0 else 0.5
    author_authority = min(1.0, video.author_follower_count / 100000.0)
    visual_quality_estimate = 1.0 if (video.resolution_height or 0) > 720 else 0.5

    score = (
        (engagement_rate * 0.25)
        + (growth_velocity * 0.20)
        + (sound_trend_score * 0.15)
        + (hashtag_score * 0.10)
        + (retention_estimate * 0.10)
        + (author_authority * 0.10)
        + (visual_quality_estimate * 0.10)
    )

    normalized_score = min(100.0, max(0.0, score))

    return {
        "virality_score": round(normalized_score, 2),
        "engagement_rate": round(engagement_rate, 4),
        "growth_velocity": round(growth_velocity, 4),
        "sound_trend_score": round(sound_trend_score, 4),
        "hashtag_score": round(hashtag_score, 4),
        "retention_estimate": round(retention_estimate, 4),
        "author_authority": round(author_authority, 4),
        "visual_quality_estimate": round(visual_quality_estimate, 4),
        "breakdown": {
            "engagement_rate_weighted": round(engagement_rate * 0.25, 4),
            "growth_velocity_weighted": round(growth_velocity * 0.20, 4),
            "sound_trend_weighted": round(sound_trend_score * 0.15, 4),
            "hashtag_weighted": round(hashtag_score * 0.10, 4),
            "retention_weighted": round(retention_estimate * 0.10, 4),
            "author_authority_weighted": round(author_authority * 0.10, 4),
            "visual_quality_weighted": round(visual_quality_estimate * 0.10, 4),
        },
    }


def _hours_since(upload_ts: Optional[datetime]) -> float:
    if not upload_ts:
        return 24.0
    now = datetime.now(timezone.utc)
    if upload_ts.tzinfo is None:
        upload_ts = upload_ts.replace(tzinfo=timezone.utc)
    delta = now - upload_ts
    return max(delta.total_seconds() / 3600, 1.0)


def _compute_sound_trend(video: ScrapedVideoData) -> float:
    if video.music:
        return 1.0
    return 0.5


def _compute_hashtag_score(hashtags: list, trending_hashtags: set) -> float:
    if not hashtags:
        return 0.0
    trending_count = sum(1 for h in hashtags if h.lower() in trending_hashtags)
    return trending_count / len(hashtags)
