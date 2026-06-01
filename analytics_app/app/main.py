from fastapi import FastAPI

from analytics_app.app.routers.dashboard import router as dashboard_router
from analytics_app.app.routers.internal import router as internal_router
from analytics_app.app.db import settings

app = FastAPI(title="UTM Analytics", version="1.0.0")
app.include_router(dashboard_router)
app.include_router(internal_router)


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok", "base_url": settings.BASE_URL.rstrip("/")}
