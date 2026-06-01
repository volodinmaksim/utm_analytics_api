from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from analytics_app.app.broadcasts.templates import ingest_telegram_message
from analytics_app.app.db import get_session
from analytics_app.app.internal_auth import require_internal_api
from analytics_app.app.schemas.broadcasts import (
    TelegramTemplateIngestResponse,
    TelegramTemplateIngestRequest,
)

router = APIRouter(prefix="/api/internal")


@router.post(
    "/telegram-templates/ingest",
    response_model=TelegramTemplateIngestResponse,
)
async def telegram_templates_ingest(
    data: TelegramTemplateIngestRequest,
    session: AsyncSession = Depends(get_session),
    _auth: None = Depends(require_internal_api),
):
    message = data.message
    return await ingest_telegram_message(
        session,
        message=message,
    )
