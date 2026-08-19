from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Literal
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from services.api.database import engine
from services.api.models import JobRun


PROCESSING_LOCK_CONSTRAINT = "uq_job_runs_single_processing_job"

StartReason = Literal[
    "started",
    "already_completed",
    "already_processing",
]


@dataclass(frozen=True)
class StartRunResult:
    reason: StartReason
    run_id: UUID | None = None

    @property
    def started(self) -> bool:
        return self.reason == "started"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def start_job_run(
    job_name: str,
    target_date: date,
) -> StartRunResult:
    """
    Create a pending run and transition it to processing atomically.
    """

    with Session(engine) as session:
        completed_statement = (
            select(JobRun)
            .where(JobRun.job_name == job_name)
            .where(JobRun.target_date == target_date)
            .where(JobRun.status == "completed")
        )

        completed_run = session.exec(completed_statement).first()

        if completed_run is not None:
            return StartRunResult(reason="already_completed")

        run = JobRun(
            job_name=job_name,
            target_date=target_date,
            status="pending",
        )

        try:
            session.add(run)
            session.flush()

            run.status = "processing"
            run.started_at = utc_now()

            session.add(run)
            session.commit()
            session.refresh(run)

        except IntegrityError as exc:
            session.rollback()

            constraint_name = getattr(
                getattr(exc.orig, "diag", None),
                "constraint_name",
                None,
            )

            if constraint_name == PROCESSING_LOCK_CONSTRAINT:
                return StartRunResult(reason="already_processing")

            raise

        return StartRunResult(
            reason="started",
            run_id=run.id,
        )


def mark_job_completed(run_id: UUID) -> None:
    with Session(engine) as session:
        run = session.get(JobRun, run_id)

        if run is None:
            raise LookupError(f"Job run {run_id} was not found")

        if run.status != "processing":
            raise RuntimeError(
                f"Cannot complete job run {run_id} "
                f"from status {run.status!r}"
            )

        run.status = "completed"
        run.finished_at = utc_now()
        run.error_message = None

        session.add(run)
        session.commit()


def mark_job_failed(
    run_id: UUID,
    error: BaseException | str,
) -> None:
    error_message = str(error).strip() or type(error).__name__
    error_message = error_message[:4000]

    with Session(engine) as session:
        run = session.get(JobRun, run_id)

        if run is None:
            raise LookupError(f"Job run {run_id} was not found")

        if run.status != "processing":
            raise RuntimeError(
                f"Cannot fail job run {run_id} "
                f"from status {run.status!r}"
            )

        run.status = "failed"
        run.finished_at = utc_now()
        run.error_message = error_message

        session.add(run)
        session.commit()


def get_job_run(run_id: UUID) -> JobRun | None:
    with Session(engine) as session:
        return session.get(JobRun, run_id)