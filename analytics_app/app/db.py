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

    ADMIN_TELEGRAM_ID: int
    RPP_BOT_TOKEN: SecretStr
    FARMA_BOT_TOKEN: SecretStr
    SFBT_BOT_TOKEN: SecretStr
    CBTBASE_BOT_TOKEN: SecretStr | None = None
    PSYGASTRO_BOT_TOKEN: SecretStr | None = None

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
        'Получить файл: "Пакет инструментов для работы с РПП от Ирины Ушаковой"'
    )
    FARMA_FILE_EVENT: str = 'Получить файл: "Гайд по серотониновому синдрому"'
    SFBT_FILE_EVENT: str = 'Получить файл: "Пакет Опора и Ресурс"'
    CBTBASE_FILE_EVENT: str = 'Получить файл: "Протокол КПТ-сессии"'
    PSYGASTRO_FILE_EVENT: str = 'Получить файл: "Шкала оценки тяжести симптомов СРК"'

    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

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
