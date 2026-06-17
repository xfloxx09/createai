from app.config import settings
from app.database import async_session_factory
from app.models import AppConfig
from sqlalchemy import select


async def get_config_value(key: str, field: str, default=None):
    try:
        async with async_session_factory() as session:
            result = await session.execute(
                select(AppConfig).where(AppConfig.key == key)
            )
            config = result.scalar_one_or_none()
            if config and config.value and field in config.value:
                val = config.value[field]
                if val:
                    return val
    except Exception:
        pass
    env_val = getattr(settings, field, None)
    return env_val if env_val else default
