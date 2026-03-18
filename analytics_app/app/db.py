from asyncio import current_task

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_scoped_session,
    async_sessionmaker,
    create_async_engine,
)


class Settings(BaseSettings):
    DB_URL: str
    HOST: str
    PORT: int
    BASE_URL: str
    GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE: str | None = None
    GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON: str | None = None
    GOOGLE_SHEETS_SCOPES: str = "https://www.googleapis.com/auth/spreadsheets.readonly"
    PAYMENTS_SYNC_OVERLAP_ROWS: int = 50
    WISH_PREFIXES: str = "user_wish:"
    POSTS_LIMIT: int = 200
    WISHES_LIMIT: int = 200
    CACHE_TTL: int = 60
    RPP_FILE_EVENT: str = (
        '???????? ????: "????? ???????????? ??? ?????? ? ??? ?? ????? ????????"'
    )
    FARMA_FILE_EVENT: str = '???????? ????: "???? ?? ?????????????? ????????"'

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
        _engine = create_async_engine(
            settings.DB_URL,
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            class_=AsyncSession,
        )
    return _session_factory


def get_scoped_session() -> async_scoped_session[AsyncSession]:
    return async_scoped_session(
        session_factory=get_session_factory(),
        scopefunc=current_task,
    )
