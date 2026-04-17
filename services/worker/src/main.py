"""
Celery application entry-point for the ingestion worker.

Usage:
    celery -A services.worker.src.main worker --loglevel=info
"""
from celery import Celery

from services.worker.src.config import get_worker_settings

_settings = get_worker_settings()

celery_app = Celery(
    "ai_knowledge_worker",
    broker=_settings.celery_broker_url,
    backend=_settings.celery_result_backend,
    include=[
        "services.worker.src.tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Retry failed tasks up to 3 times with exponential backoff.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)

if __name__ == "__main__":
    celery_app.start()
