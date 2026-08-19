from datetime import date

from sqlmodel import Session, delete

from services.api.database import engine
from services.api.models import JobRun
from services.job_runner import (
    get_job_run,
    mark_job_completed,
    mark_job_failed,
    start_job_run,
)


TEST_JOB_NAME = "nightly_export_test"
TEST_DATE = date(2099, 12, 29)


def cleanup_test_runs() -> None:
    with Session(engine) as session:
        session.exec(
            delete(JobRun).where(
                JobRun.job_name == TEST_JOB_NAME
            )
        )
        session.commit()


def test_job_run_completes_successfully():
    cleanup_test_runs()

    result = start_job_run(
        TEST_JOB_NAME,
        TEST_DATE,
    )

    assert result.started is True
    assert result.run_id is not None

    mark_job_completed(result.run_id)

    saved = get_job_run(result.run_id)

    assert saved is not None
    assert saved.status == "completed"
    assert saved.started_at is not None
    assert saved.finished_at is not None
    assert saved.error_message is None


def test_second_run_aborts_while_processing():
    cleanup_test_runs()

    first = start_job_run(
        TEST_JOB_NAME,
        TEST_DATE,
    )

    second = start_job_run(
        TEST_JOB_NAME,
        TEST_DATE,
    )

    assert first.started is True
    assert second.reason == "already_processing"

    assert first.run_id is not None
    mark_job_completed(first.run_id)


def test_completed_run_is_idempotent():
    cleanup_test_runs()

    first = start_job_run(
        TEST_JOB_NAME,
        TEST_DATE,
    )

    assert first.run_id is not None
    mark_job_completed(first.run_id)

    second = start_job_run(
        TEST_JOB_NAME,
        TEST_DATE,
    )

    assert second.reason == "already_completed"
    assert second.run_id is None


def test_failed_run_does_not_remain_processing():
    cleanup_test_runs()

    result = start_job_run(
        TEST_JOB_NAME,
        TEST_DATE,
    )

    assert result.run_id is not None

    mark_job_failed(
        result.run_id,
        RuntimeError("test failure"),
    )

    saved = get_job_run(result.run_id)

    assert saved is not None
    assert saved.status == "failed"
    assert saved.finished_at is not None
    assert saved.error_message == "test failure"