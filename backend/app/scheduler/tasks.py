import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from celery import Celery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory
from app.models import ScrapedVideo, ScoredVideo, GeneratedVideo, UploadLog, ScheduleConfig
from app.scrapers.instagram import InstagramScraper
from app.scrapers.tiktok import TikTokScraper
from app.scrapers.youtube import YouTubeScraper
from app.scrapers.facebook import FacebookScraper
from app.scoring.engine import compute_virality_score
from app.generation.pipeline import VideoGenerationPipeline
from app.analysis.strategy import analyze_strategy, load_strategy

logger = logging.getLogger(__name__)

celery_app = Celery(
    "createai",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def scrape_and_score(self):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_scrape_and_score_async())
    finally:
        loop.close()


async def _scrape_and_score_async():
    scrapers = [
        InstagramScraper(),
        TikTokScraper(),
        YouTubeScraper(),
        FacebookScraper(),
    ]

    all_scraped = []
    for scraper in scrapers:
        try:
            videos = await scraper.scrape(max_results=settings.max_scrape_per_platform)
            all_scraped.append((scraper.platform, videos))
            logger.info(f"Scraped {len(videos)} from {scraper.platform}")
        except Exception as e:
            logger.error(f"Failed to scrape {scraper.platform}: {e}")

    async with async_session_factory() as session:
        trending_hashtags = await _collect_trending_hashtags(session)

        for platform, videos in all_scraped:
            for video_data in videos:
                scraped = ScrapedVideo(
                    platform=video_data.platform,
                    video_url=video_data.video_url,
                    download_url=video_data.download_url,
                    likes=video_data.likes,
                    comments=video_data.comments,
                    shares=video_data.shares,
                    views=video_data.views,
                    saves=video_data.saves,
                    caption=video_data.caption,
                    hashtags=video_data.hashtags,
                    music=video_data.music,
                    duration=video_data.duration,
                    author_follower_count=video_data.author_follower_count,
                    upload_timestamp=video_data.upload_timestamp,
                    thumbnail_url=video_data.thumbnail_url,
                    resolution_height=video_data.resolution_height,
                    raw_data=video_data.raw_data,
                )
                session.add(scraped)
                await session.flush()

                score_result = compute_virality_score(video_data, trending_hashtags)
                scored = ScoredVideo(
                    scraped_video_id=scraped.id,
                    virality_score=score_result["virality_score"],
                    engagement_rate=score_result["engagement_rate"],
                    growth_velocity=score_result["growth_velocity"],
                    sound_trend_score=score_result["sound_trend_score"],
                    hashtag_score=score_result["hashtag_score"],
                    retention_estimate=score_result["retention_estimate"],
                    author_authority=score_result["author_authority"],
                    visual_quality_estimate=score_result["visual_quality_estimate"],
                    score_breakdown=score_result,
                )
                session.add(scored)

        await session.commit()
    logger.info(f"Scrape and score complete. Total videos: {sum(len(v) for _, v in all_scraped)}")
    try:
        await analyze_strategy()
        logger.info("Content strategy analyzed and saved")
    except Exception as e:
        logger.error(f"Strategy analysis failed: {e}")


async def _collect_trending_hashtags(session: AsyncSession) -> set:
    from sqlalchemy import text

    result = await session.execute(
        text("""
            SELECT DISTINCT jsonb_array_elements_text(hashtags) as tag
            FROM scraped_videos
            WHERE scraped_at >= NOW() - INTERVAL '24 hours'
        """)
    )
    rows = result.fetchall()
    hashtag_counts = {}
    for row in rows:
        tag = row[0]
        if tag:
            hashtag_counts[tag.lower()] = hashtag_counts.get(tag.lower(), 0) + 1
    top50 = {tag for tag, _ in sorted(hashtag_counts.items(), key=lambda x: -x[1])[:50]}
    return top50


@celery_app.task(bind=True, max_retries=3)
def generate_video_task(self):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(_generate_video_async())
        return result
    finally:
        loop.close()


async def _generate_video_async() -> Optional[dict]:
    async with async_session_factory() as session:
        result = await session.execute(
            select(ScoredVideo)
            .order_by(ScoredVideo.virality_score.desc())
            .limit(10)
        )
        scored_videos = result.scalars().all()

        if not scored_videos:
            logger.warning("No scored videos available for generation")
            return None

        top_videos_data = []
        for sv in scored_videos:
            scraped = sv.scraped_video
            if scraped:
                top_videos_data.append({
                    "caption": scraped.caption,
                    "hashtags": scraped.hashtags,
                    "music": scraped.music,
                    "duration": scraped.duration,
                    "download_url": scraped.download_url,
                    "likes": scraped.likes,
                    "views": scraped.views,
                    "virality_score": sv.virality_score,
                })

    strategy = None
    try:
        strategy = await load_strategy()
    except Exception as e:
        logger.warning(f"Could not load strategy: {e}")
    pipeline = VideoGenerationPipeline()
    try:
        generation_result = await pipeline.generate(top_videos_data, strategy)
    except Exception as e:
        logger.error(f"Video generation failed: {e}")
        return None

    async with async_session_factory() as session:
        gv = GeneratedVideo(
            source_video_ids=[sv.id for sv in scored_videos],
            hook_text=generation_result["hook_text"],
            caption=generation_result["caption"],
            music_url=top_videos_data[0].get("download_url") if top_videos_data else None,
            stock_clip_url=None,
            output_path=generation_result["output_path"],
            thumbnail_path=generation_result.get("thumbnail_path"),
            duration=generation_result["duration"],
            pattern_breakdown=generation_result.get("pattern_breakdown"),
            total_cost=generation_result.get("total_cost", 0.0),
            cost_breakdown=generation_result.get("cost_breakdown", {}),
        )
        session.add(gv)
        await session.commit()

        generation_result["generated_video_id"] = gv.id

    return generation_result


@celery_app.task(bind=True, max_retries=3)
def auto_upload_task(self, generated_video_id: int):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_auto_upload_async(generated_video_id))
    finally:
        loop.close()


async def _auto_upload_async(generated_video_id: int):
    from app.upload.manager import UploadManager

    async with async_session_factory() as session:
        result = await session.execute(
            select(GeneratedVideo).where(GeneratedVideo.id == generated_video_id)
        )
        gv = result.scalar_one_or_none()
        if not gv:
            logger.error(f"GeneratedVideo {generated_video_id} not found")
            return

        manager = UploadManager()
        platforms = ["instagram", "tiktok", "youtube", "facebook"]
        results = await manager.upload_to_platforms(
            gv.output_path, gv.caption, platforms, gv.thumbnail_path
        )

        for platform, upload_result in results.items():
            log_entry = UploadLog(
                generated_video_id=gv.id,
                platform=platform,
                status=upload_result.get("status", "failed"),
                error_message=upload_result.get("error"),
                platform_post_url=upload_result.get("platform_post_url"),
                completed_at=datetime.now(timezone.utc) if upload_result.get("status") == "success" else None,
            )
            session.add(log_entry)

        await session.commit()
