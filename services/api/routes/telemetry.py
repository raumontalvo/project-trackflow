import logging
import os
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import insert
from sqlmodel import Session

from services.api.database import get_db
from services.api.models import TelemetryEventRecord

logger = logging.getLogger(__name__)

TELEMETRY_ENDPOINT = os.getenv(
    "TELEMETRY_ENDPOINT",
    "/telemetry/events",
)

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


class TelemetryEvent(BaseModel):
    eventId: str
    timestamp: datetime
    sessionId: str
    userId: str
    event_type: str
    schemaVersion: str
    requestId: str
    properties: dict[str, Any] = Field(default_factory=dict)


class TelemetryBatchEnvelope(BaseModel):
    """
    The batch envelope is validated here, but each event stays unvalidated
    until the endpoint loops over it.

    This enables partial acceptance:
    one invalid event does not reject the entire batch.
    """

    events: list[Any]


TRACKFLOW_INVENTORY_EVENTS = {
    "inbound_order_created",
    "outbound_order_created",
    "stock_threshold_triggered",
    "direct_stock_edit_rejected",
    "inventory_discrepancy_detected",
}


EVENT_PROPERTY_ALLOWLISTS: dict[str, set[str]] = {
    # Authoritative TrackFlow inventory events
    "inbound_order_created": {
        "warehouse",
        "client_id",
        "product_id",
        "product_category",
        "quantity",
    },
    "outbound_order_created": {
        "warehouse",
        "client_id",
        "product_id",
        "product_category",
        "quantity",
    },
    "stock_threshold_triggered": {
        "warehouse",
        "client_id",
        "product_id",
        "product_category",
        "quantity",
        "current_stock",
        "min_stock_threshold",
        "triggering_outbound_order_id",
    },
    "direct_stock_edit_rejected": {
        "warehouse",
        "client_id",
        "product_id",
        "product_category",
        "quantity",
        "attempted_field",
        "rejection_reason",
        "created_by",
    },
    "inventory_discrepancy_detected": {
        "warehouse",
        "client_id",
        "product_id",
        "product_category",
        "quantity",
        "expected_quantity",
        "actual_quantity",
        "discrepancy_quantity",
        "created_by",
    },

    # Existing event names from the previous telemetry phase.
    # These remain accepted so the frontend does not need to change.
    "receiving_order_created": {
        "receiving_order_id",
        "sku_id",
        "sku_code",
        "warehouse",
        "client_id",
        "quantity",
        "created_by",
    },
    "dispatch_order_created": {
        "dispatch_order_id",
        "sku_id",
        "sku_code",
        "warehouse",
        "client_id",
        "destination_country",
        "quantity",
        "created_by",
    },
    "dispatch_order_failed": {
        "sku_id",
        "sku_code",
        "warehouse",
        "client_id",
        "destination_country",
        "quantity",
        "failure_reason",
        "created_by",
        "sla_sensitive",
    },
    "dispatch_form_abandoned": {
        "warehouse",
        "sku_id",
        "client_id",
        "abandoned_step",
        "time_on_form_seconds",
        "created_by",
    },
    "user_login_failed": {
        "failure_reason",
        "warehouse",
        "user_role",
        "attempt_count",
        "ip_hash",
    },
}


TRACKFLOW_REQUIRED_PROPERTIES = {
    "warehouse",
    "client_id",
    "product_id",
    "product_category",
    "quantity",
}


VALID_WAREHOUSES = {
    "los_angeles",
    "zaragoza",
}


VALID_PRODUCT_CATEGORIES = {
    "fashion",
    "electronics",
    "cosmetics",
}


FORBIDDEN_PROPERTY_KEYS = {
    "recipient_name",
    "recipient_email",
    "recipient_phone",
    "recipient_address",
    "delivery_address",
    "end_consumer_id",
}


def validate_trackflow_inventory_event(event: TelemetryEvent) -> None:
    """
    Validate the minimum TrackFlow dimensions for the five authoritative
    inventory event types without modifying the existing Pydantic model.
    """

    if event.event_type not in TRACKFLOW_INVENTORY_EVENTS:
        return

    missing = TRACKFLOW_REQUIRED_PROPERTIES - event.properties.keys()

    if missing:
        raise ValueError(
            f"Missing required properties: {sorted(missing)}"
        )

    warehouse = event.properties["warehouse"]

    if warehouse not in VALID_WAREHOUSES:
        raise ValueError(
            "warehouse must be 'los_angeles' or 'zaragoza'"
        )

    product_category = event.properties["product_category"]

    if product_category not in VALID_PRODUCT_CATEGORIES:
        raise ValueError(
            "product_category must be fashion, electronics, or cosmetics"
        )

    quantity = event.properties["quantity"]

    if (
        not isinstance(quantity, int)
        or isinstance(quantity, bool)
        or quantity < 0
    ):
        raise ValueError(
            "quantity must be a non-negative integer"
        )


def build_tags(event: TelemetryEvent) -> dict[str, Any]:
    """
    Copy only approved properties into the JSONB tags column.
    Arbitrary frontend properties are never persisted.
    """

    forbidden_found = (
        FORBIDDEN_PROPERTY_KEYS
        & event.properties.keys()
    )

    if forbidden_found:
        raise ValueError(
            f"Forbidden properties found: {sorted(forbidden_found)}"
        )

    allowed_keys = EVENT_PROPERTY_ALLOWLISTS.get(event.event_type)

    if allowed_keys is None:
        raise ValueError(
            f"Unsupported event_type: {event.event_type}"
        )

    return {
        key: value
        for key, value in event.properties.items()
        if key in allowed_keys
    }


def map_event_to_row(
    event: TelemetryEvent,
) -> dict[str, Any]:
    validate_trackflow_inventory_event(event)

    return {
        "event_id": event.eventId,
        "timestamp": event.timestamp,
        "session_id": event.sessionId,
        "user_id": event.userId,
        "event_type": event.event_type,
        "schema_version": event.schemaVersion,
        "request_id": event.requestId,
        "tags": build_tags(event),
    }


@router.post("/events")
def receive_telemetry(
    batch: TelemetryBatchEnvelope,
    db: Session = Depends(get_db),
) -> dict[str, int]:
    logger.info(
        "Configured telemetry endpoint: %s",
        TELEMETRY_ENDPOINT,
    )

    received = len(batch.events)
    rejected = 0
    rows: list[dict[str, Any]] = []

    for index, raw_event in enumerate(batch.events):
        try:
            event = TelemetryEvent.model_validate(raw_event)
            row = map_event_to_row(event)
            rows.append(row)

        except (ValidationError, TypeError, ValueError) as error:
            rejected += 1

            logger.warning(
                "Rejected telemetry event at batch index %s: %s",
                index,
                error,
            )

    stored = 0

    if rows:
        try:
            statement = insert(
                TelemetryEventRecord.__table__
            )

            # One INSERT statement for every valid event in the batch.
            db.execute(statement, rows)
            db.commit()

            stored = len(rows)

        except Exception as error:
            db.rollback()

            logger.exception(
                "Telemetry bulk insert failed"
            )

            raise HTTPException(
                status_code=500,
                detail="Telemetry events could not be stored",
            ) from error

    logger.info(
        "Telemetry batch processed: received=%s stored=%s rejected=%s",
        received,
        stored,
        rejected,
    )

    return {
        "received": received,
        "stored": stored,
        "rejected": rejected,
    }