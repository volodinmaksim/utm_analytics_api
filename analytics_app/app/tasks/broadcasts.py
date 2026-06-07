import asyncio
import os
import socket

from analytics_app.app.broadcasts.repository import (
    mark_expired_collecting_templates_ready,
)
from analytics_app.app.db import get_session_factory
from analytics_app.app.broadcasts.worker import process_broadcasts
from analytics_app.app.tasks.celery_app import celery_app

BROADCASTS_LIMIT = 10
FINALIZE_TEMPLATES_LIMIT = 50


@celery_app.task(name="broadcasts.process")
def process_broadcasts_task() -> None:
    asyncio.run(_process_broadcasts())


async def _process_broadcasts() -> None:
    session_factory = get_session_factory()
    worker_id = f"{socket.gethostname()}:{os.getpid()}"

    async with session_factory() as session:
        await process_broadcasts(
            session,
            limit=BROADCASTS_LIMIT,
            worker_id=worker_id,
        )


@celery_app.task(name="telegram_templates.finalize_collecting")
def finalize_collecting_templates():
    asyncio.run(_finalize_collecting_templates())


async def _finalize_collecting_templates():
    session_factory = get_session_factory()

    async with session_factory() as session:
        await mark_expired_collecting_templates_ready(
            session, limit=FINALIZE_TEMPLATES_LIMIT
        )
        await session.commit()
