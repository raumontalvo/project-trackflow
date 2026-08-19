import logging
import time
from pathlib import Path

from sqlmodel import Session

from services.api.database import create_db_and_tables, engine
from services.api.models import DeadLetterTask
from services.celery_app import celery_app
from shared.incident_analysis.analyzer import analyze_csv

logger = logging.getLogger(__name__)


def record_dead_letter(
    task_id: str,
    attempt: int,
    error_message: str,
) -> None:
    create_db_and_tables()

    with Session(engine) as session:
        dead_letter = DeadLetterTask(
            task_id=task_id,
            attempt=attempt,
            error_message=error_message,
        )
        session.add(dead_letter)
        session.commit()


@celery_app.task(
    bind=True,
    name="services.tasks.analyze_incidents_task",
    max_retries=3,
)
def analyze_incidents_task(self, file_path: str) -> dict:
    task_id = self.request.id
    attempt = self.request.retries + 1
    started_at = time.monotonic()
    path = Path(file_path)
    delete_file = False

    logger.info(
        "task_id=%s attempt=%s status=started",
        task_id,
        attempt,
    )

    try:
        results = analyze_csv(file_path)
        delete_file = True

        duration = time.monotonic() - started_at
        logger.info(
            "task_id=%s attempt=%s status=success duration_seconds=%.3f",
            task_id,
            attempt,
            duration,
        )

        return results

    except Exception as error:
        duration = time.monotonic() - started_at

        logger.exception(
            "task_id=%s attempt=%s status=failure duration_seconds=%.3f error=%s",
            task_id,
            attempt,
            duration,
            str(error),
        )

        if attempt >= 3:
            record_dead_letter(
                task_id=task_id,
                attempt=attempt,
                error_message=str(error),
            )
            delete_file = True
            raise

        countdown = 2 ** attempt

        logger.info(
            "task_id=%s attempt=%s status=retrying countdown_seconds=%s",
            task_id,
            attempt,
            countdown,
        )

        raise self.retry(
            exc=error,
            countdown=countdown,
        )

    finally:
        if delete_file:
            path.unlink(missing_ok=True)
