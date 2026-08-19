from datetime import datetime
from typing import Any

import pandas as pd
from sqlmodel import Session, select

from services.api.models import TelemetryEventRecord


TECHNICAL_FAILURE_EVENT_TYPES = (
    "direct_stock_edit_rejected",
    "dispatch_order_failed",
    "user_login_failed",
)


def events_per_day(
    db: Session,
    start_date: datetime,
    end_date: datetime,
) -> list[dict[str, Any]]:
    """
    Return the number of telemetry events produced per day.

    Operational question:
    How much telemetry activity did the system produce each day?
    """

    statement = (
        select(TelemetryEventRecord.timestamp)
        .where(TelemetryEventRecord.timestamp >= start_date)
        .where(TelemetryEventRecord.timestamp < end_date)
    )

    rows = db.exec(statement).all()

    if not rows:
        return []

    dataframe = pd.DataFrame(
        {
            "timestamp": rows,
        }
    )

    dataframe["timestamp"] = pd.to_datetime(
        dataframe["timestamp"],
        utc=True,
    )

    dataframe["date"] = dataframe["timestamp"].dt.date

    result = (
        dataframe.groupby("date")
        .agg(
            event_count=("timestamp", "count"),
        )
        .reset_index()
        .sort_values("date")
    )

    result["date"] = result["date"].astype(str)
    result["event_count"] = result["event_count"].astype(int)

    return result.to_dict(orient="records")


def events_by_type_per_day(
    db: Session,
    start_date: datetime,
    end_date: datetime,
) -> list[dict[str, Any]]:
    """
    Return telemetry event volume grouped by date and event type.

    Operational question:
    Which event types dominate system activity each day?
    """

    statement = (
        select(
            TelemetryEventRecord.timestamp,
            TelemetryEventRecord.event_type,
        )
        .where(TelemetryEventRecord.timestamp >= start_date)
        .where(TelemetryEventRecord.timestamp < end_date)
    )

    rows = db.exec(statement).all()

    if not rows:
        return []

    dataframe = pd.DataFrame(
        rows,
        columns=[
            "timestamp",
            "event_type",
        ],
    )

    dataframe["timestamp"] = pd.to_datetime(
        dataframe["timestamp"],
        utc=True,
    )

    dataframe["date"] = dataframe["timestamp"].dt.date

    result = (
        dataframe.groupby(
            [
                "date",
                "event_type",
            ]
        )
        .agg(
            event_count=("event_type", "count"),
        )
        .reset_index()
        .sort_values(
            [
                "date",
                "event_type",
            ]
        )
    )

    result["date"] = result["date"].astype(str)
    result["event_count"] = result["event_count"].astype(int)

    return result.to_dict(orient="records")


def technical_failures_per_day(
    db: Session,
    start_date: datetime,
    end_date: datetime,
) -> list[dict[str, Any]]:
    """
    Return technical failure events grouped by date and event type.

    Operational question:
    Which technical failures occurred and when did they happen?
    """

    statement = (
        select(
            TelemetryEventRecord.timestamp,
            TelemetryEventRecord.event_type,
        )
        .where(TelemetryEventRecord.timestamp >= start_date)
        .where(TelemetryEventRecord.timestamp < end_date)
        .where(
            TelemetryEventRecord.event_type.in_(
                TECHNICAL_FAILURE_EVENT_TYPES
            )
        )
    )

    rows = db.exec(statement).all()

    if not rows:
        return []

    dataframe = pd.DataFrame(
        rows,
        columns=[
            "timestamp",
            "event_type",
        ],
    )

    dataframe["timestamp"] = pd.to_datetime(
        dataframe["timestamp"],
        utc=True,
    )

    dataframe["date"] = dataframe["timestamp"].dt.date

    result = (
        dataframe.groupby(
            [
                "date",
                "event_type",
            ]
        )
        .agg(
            failure_count=("event_type", "count"),
        )
        .reset_index()
        .sort_values(
            [
                "date",
                "event_type",
            ]
        )
    )

    result["date"] = result["date"].astype(str)
    result["failure_count"] = result["failure_count"].astype(int)

    return result.to_dict(orient="records")


def generate_technical_report(
    db: Session,
    start_date: datetime,
    end_date: datetime,
) -> dict[str, Any]:
    """
    Run all independent metric functions using the same resolved period.
    """

    return {
        "period": {
            "from": start_date.isoformat(),
            "to": end_date.isoformat(),
        },
        "metrics": {
            "events_per_day": events_per_day(
                db,
                start_date,
                end_date,
            ),
            "events_by_type_per_day": events_by_type_per_day(
                db,
                start_date,
                end_date,
            ),
            "technical_failures_per_day": technical_failures_per_day(
                db,
                start_date,
                end_date,
            ),
        },
    }