from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "artplatform",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_track_started=True,
    task_routes={
        "app.pipeline.runner.run_pipeline": {"queue": "pipeline"},
        "app.workers.gpu_tasks.*": {"queue": "gpu"},
        "app.workers.cpu_tasks.*": {"queue": "cpu"},
    },
)
