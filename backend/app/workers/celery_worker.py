"""Celery task worker configuration for asynchronous video & image analysis."""
import os
import logging
from app.workers.analysis_worker import execute_analysis_job

logger = logging.getLogger("crowdlytics.celery")

# Attempt Celery import if installed; otherwise fallback gracefully
try:
    from celery import Celery

    broker_url = os.getenv("CELERY_BROKER_URL", os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"))
    result_backend = os.getenv("CELERY_RESULT_BACKEND", broker_url)

    celery_app = Celery(
        "crowdlytics_tasks",
        broker=broker_url,
        backend=result_backend,
    )

    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
    )

    @celery_app.task(name="tasks.execute_analysis_job", bind=True, max_retries=2)
    def celery_execute_analysis_job(self, job_id: str):
        """Celery worker task wrapper around execute_analysis_job."""
        logger.info("Executing analysis job via Celery: %s", job_id)
        try:
            execute_analysis_job(job_id)
        except Exception as exc:
            logger.error("Celery task error on job %s: %s", job_id, exc)
            raise self.retry(exc=exc, countdown=5)

except ImportError:
    celery_app = None


if __name__ == "__main__":
    if celery_app is not None:
        celery_app.worker_main(["worker", "--loglevel=info", "-c", "2"])
    else:
        print("Celery not installed or running in standalone mode.")
