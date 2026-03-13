import uvicorn

from analytics_app.app.db import settings

if __name__ == "__main__":
    uvicorn.run(
        "analytics_app.app.main:app",
        host=settings.HOST,
        port=settings.PORT,
    )
