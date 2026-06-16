from celery import Celery
from celery.schedules import crontab
from sqlalchemy import create_engine, text

from app.config import settings


def get_schedule_interval() -> int:
    try:
        engine = create_engine(settings.database_url_sync)
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT interval_hours FROM schedule_config WHERE id = 1 AND active = TRUE")
            )
            row = result.fetchone()
            if row:
                return row[0]
    except Exception:
        pass
    return 24


def get_beat_schedule() -> dict:
    interval = get_schedule_interval()

    schedule_map = {
        1: crontab(minute=0),
        12: crontab(hour="*/12", minute=0),
        24: crontab(hour=0, minute=0),
        168: crontab(day_of_week=0, hour=0, minute=0),
        720: crontab(day_of_month=1, hour=0, minute=0),
    }

    schedule = schedule_map.get(interval, crontab(hour=0, minute=0))

    return {
        "scrape-and-score": {
            "task": "app.scheduler.tasks.scrape_and_score",
            "schedule": schedule,
            "options": {"queue": "default"},
        },
    }


beat_app = Celery(
    "createai-beat",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
beat_app.conf.update(
    beat_schedule=get_beat_schedule(),
    timezone="UTC",
)
