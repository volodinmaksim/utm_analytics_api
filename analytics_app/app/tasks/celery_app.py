from celery import Celery

from analytics_app.app.db import settings

celery_app = Celery(
    "analytics_app",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "analytics_app.app.tasks.broadcasts",
    ],
)


celery_app.conf.timezone = "Europe/Moscow"
celery_app.conf.enable_utc = True


celery_app.conf.beat_schedule = {
    "process-broadcasts-every-10-seconds": {
        "task": "broadcasts.process",
        "schedule": 10.0,
    },
}
