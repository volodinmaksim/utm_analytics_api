import secrets
from typing import Annotated

from fastapi import Header, HTTPException, status

from analytics_app.app.db import settings

INTERNAL_SECRET_HEADER = "X-Internal-API-Key"


async def require_internal_api(
    x_internal_api_key: Annotated[
        str | None, Header(alias=INTERNAL_SECRET_HEADER)
    ] = None,
) -> None:
    if x_internal_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal API key",
        )

    expected = settings.INTERNAL_SECRET_KEY.get_secret_value()
    if not secrets.compare_digest(x_internal_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal API key",
        )

    return None
