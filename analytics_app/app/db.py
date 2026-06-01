from collections.abc import AsyncIterator

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class Settings(BaseSettings):
    DB_URL: str
    HOST: str
    PORT: int
    BASE_URL: str
    INTERNAL_SECRET_KEY: SecretStr
    ADMIN_TELEGRAM_ID: SecretStr
    ADMIN_PASSWORD: SecretStr
    ADMIN_SESSION_SECRET: SecretStr
    ADMIN_SESSION_COOKIE: str
    ADMIN_SESSION_MAX_AGE: int
    GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE: str | None = None
    GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON: str | None = None
    GOOGLE_SHEETS_SCOPES: str = "https://www.googleapis.com/auth/spreadsheets.readonly"
    PAYMENTS_SYNC_OVERLAP_ROWS: int = 50
    PAYMENTS_SOURCE_TIMEZONE: str = "UTC"
    WISH_PREFIXES: str = "user_wish:"
    POSTS_LIMIT: int = 200
    WISHES_LIMIT: int = 200
    CACHE_TTL: int = 60
    RPP_FILE_EVENT: str = (
        '\u041f\u043e\u043b\u0443\u0447\u0438\u0442\u044c \u0444\u0430\u0439\u043b: "\u041f\u0430\u043a\u0435\u0442 \u0438\u043d\u0441\u0442\u0440\u0443\u043c\u0435\u043d\u0442\u043e\u0432 \u0434\u043b\u044f \u0440\u0430\u0431\u043e\u0442\u044b \u0441 \u0420\u041f\u041f \u043e\u0442 \u0418\u0440\u0438\u043d\u044b \u0423\u0448\u0430\u043a\u043e\u0432\u043e\u0439"'
    )
    FARMA_FILE_EVENT: str = (
        '\u041f\u043e\u043b\u0443\u0447\u0438\u0442\u044c \u0444\u0430\u0439\u043b: "\u0413\u0430\u0439\u0434 \u043f\u043e \u0441\u0435\u0440\u043e\u0442\u043e\u043d\u0438\u043d\u043e\u0432\u043e\u043c\u0443 \u0441\u0438\u043d\u0434\u0440\u043e\u043c\u0443"'
    )
    SFBT_FILE_EVENT: str = (
        '\u041f\u043e\u043b\u0443\u0447\u0438\u0442\u044c \u0444\u0430\u0439\u043b: "\u041f\u0430\u043a\u0435\u0442 \u041e\u043f\u043e\u0440\u0430 \u0438 \u0420\u0435\u0441\u0443\u0440\u0441"'
    )

    model_config = SettingsConfigDict(
        env_file="analytics.env",
        env_file_encoding="utf-8",
    )


settings = Settings()

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(settings.DB_URL, pool_pre_ping=True)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            autoflush=False,
            expire_on_commit=False,
            class_=AsyncSession,
        )
    return _session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    session_factory = get_session_factory()
    session = session_factory()
    try:
        yield session
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
