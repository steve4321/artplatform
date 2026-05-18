from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "artplatform",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

conf = {
    "task_serializer": "json",
    "result_serializer": "json",
    "accept_content": ["json"],
    "timezone": "UTC",
    "task_track_started": True,
    "task_routes": {
        "app.pipeline.runner.run_pipeline": {"queue": "pipeline"},
        "app.workers.gpu_tasks.*": {"queue": "gpu"},
        "app.workers.cpu_tasks.*": {"queue": "cpu"},
    },
}

if settings.LOCAL_DEV:
    conf["task_always_eager"] = True
    conf["task_eager_propagates"] = True

celery_app.conf.update(conf)
