import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Response, status

from analytics_app.app.db import settings

ADMIN_SESSION_KEY = "admin"


def ensure_admin_auth_configured() -> None:
    if settings.ADMIN_PASSWORD and settings.ADMIN_SESSION_SECRET:
        return
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Admin authentication is not configured",
    )


def verify_admin_password(password: str) -> bool:
    ensure_admin_auth_configured()
    return secrets.compare_digest(password, settings.ADMIN_PASSWORD or "")


def is_admin_authenticated(request: Request) -> bool:
    ensure_admin_auth_configured()
    token = request.cookies.get(settings.ADMIN_SESSION_COOKIE)
    if not token:
        return False
    payload = _unsign_session_token(token)
    if payload is None:
        return False
    return bool(payload.get(ADMIN_SESSION_KEY))


def login_admin(response: Response) -> None:
    ensure_admin_auth_configured()
    token = _sign_session_token(
        {
            ADMIN_SESSION_KEY: True,
            "exp": int(time.time()) + settings.ADMIN_SESSION_MAX_AGE,
        }
    )
    response.set_cookie(
        key=settings.ADMIN_SESSION_COOKIE,
        value=token,
        max_age=settings.ADMIN_SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
    )


def logout_admin(response: Response) -> None:
    response.delete_cookie(settings.ADMIN_SESSION_COOKIE)


async def require_admin_api(request: Request) -> None:
    if is_admin_authenticated(request):
        return
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Admin authentication required",
    )


def _sign_session_token(payload: dict[str, object]) -> str:
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    encoded = base64.urlsafe_b64encode(body).decode("ascii")
    signature = hmac.new(
        settings.ADMIN_SESSION_SECRET.encode("utf-8"),
        encoded.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return f"{encoded}.{signature}"


def _unsign_session_token(token: str) -> dict[str, object] | None:
    try:
        encoded, signature = token.rsplit(".", 1)
    except ValueError:
        return None

    expected = hmac.new(
        settings.ADMIN_SESSION_SECRET.encode("utf-8"),
        encoded.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None

    try:
        payload = json.loads(base64.urlsafe_b64decode(encoded.encode("ascii")))
    except (ValueError, json.JSONDecodeError):
        return None

    expires_at = payload.get("exp")
    if not isinstance(expires_at, int) or expires_at < int(time.time()):
        return None
    return payload


AdminApiDep = Annotated[None, Depends(require_admin_api)]
