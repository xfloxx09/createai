import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import init_db, get_db, async_session_factory
from app.models import ScrapedVideo, ScoredVideo, GeneratedVideo, UploadLog, ScheduleConfig, AppConfig
from app.costs import COST_PER_SCRAPE, COST_PER_GENERATE, COST_PER_UPLOAD, PROVIDERS, estimate_full_pipeline, estimate_scrape_cost, estimate_generate_cost, estimate_upload_cost
from app.analysis.strategy import analyze_strategy, load_strategy, _default_strategy
from app.scrapers.instagram import InstagramScraper
from app.scrapers.tiktok import TikTokScraper
from app.scrapers.youtube import YouTubeScraper
from app.scrapers.facebook import FacebookScraper
from app.scoring.engine import compute_virality_score
from app.generation.pipeline import VideoGenerationPipeline
from app.upload.manager import UploadManager
from app.scheduler.tasks import scrape_and_score, generate_video_task, auto_upload_task, _scrape_and_score_async, _generate_video_async

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await _ensure_schedule_config()
    yield


async def _ensure_schedule_config():
    async with async_session_factory() as session:
        result = await session.execute(select(ScheduleConfig).where(ScheduleConfig.id == 1))
        if not result.scalar_one_or_none():
            session.add(ScheduleConfig(id=1, interval_hours=24, active=True))
            await session.commit()


app = FastAPI(
    title="CreateAI - Short Video Mass Production API",
    description="MVP for mass-producing short-form videos for Instagram Reels, TikTok, YouTube Shorts, and Facebook Reels.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    platform_filter: Optional[list[str]] = None


class UploadRequest(BaseModel):
    generated_video_id: int
    platforms: list[str]
    caption: Optional[str] = None


class ScheduleUpdateRequest(BaseModel):
    interval_hours: int


class ScrapeResponse(BaseModel):
    status: str
    message: str
    platforms_scraped: list[str]
    total_videos: int


class GenerateResponse(BaseModel):
    task_id: str
    status: str
    message: str


class UploadResponse(BaseModel):
    task_id: str
    status: str
    platforms: list[str]


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/api/videos/scored", response_model=list[dict])
async def get_scored_videos(
    limit: int = Query(50, ge=1, le=200),
    platform: Optional[str] = None,
    min_score: Optional[float] = None,
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(
            ScoredVideo.id,
            ScoredVideo.virality_score,
            ScoredVideo.score_breakdown,
            ScoredVideo.scored_at,
            ScrapedVideo.platform,
            ScrapedVideo.video_url,
            ScrapedVideo.caption,
            ScrapedVideo.hashtags,
            ScrapedVideo.thumbnail_url,
            ScrapedVideo.likes,
            ScrapedVideo.views,
            ScrapedVideo.music,
            ScrapedVideo.duration,
            ScrapedVideo.author_follower_count,
        )
        .join(ScrapedVideo, ScoredVideo.scraped_video_id == ScrapedVideo.id)
    )

    if platform:
        query = query.where(ScrapedVideo.platform == platform)
    if min_score is not None:
        query = query.where(ScoredVideo.virality_score >= min_score)

    query = query.order_by(ScoredVideo.virality_score.desc()).limit(limit)
    result = await db.execute(query)
    rows = result.all()

    return [
        {
            "id": row.id,
            "virality_score": row.virality_score,
            "score_breakdown": row.score_breakdown,
            "scored_at": row.scored_at.isoformat() if row.scored_at else None,
            "platform": row.platform,
            "video_url": row.video_url,
            "caption": row.caption[:200] if row.caption else "",
            "hashtags": row.hashtags,
            "thumbnail_url": row.thumbnail_url,
            "likes": row.likes,
            "views": row.views,
            "music": row.music,
            "duration": row.duration,
            "author_follower_count": row.author_follower_count,
        }
        for row in rows
    ]


@app.get("/api/videos/top", response_model=list[dict])
async def get_top_videos(limit: int = Query(10, ge=1, le=50), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ScoredVideo)
        .order_by(ScoredVideo.virality_score.desc())
        .limit(limit)
    )
    scored = result.scalars().all()

    output = []
    for sv in scored:
        scraped = sv.scraped_video
        output.append({
            "id": sv.id,
            "scraped_video_id": sv.scraped_video_id,
            "virality_score": sv.virality_score,
            "score_breakdown": sv.score_breakdown,
            "platform": scraped.platform if scraped else None,
            "video_url": scraped.video_url if scraped else None,
            "caption": scraped.caption[:200] if scraped and scraped.caption else "",
            "hashtags": scraped.hashtags if scraped else [],
            "duration": scraped.duration if scraped else 0,
            "likes": scraped.likes if scraped else 0,
            "views": scraped.views if scraped else 0,
            "music": scraped.music if scraped else None,
            "download_url": scraped.download_url if scraped else None,
        })
    return output


@app.post("/api/scrape/trigger")
async def trigger_scrape():
    try:
        result = await _scrape_and_score_async()
        total = result.get("total_videos", 0)
        errors = result.get("errors", {})
        msg = f"Scraped {total} videos"
        if errors:
            errs = "; ".join(f"{p}: {e}" for p, e in errors.items())
            msg += f" | Errors: {errs}"
        return {"status": "success", "message": msg, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scrape failed: {str(e)}")


@app.post("/api/generate", response_model=GenerateResponse)
async def generate_video(request: GenerateRequest, background_tasks: BackgroundTasks):
    task = generate_video_task.delay()
    return GenerateResponse(
        task_id=task.id,
        status="queued",
        message="Video generation task queued",
    )


@app.get("/api/generate/{task_id}/status")
async def get_generation_status(task_id: str):
    from celery.result import AsyncResult
    from app.scheduler.tasks import celery_app

    result = AsyncResult(task_id, app=celery_app)
    return {
        "task_id": task_id,
        "status": result.state,
        "ready": result.ready(),
        "failed": result.failed(),
    }


@app.get("/api/generate/{task_id}/result")
async def get_generation_result(task_id: str):
    from celery.result import AsyncResult
    from app.scheduler.tasks import celery_app

    result = AsyncResult(task_id, app=celery_app)
    if result.failed():
        return {"status": "failed", "error": str(result.result)}
    if not result.ready():
        return {"status": "pending"}

    data = result.result
    if not data:
        return {"status": "failed", "error": "No result data"}

    return {"status": "success", "data": data}


@app.get("/api/generated", response_model=list[dict])
async def list_generated_videos(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(GeneratedVideo).order_by(GeneratedVideo.created_at.desc()).limit(20)
    )
    videos = result.scalars().all()
    return [
        {
            "id": v.id,
            "hook_text": v.hook_text,
            "caption": v.caption,
            "output_path": v.output_path,
            "thumbnail_path": v.thumbnail_path,
            "duration": v.duration,
            "pattern_breakdown": v.pattern_breakdown,
            "total_cost": v.total_cost,
            "cost_breakdown": v.cost_breakdown,
            "created_at": v.created_at.isoformat() if v.created_at else None,
        }
        for v in videos
    ]


@app.post("/api/upload", response_model=UploadResponse)
async def upload_video(request: UploadRequest, background_tasks: BackgroundTasks):
    task = auto_upload_task.delay(request.generated_video_id)
    return UploadResponse(
        task_id=task.id,
        status="queued",
        platforms=request.platforms,
    )


@app.get("/api/upload/log", response_model=list[dict])
async def get_upload_log(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(
            UploadLog.id,
            UploadLog.platform,
            UploadLog.status,
            UploadLog.error_message,
            UploadLog.platform_post_url,
            UploadLog.created_at,
            UploadLog.completed_at,
            GeneratedVideo.hook_text,
            GeneratedVideo.caption,
        )
        .join(
            GeneratedVideo,
            UploadLog.generated_video_id == GeneratedVideo.id,
            isouter=True,
        )
        .order_by(UploadLog.created_at.desc())
        .limit(limit)
    )
    rows = result.all()
    return [
        {
            "id": row.id,
            "platform": row.platform,
            "status": row.status,
            "error_message": row.error_message,
            "platform_post_url": row.platform_post_url,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            "hook_text": row.hook_text,
            "caption_snippet": row.caption[:100] if row.caption else "",
        }
        for row in rows
    ]


@app.get("/api/schedule")
async def get_schedule(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ScheduleConfig).where(ScheduleConfig.id == 1))
    config = result.scalar_one_or_none()
    if not config:
        return {"interval_hours": 24, "active": True}
    return {
        "interval_hours": config.interval_hours,
        "active": config.active,
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
    }


@app.put("/api/schedule")
async def update_schedule(request: ScheduleUpdateRequest, db: AsyncSession = Depends(get_db)):
    if request.interval_hours not in (1, 12, 24, 168, 720):
        raise HTTPException(
            status_code=400,
            detail="interval_hours must be one of: 1, 12, 24, 168, 720",
        )

    result = await db.execute(select(ScheduleConfig).where(ScheduleConfig.id == 1))
    config = result.scalar_one_or_none()
    if config:
        config.interval_hours = request.interval_hours
        config.updated_at = datetime.now(timezone.utc)
    else:
        config = ScheduleConfig(id=1, interval_hours=request.interval_hours, active=True)
        db.add(config)
    await db.commit()

    return {"status": "updated", "interval_hours": request.interval_hours}


@app.get("/api/generated/{video_id}/download")
async def download_video(video_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GeneratedVideo).where(GeneratedVideo.id == video_id))
    video = result.scalar_one_or_none()
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    if not os.path.exists(video.output_path):
        raise HTTPException(status_code=404, detail="Video file not found on disk")

    filename = f"createai_{video_id}_{video.hook_text[:30]}.mp4"
    sanitized = "".join(c for c in filename if c.isalnum() or c in "._- ").strip()
    return FileResponse(
        video.output_path,
        media_type="video/mp4",
        filename=sanitized or f"createai_{video_id}.mp4",
    )


@app.get("/api/generated/{video_id}/thumbnail")
async def get_video_thumbnail(video_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GeneratedVideo).where(GeneratedVideo.id == video_id))
    video = result.scalar_one_or_none()
    if not video or not video.thumbnail_path or not os.path.exists(video.thumbnail_path):
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    return FileResponse(video.thumbnail_path, media_type="image/jpeg")


@app.get("/api/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    total_scraped = await db.scalar(select(func.count(ScrapedVideo.id)))
    total_scored = await db.scalar(select(func.count(ScoredVideo.id)))
    total_generated = await db.scalar(select(func.count(GeneratedVideo.id)))
    total_uploads = await db.scalar(select(func.count(UploadLog.id)))

    result = await db.execute(
        select(UploadLog.status, func.count(UploadLog.id))
        .group_by(UploadLog.status)
    )
    upload_statuses = {row.status: row[1] for row in result.all()}
    platform_result = await db.execute(
        select(ScrapedVideo.platform, func.count(ScrapedVideo.id))
        .group_by(ScrapedVideo.platform)
    )
    platform_counts = {row.platform: row[1] for row in platform_result.all()}

    return {
        "total_scraped_videos": total_scraped or 0,
        "total_scored_videos": total_scored or 0,
        "total_generated_videos": total_generated or 0,
        "total_uploads": total_uploads or 0,
        "upload_statuses": upload_statuses,
        "platform_counts": platform_counts,
    }


@app.get("/api/stats/costs")
async def get_cost_summary(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GeneratedVideo))
    videos = result.scalars().all()
    total_cost = round(sum(v.total_cost or 0 for v in videos), 6)
    scrape_cost = round(sum(((v.cost_breakdown or {}).get("scrape") or {}).get("total", 0) for v in videos), 6)
    generate_cost = round(sum(sum(((v.cost_breakdown or {}).get("generate") or {}).values()) for v in videos), 6)
    count = len(videos)
    return {
        "total_cost": total_cost,
        "scrape_cost": scrape_cost,
        "generate_cost": generate_cost,
        "videos_generated": count,
        "average_cost_per_video": round(total_cost / max(count, 1), 6),
        "cost_per_scrape": COST_PER_SCRAPE,
        "cost_per_generate": COST_PER_GENERATE,
        "cost_per_upload": COST_PER_UPLOAD,
        "providers": PROVIDERS,
    }


@app.get("/api/stats/costs/estimate")
async def estimate_costs(platforms: str = "instagram,tiktok,youtube,facebook", count: int = 10):
    platform_list = [p.strip() for p in platforms.split(",") if p.strip()]
    return estimate_full_pipeline(platform_list, count)


@app.get("/api/strategy")
async def get_strategy(db: AsyncSession = Depends(get_db)):
    strategy = await load_strategy(db)
    return strategy


@app.post("/api/strategy/refresh")
async def refresh_strategy(db: AsyncSession = Depends(get_db)):
    strategy = await analyze_strategy(db)
    return strategy


DEFAULT_CONFIGS = {
    "scrape": {
        "instagram_enabled": True,
        "tiktok_enabled": True,
        "youtube_enabled": True,
        "facebook_enabled": True,
        "max_per_platform": 50,
        "apify_token": "",
        "youtube_api_key": "",
    },
    "generate": {
        "stock_video_source": "pexels",
        "pexels_api_key": "",
        "whisper_model": "base",
        "music_enabled": False,
        "hook_style": "question",
        "caption_style": "standard",
        "max_duration": 60,
        "resolution": "1080x1920",
    },
    "upload": {
        "instagram": {"enabled": True, "app_id": "", "app_secret": "", "page_access_token": "", "ig_user_id": ""},
        "tiktok": {"enabled": True, "upload_post_api_key": ""},
        "youtube": {"enabled": True, "client_id": "", "client_secret": "", "refresh_token": ""},
        "facebook": {"enabled": True, "page_access_token": ""},
    },
}


async def _get_config(db: AsyncSession, key: str) -> dict:
    result = await db.execute(select(AppConfig).where(AppConfig.key == key))
    row = result.scalar_one_or_none()
    if row:
        return row.value
    return DEFAULT_CONFIGS.get(key, {})


@app.get("/api/admin/config/{key}")
async def get_admin_config(key: str, db: AsyncSession = Depends(get_db)):
    if key not in DEFAULT_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Unknown config key: {key}")
    config = await _get_config(db, key)
    return {"key": key, "value": config}


@app.put("/api/admin/config/{key}")
async def update_admin_config(key: str, body: dict, db: AsyncSession = Depends(get_db)):
    if key not in DEFAULT_CONFIGS:
        raise HTTPException(status_code=400, detail=f"Unknown config key: {key}")
    result = await db.execute(select(AppConfig).where(AppConfig.key == key))
    row = result.scalar_one_or_none()
    if row:
        row.value = body
    else:
        db.add(AppConfig(key=key, value=body))
    await db.commit()
    return {"status": "updated", "key": key}


frontend_dir = "/frontend"
if os.path.isdir(frontend_dir):
    assets_dir = os.path.join(frontend_dir, "assets")
    if os.path.isdir(assets_dir):
        from fastapi.staticfiles import StaticFiles
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str = ""):
        index_path = os.path.join(frontend_dir, "index.html")
        if os.path.isfile(index_path):
            return FileResponse(index_path)
        return JSONResponse({"error": "Frontend not built"}, status_code=200)
