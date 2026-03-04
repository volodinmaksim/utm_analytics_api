import uvicorn

from appv1.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "appv1.main:app",
        host=settings.HOST,
        port=settings.PORT,
    )
