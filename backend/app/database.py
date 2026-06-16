from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from sqlalchemy.dialects.postgresql import psycopg2 as psycopg2_dialect
from app.config import settings

psycopg2_dialect.PGDialect_psycopg2.is_async = True

sync_engine = create_engine(settings.database_url_sync, echo=settings.debug, poolclass=NullPool)
engine = AsyncEngine(sync_engine)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _migrate_schema()


MIGRATIONS = [
    "ALTER TABLE generated_videos ADD COLUMN IF NOT EXISTS total_cost FLOAT DEFAULT 0.0",
    "ALTER TABLE generated_videos ADD COLUMN IF NOT EXISTS cost_breakdown JSON DEFAULT '{}'::json",
]


async def _migrate_schema():
    async with engine.begin() as conn:
        for stmt in MIGRATIONS:
            try:
                await conn.execute(text(stmt))
            except Exception:
                pass
