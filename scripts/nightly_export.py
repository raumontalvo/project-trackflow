import csv
import json
import logging
import os
import subprocess
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import text


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.api.database import engine
from services.job_runner import (
    mark_job_completed,
    mark_job_failed,
    start_job_run,
)


JOB_NAME = "nightly_export"
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"

DEFAULT_PIPELINE_PATH = (
    PROJECT_ROOT
    / "data"
    / "pipelines"
    / "pipeline.py"
)

CSV_COLUMNS = [
    "event_id",
    "timestamp",
    "session_id",
    "user_id",
    "event_type",
    "schema_version",
    "request_id",
    "tags",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

logger = logging.getLogger(__name__)


def resolve_target_date() -> date:
    """
    Return TARGET_DATE when configured, otherwise yesterday in UTC.
    """

    configured_date = os.getenv("TARGET_DATE")

    if configured_date:
        try:
            return date.fromisoformat(configured_date)
        except ValueError as exc:
            raise ValueError(
                "TARGET_DATE must use YYYY-MM-DD format"
            ) from exc

    return datetime.now(timezone.utc).date() - timedelta(days=1)


def resolve_pipeline_path() -> Path:
    """
    Return the configured pipeline path or the repository default.

    PIPELINE_PATH exists mainly for testing failure behavior without
    modifying production code.
    """

    configured_path = os.getenv("PIPELINE_PATH")

    if configured_path:
        return Path(configured_path).expanduser().resolve()

    return DEFAULT_PIPELINE_PATH


def build_target_interval(
    target_date: date,
) -> tuple[datetime, datetime]:
    """
    Build a half-open UTC interval for the target calendar day.
    """

    interval_start = datetime.combine(
        target_date,
        time.min,
        tzinfo=timezone.utc,
    )
    interval_end = interval_start + timedelta(days=1)

    return interval_start, interval_end


def serialize_csv_value(value: object) -> object:
    """
    Convert database values into stable CSV-compatible values.
    """

    if isinstance(value, (dict, list)):
        return json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
        )

    if isinstance(value, datetime):
        return value.isoformat()

    if value is None:
        return ""

    return value


def export_telemetry_csv(target_date: date) -> Path:
    """
    Export telemetry for one UTC day.

    The CSV is an audit and recovery backup. The data pipeline continues
    reading directly from the telemetry_events database table.
    """

    RAW_DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path = (
        RAW_DATA_DIR
        / f"telemetry_{target_date.isoformat()}.csv"
    )

    if output_path.exists():
        logger.info(
            "job_name=%s status=processing "
            "target_date=%s event=csv_skipped "
            "reason=file_already_exists path=%s",
            JOB_NAME,
            target_date,
            output_path,
        )
        return output_path

    interval_start, interval_end = build_target_interval(
        target_date
    )

    query = text(
        """
        SELECT
            event_id,
            timestamp,
            session_id,
            user_id,
            event_type,
            schema_version,
            request_id,
            tags
        FROM telemetry_events
        WHERE timestamp >= :interval_start
          AND timestamp < :interval_end
        ORDER BY timestamp, event_id
        """
    )

    temporary_path = output_path.with_suffix(".csv.tmp")
    row_count = 0

    try:
        with engine.connect() as connection:
            result = connection.execute(
                query,
                {
                    "interval_start": interval_start,
                    "interval_end": interval_end,
                },
            )

            with temporary_path.open(
                "w",
                encoding="utf-8",
                newline="",
            ) as output_file:
                writer = csv.DictWriter(
                    output_file,
                    fieldnames=CSV_COLUMNS,
                )
                writer.writeheader()

                for row in result.mappings():
                    writer.writerow(
                        {
                            column: serialize_csv_value(
                                row[column]
                            )
                            for column in CSV_COLUMNS
                        }
                    )
                    row_count += 1

        temporary_path.replace(output_path)

    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise

    logger.info(
        "job_name=%s status=processing "
        "target_date=%s event=csv_exported "
        "rows=%s path=%s",
        JOB_NAME,
        target_date,
        row_count,
        output_path,
    )

    return output_path


def run_pipeline(target_date: date) -> None:
    """
    Run the existing pipeline as an independent subprocess.
    """

    pipeline_path = resolve_pipeline_path()

    if not pipeline_path.is_file():
        raise FileNotFoundError(
            f"Pipeline entry point was not found: {pipeline_path}"
        )

    environment = os.environ.copy()
    environment["TARGET_DATE"] = target_date.isoformat()

    command = [
        sys.executable,
        str(pipeline_path),
    ]

    logger.info(
        "job_name=%s status=processing "
        "target_date=%s event=pipeline_started "
        "command=%s",
        JOB_NAME,
        target_date,
        " ".join(command),
    )

    subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=environment,
        check=True,
    )

    logger.info(
        "job_name=%s status=processing "
        "target_date=%s event=pipeline_completed",
        JOB_NAME,
        target_date,
    )


def execute_nightly_job() -> int:
    """
    Run the complete nightly orchestration lifecycle.
    """

    target_date = resolve_target_date()

    start_result = start_job_run(
        job_name=JOB_NAME,
        target_date=target_date,
    )

    if start_result.reason == "already_processing":
        logger.info(
            "job_name=%s status=processing "
            "target_date=%s event=skipped "
            "reason=processing_lock_exists",
            JOB_NAME,
            target_date,
        )
        return 0

    if start_result.reason == "already_completed":
        logger.info(
            "job_name=%s status=completed "
            "target_date=%s event=skipped "
            "reason=already_completed",
            JOB_NAME,
            target_date,
        )
        return 0

    run_id: UUID | None = start_result.run_id

    if run_id is None:
        raise RuntimeError(
            "Job run started without a run ID"
        )

    logger.info(
        "job_name=%s status=processing "
        "target_date=%s run_id=%s event=started",
        JOB_NAME,
        target_date,
        run_id,
    )

    try:
        export_telemetry_csv(target_date)
        run_pipeline(target_date)
        mark_job_completed(run_id)

    except Exception as exc:
        try:
            mark_job_failed(
                run_id=run_id,
                error=exc,
            )
        except Exception:
            logger.exception(
                "job_name=%s status=failed "
                "target_date=%s run_id=%s "
                "event=status_update_failed",
                JOB_NAME,
                target_date,
                run_id,
            )

        logger.exception(
            "job_name=%s status=failed "
            "target_date=%s run_id=%s "
            "event=failed error=%s",
            JOB_NAME,
            target_date,
            run_id,
            exc,
        )
        return 1

    logger.info(
        "job_name=%s status=completed "
        "target_date=%s run_id=%s event=completed",
        JOB_NAME,
        target_date,
        run_id,
    )

    return 0


def main() -> int:
    try:
        return execute_nightly_job()
    except Exception as exc:
        logger.exception(
            "job_name=%s status=failed "
            "event=startup_failure error=%s",
            JOB_NAME,
            exc,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())