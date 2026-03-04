from asyncio import current_task

from sqlalchemy.ext.asyncio import (
    async_scoped_session,
    async_sessionmaker,
    create_async_engine,
)

from appv1.config import settings


class DataBaseHelper:
    def __init__(self, url: str):
        self.engine = create_async_engine(url, pool_pre_ping=True)
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )

    def get_scoped_session(self):
        return async_scoped_session(
            session_factory=self.session_factory,
            scopefunc=current_task,
        )


db_helper = DataBaseHelper(settings.DB_URL)
