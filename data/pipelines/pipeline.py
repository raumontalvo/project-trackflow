import hashlib
import json
import sys
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from prefect import flow, get_run_logger, task
from prefect.runtime import flow_run
from prefect.states import State
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, select

from services.api.database import engine
from services.api.models import (
    PipelineRun,
    TelemetryEventRecord,
    WeeklyWarehouseClientPerformance,
)


PIPELINE_NAME = "weekly_warehouse_client_performance"

BUSINESS_EVENT_TYPES = {
    "inbound_order_created",
    "outbound_order_created",
    "stock_threshold_triggered",
    "inventory_discrepancy_detected",
}

VALID_WAREHOUSES = {
    "los_angeles",
    "zaragoza",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def resolve_week_start(value: date | str | None = None) -> date:
    if value is None:
        today = utc_now().date()
        current_monday = today - timedelta(days=today.weekday())
        return current_monday - timedelta(days=7)

    if isinstance(value, str):
        value = date.fromisoformat(value)

    if value.weekday() != 0:
        raise ValueError("week_start must be a Monday")

    return value


def build_week_interval(week_start: date) -> tuple[datetime, datetime]:
    interval_start = datetime.combine(
        week_start,
        time.min,
        tzinfo=timezone.utc,
    )
    interval_end = interval_start + timedelta(days=7)

    return interval_start, interval_end


def transformation_cache_key(
    task_context: Any,
    parameters: dict[str, Any],
) -> str:
    """
    The cache key is derived from the exact extracted source records.

    If event IDs, timestamps, event types, or tags change, the key changes.
    The task result remains valid for one hour.
    """

    serialized = json.dumps(
        parameters,
        sort_keys=True,
        default=str,
    )

    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def get_prefect_flow_run_id() -> str | None:
    try:
        return str(flow_run.id) if flow_run.id else None
    except Exception:
        return None


@task(
    name="create_pipeline_run_log",
    retries=2,
    retry_delay_seconds=5,
)
def create_pipeline_run_log(
    week_start: date,
    trigger_type: str,
    interval_start: datetime,
    interval_end: datetime,
) -> str:
    """
    Two retries cover short database connection interruptions while
    avoiding long delays before the main pipeline begins.
    """

    run = PipelineRun(
        pipeline_name=PIPELINE_NAME,
        target_week_start=week_start,
        trigger_type=trigger_type,
        status="Running",
        started_at=utc_now(),
        source_interval_start=interval_start,
        source_interval_end=interval_end,
        prefect_flow_run_id=get_prefect_flow_run_id(),
    )

    with Session(engine) as session:
        session.add(run)
        session.commit()
        session.refresh(run)

    return str(run.id)


@task(
    name="extract_weekly_business_events",
    retries=3,
    retry_delay_seconds=10,
)
def extract_weekly_business_events(
    interval_start: datetime,
    interval_end: datetime,
) -> dict[str, Any]:
    """
    Three retries absorb transient database/network failures without
    requiring manual intervention.
    """

    statement = (
        select(TelemetryEventRecord)
        .where(TelemetryEventRecord.timestamp >= interval_start)
        .where(TelemetryEventRecord.timestamp < interval_end)
        .where(
            TelemetryEventRecord.event_type.in_(
                BUSINESS_EVENT_TYPES
            )
        )
        .order_by(TelemetryEventRecord.timestamp)
    )

    with Session(engine) as session:
        records = session.exec(statement).all()

    events = [
        {
            "event_id": record.event_id,
            "timestamp": record.timestamp,
            "event_type": record.event_type,
            "tags": record.tags,
        }
        for record in records
    ]

    highest_timestamp = (
        max(event["timestamp"] for event in events)
        if events
        else None
    )

    return {
        "events": events,
        "extracted_records": len(events),
        "highest_event_timestamp": highest_timestamp,
    }


@task(
    name="deduplicate_and_validate_events",
)
def deduplicate_and_validate_events(
    extraction: dict[str, Any],
) -> dict[str, Any]:
    clean_events: dict[str, dict[str, Any]] = {}
    rejected_records = 0
    duplicate_records = 0

    for event in extraction["events"]:
        event_id = event.get("event_id")
        timestamp_value = event.get("timestamp")
        event_type = event.get("event_type")
        tags = event.get("tags") or {}

        warehouse = tags.get("warehouse")
        client_id = tags.get("client_id")
        quantity = tags.get("quantity")

        if (
            not event_id
            or timestamp_value is None
            or event_type not in BUSINESS_EVENT_TYPES
            or warehouse not in VALID_WAREHOUSES
            or not isinstance(client_id, str)
            or not client_id.strip()
        ):
            rejected_records += 1
            continue

        if event_type == "inbound_order_created":
            if (
                not isinstance(quantity, int)
                or isinstance(quantity, bool)
                or quantity < 0
            ):
                rejected_records += 1
                continue

        normalized = {
            "event_id": event_id,
            "timestamp": timestamp_value,
            "event_type": event_type,
            "warehouse": warehouse,
            "client_id": client_id.strip(),
            "quantity": quantity,
        }

        existing = clean_events.get(event_id)

        if existing is not None:
            duplicate_records += 1

            if timestamp_value <= existing["timestamp"]:
                continue

        clean_events[event_id] = normalized

    return {
        "events": list(clean_events.values()),
        "processed_records": len(clean_events),
        "rejected_records": rejected_records,
        "duplicate_records": duplicate_records,
    }


@task(
    name="aggregate_weekly_warehouse_client_metrics",
    cache_key_fn=transformation_cache_key,
    cache_expiration=timedelta(hours=1),
)
def aggregate_weekly_warehouse_client_metrics(
    transformed: dict[str, Any],
    week_start: date,
) -> list[dict[str, Any]]:
    """
    Results are cached for one hour. The cache key is based on the exact
    transformed input data and the requested ISO week.
    """

    grouped: dict[
        tuple[str, str, date],
        dict[str, Any],
    ] = {}

    for event in transformed["events"]:
        key = (
            event["warehouse"],
            event["client_id"],
            week_start,
        )

        row = grouped.setdefault(
            key,
            {
                "warehouse": event["warehouse"],
                "client_id": event["client_id"],
                "week_start": week_start,
                "inbound_units_count": 0,
                "outbound_orders_count": 0,
                "stockout_events_count": 0,
                "discrepancy_events_count": 0,
                "discrepancy_rate": Decimal("0"),
            },
        )

        event_type = event["event_type"]

        if event_type == "inbound_order_created":
            row["inbound_units_count"] += event["quantity"]

        elif event_type == "outbound_order_created":
            row["outbound_orders_count"] += 1

        elif event_type == "stock_threshold_triggered":
            row["stockout_events_count"] += 1

        elif event_type == "inventory_discrepancy_detected":
            row["discrepancy_events_count"] += 1

    for row in grouped.values():
        outbound_count = row["outbound_orders_count"]

        row["discrepancy_rate"] = (
            Decimal(row["discrepancy_events_count"])
            / Decimal(outbound_count)
            if outbound_count > 0
            else Decimal("0")
        )

    return list(grouped.values())


@task(name="validate_weekly_metrics")
def validate_weekly_metrics(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    seen_keys: set[tuple[str, str, date]] = set()

    for row in rows:
        key = (
            row["warehouse"],
            row["client_id"],
            row["week_start"],
        )

        if key in seen_keys:
            raise ValueError(
                "Duplicate warehouse/client/week result detected"
            )

        seen_keys.add(key)

        if row["warehouse"] not in VALID_WAREHOUSES:
            raise ValueError("Invalid warehouse in aggregate result")

        if not row["client_id"]:
            raise ValueError("client_id cannot be empty")

        count_fields = (
            "inbound_units_count",
            "outbound_orders_count",
            "stockout_events_count",
            "discrepancy_events_count",
        )

        if any(row[field] < 0 for field in count_fields):
            raise ValueError("Aggregate counts cannot be negative")

        if row["discrepancy_rate"] < 0:
            raise ValueError(
                "discrepancy_rate cannot be negative"
            )

    return rows


@task(
    name="upsert_weekly_performance_rows",
    retries=3,
    retry_delay_seconds=10,
)
def upsert_weekly_performance_rows(
    rows: list[dict[str, Any]],
) -> int:
    """
    Three retries are safe because the load uses an idempotent upsert
    keyed by warehouse, client_id, and week_start.
    """

    if not rows:
        return 0

    now = utc_now()

    values = [
        {
            **row,
            "computed_at": now,
        }
        for row in rows
    ]

    statement = insert(
        WeeklyWarehouseClientPerformance.__table__
    ).values(values)

    statement = statement.on_conflict_do_update(
        index_elements=[
            "warehouse",
            "client_id",
            "week_start",
        ],
        set_={
            "inbound_units_count": statement.excluded.inbound_units_count,
            "outbound_orders_count": statement.excluded.outbound_orders_count,
            "stockout_events_count": statement.excluded.stockout_events_count,
            "discrepancy_events_count": statement.excluded.discrepancy_events_count,
            "discrepancy_rate": statement.excluded.discrepancy_rate,
            "computed_at": statement.excluded.computed_at,
        },
    )

    with engine.begin() as connection:
        connection.execute(statement)

    return len(rows)


@task(
    name="optional_pipeline_summary",
)
def optional_pipeline_summary(
    week_start: date,
    loaded_records: int,
) -> dict[str, Any]:
    """
    Optional summary step. A failure here must not interrupt the main
    pipeline execution.
    """

    return {
        "pipeline": PIPELINE_NAME,
        "week_start": week_start.isoformat(),
        "loaded_records": loaded_records,
    }


@task(
    name="complete_pipeline_run_log",
    retries=2,
    retry_delay_seconds=5,
)
def complete_pipeline_run_log(
    run_id: str,
    extraction: dict[str, Any],
    transformed: dict[str, Any],
    loaded_records: int,
) -> None:
    """
    Two retries cover brief failures when recording final audit metadata.
    """

    with Session(engine) as session:
        run = session.get(PipelineRun, UUID(run_id))

        if run is None:
            raise RuntimeError("Pipeline run log was not found")

        highest_timestamp = extraction[
            "highest_event_timestamp"
        ]

        run.status = "Completed"
        run.ended_at = utc_now()
        run.extracted_records = extraction[
            "extracted_records"
        ]
        run.processed_records = transformed[
            "processed_records"
        ]
        run.loaded_records = loaded_records
        run.rejected_records = transformed[
            "rejected_records"
        ]
        run.duplicate_records = transformed[
            "duplicate_records"
        ]
        run.highest_event_timestamp = highest_timestamp
        run.checkpoint_value = (
            highest_timestamp.isoformat()
            if highest_timestamp is not None
            else None
        )
        run.error_message = None

        session.add(run)
        session.commit()


@task(
    name="fail_pipeline_run_log",
    retries=2,
    retry_delay_seconds=5,
)
def fail_pipeline_run_log(
    run_id: str,
    error_message: str,
) -> None:
    """
    Two retries give the audit log a second chance during transient
    database interruptions.
    """

    with Session(engine) as session:
        run = session.get(PipelineRun, UUID(run_id))

        if run is None:
            return

        run.status = "Failed"
        run.ended_at = utc_now()
        run.error_message = error_message[:4000]

        session.add(run)
        session.commit()


@flow(name="extract_weekly_warehouse_client_events_flow")
def extract_weekly_warehouse_client_events_flow(
    interval_start: datetime,
    interval_end: datetime,
) -> dict[str, Any]:
    """Extract TrackFlow business events for one completed ISO week."""

    return extract_weekly_business_events(
        interval_start,
        interval_end,
    )


@flow(name="transform_weekly_warehouse_client_performance_flow")
def transform_weekly_warehouse_client_performance_flow(
    extraction: dict[str, Any],
    week_start: date,
) -> dict[str, Any]:
    """
    Validate, deduplicate, aggregate, and verify the four TrackFlow KPIs.
    """

    transformed = deduplicate_and_validate_events(
        extraction
    )

    aggregated = aggregate_weekly_warehouse_client_metrics(
        transformed,
        week_start,
    )

    validated = validate_weekly_metrics(aggregated)

    return {
        "transformed": transformed,
        "performance_rows": validated,
    }


@flow(name="load_weekly_warehouse_client_performance_flow")
def load_weekly_warehouse_client_performance_flow(
    performance_rows: list[dict[str, Any]],
) -> int:
    """
    Upsert weekly warehouse/client KPI rows into the reporting schema.
    """

    return upsert_weekly_performance_rows(
        performance_rows
    )


@flow(name="weekly_warehouse_client_performance_flow")
def weekly_warehouse_client_performance_flow(
    week_start: date | str | None = None,
    trigger_type: str = "scheduled",
) -> dict[str, Any]:
    """
    Produce the Weekly Warehouse & Client Performance Report.

    The main flow coordinates the TrackFlow extraction, transformation,
    and load subflows while maintaining the pipeline execution audit log.
    """

    logger = get_run_logger()

    resolved_week_start = resolve_week_start(week_start)
    interval_start, interval_end = build_week_interval(
        resolved_week_start
    )

    run_id = create_pipeline_run_log(
        resolved_week_start,
        trigger_type,
        interval_start,
        interval_end,
    )

    try:
        extraction = extract_weekly_warehouse_client_events_flow(
            interval_start,
            interval_end,
        )

        transformation = (
            transform_weekly_warehouse_client_performance_flow(
                extraction,
                resolved_week_start,
            )
        )

        transformed = transformation["transformed"]
        performance_rows = transformation["performance_rows"]

        loaded_records = (
            load_weekly_warehouse_client_performance_flow(
                performance_rows
            )
        )

        optional_state: State = optional_pipeline_summary(
            resolved_week_start,
            loaded_records,
            return_state=True,
        )

        if optional_state.is_failed():
            logger.warning(
                "Optional pipeline summary failed; "
                "main execution will continue."
            )

        complete_pipeline_run_log(
            run_id,
            extraction,
            transformed,
            loaded_records,
        )

        return {
            "pipeline": PIPELINE_NAME,
            "status": "Completed",
            "week_start": resolved_week_start.isoformat(),
            "run_id": run_id,
            "extracted_records": extraction[
                "extracted_records"
            ],
            "processed_records": transformed[
                "processed_records"
            ],
            "loaded_records": loaded_records,
            "rejected_records": transformed[
                "rejected_records"
            ],
            "duplicate_records": transformed[
                "duplicate_records"
            ],
        }

    except Exception as error:
        fail_state: State = fail_pipeline_run_log(
            run_id,
            str(error),
            return_state=True,
        )

        if fail_state.is_failed():
            logger.error(
                "Failed to update pipeline run log: %s",
                fail_state.message,
            )

        raise


@flow(name="recompute_weekly_performance_flow")
def recompute_weekly_performance_flow(
    week_start: date | str,
) -> dict[str, Any]:
    """Manually recompute a specific TrackFlow ISO week."""

    return weekly_warehouse_client_performance_flow(
        week_start=week_start,
        trigger_type="manual",
    )


def get_weekly_warehouse_client_performance(
    week_start: date | None = None,
) -> dict[str, Any]:
    with Session(engine) as session:
        resolved_week = week_start

        if resolved_week is None:
            latest_statement = select(
                WeeklyWarehouseClientPerformance.week_start
            ).order_by(
                WeeklyWarehouseClientPerformance.week_start.desc()
            )

            resolved_week = session.exec(
                latest_statement
            ).first()

        if resolved_week is None:
            return {
                "week_start": None,
                "entries": [],
            }

        statement = (
            select(WeeklyWarehouseClientPerformance)
            .where(
                WeeklyWarehouseClientPerformance.week_start
                == resolved_week
            )
            .order_by(
                WeeklyWarehouseClientPerformance.warehouse,
                WeeklyWarehouseClientPerformance.client_id,
            )
        )

        records = session.exec(statement).all()

    return {
        "week_start": resolved_week.isoformat(),
        "entries": [
            {
                "warehouse": record.warehouse,
                "client_id": record.client_id,
                "inbound_units_count": record.inbound_units_count,
                "outbound_orders_count": record.outbound_orders_count,
                "stockout_events_count": record.stockout_events_count,
                "discrepancy_events_count": record.discrepancy_events_count,
                "discrepancy_rate": float(
                    record.discrepancy_rate
                ),
            }
            for record in records
        ],
    }


def get_latest_pipeline_run() -> dict[str, Any] | None:
    statement = (
        select(PipelineRun)
        .where(PipelineRun.pipeline_name == PIPELINE_NAME)
        .order_by(PipelineRun.started_at.desc())
    )

    with Session(engine) as session:
        record = session.exec(statement).first()

    if record is None:
        return None

    return {
        "id": str(record.id),
        "pipeline_name": record.pipeline_name,
        "target_week_start": (
            record.target_week_start.isoformat()
            if record.target_week_start
            else None
        ),
        "trigger_type": record.trigger_type,
        "status": record.status,
        "started_at": record.started_at.isoformat(),
        "ended_at": (
            record.ended_at.isoformat()
            if record.ended_at
            else None
        ),
        "extracted_records": record.extracted_records,
        "processed_records": record.processed_records,
        "loaded_records": record.loaded_records,
        "rejected_records": record.rejected_records,
        "duplicate_records": record.duplicate_records,
        "source_interval_start": (
            record.source_interval_start.isoformat()
            if record.source_interval_start
            else None
        ),
        "source_interval_end": (
            record.source_interval_end.isoformat()
            if record.source_interval_end
            else None
        ),
        "highest_event_timestamp": (
            record.highest_event_timestamp.isoformat()
            if record.highest_event_timestamp
            else None
        ),
        "checkpoint_value": record.checkpoint_value,
        "error_message": record.error_message,
        "prefect_flow_run_id": record.prefect_flow_run_id,
    }


def trigger_weekly_performance_run(
    week_start: date | str,
) -> dict[str, Any]:
    resolved_week = resolve_week_start(week_start)

    running_statement = (
        select(PipelineRun)
        .where(PipelineRun.pipeline_name == PIPELINE_NAME)
        .where(PipelineRun.target_week_start == resolved_week)
        .where(PipelineRun.status == "Running")
    )

    with Session(engine) as session:
        existing_run = session.exec(
            running_statement
        ).first()

    if existing_run is not None:
        raise RuntimeError(
            "A pipeline run is already active for this week"
        )

    result = recompute_weekly_performance_flow(
        resolved_week
    )

    return {
        "status": "accepted",
        "week_start": resolved_week.isoformat(),
        "pipeline": PIPELINE_NAME,
        "run_id": result["run_id"],
    }


if __name__ == "__main__":
    weekly_warehouse_client_performance_flow()