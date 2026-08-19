from datetime import date, datetime, timezone
from decimal import Decimal

from data.pipelines.pipeline import (
    aggregate_weekly_warehouse_client_metrics,
    deduplicate_and_validate_events,
)


TARGET_WEEK = date(2026, 7, 13)


def run_task(task, *args):
    """
    Execute the underlying Python function without requiring
    a Prefect flow or external infrastructure.
    """
    return task.fn(*args)


def test_inbound_volume_sums_quantities_for_warehouse_and_client():
    extraction = {
        "events": [
            {
                "event_id": "inbound-1",
                "timestamp": datetime(
                    2026,
                    7,
                    14,
                    10,
                    0,
                    tzinfo=timezone.utc,
                ),
                "event_type": "inbound_order_created",
                "tags": {
                    "warehouse": "los_angeles",
                    "client_id": "fashion-co",
                    "quantity": 100,
                },
            },
            {
                "event_id": "inbound-2",
                "timestamp": datetime(
                    2026,
                    7,
                    15,
                    11,
                    0,
                    tzinfo=timezone.utc,
                ),
                "event_type": "inbound_order_created",
                "tags": {
                    "warehouse": "los_angeles",
                    "client_id": "fashion-co",
                    "quantity": 250,
                },
            },
        ],
        "extracted_records": 2,
        "highest_event_timestamp": None,
    }

    transformed = run_task(
        deduplicate_and_validate_events,
        extraction,
    )

    rows = run_task(
        aggregate_weekly_warehouse_client_metrics,
        transformed,
        TARGET_WEEK,
    )

    assert len(rows) == 1
    assert rows[0]["inbound_units_count"] == 350


def test_outbound_throughput_counts_orders():
    extraction = {
        "events": [
            {
                "event_id": f"outbound-{index}",
                "timestamp": datetime(
                    2026,
                    7,
                    16,
                    9,
                    index,
                    tzinfo=timezone.utc,
                ),
                "event_type": "outbound_order_created",
                "tags": {
                    "warehouse": "zaragoza",
                    "client_id": "electronics-co",
                },
            }
            for index in range(4)
        ],
        "extracted_records": 4,
        "highest_event_timestamp": None,
    }

    transformed = run_task(
        deduplicate_and_validate_events,
        extraction,
    )

    rows = run_task(
        aggregate_weekly_warehouse_client_metrics,
        transformed,
        TARGET_WEEK,
    )

    assert len(rows) == 1
    assert rows[0]["outbound_orders_count"] == 4


def test_stockout_frequency_counts_threshold_events():
    extraction = {
        "events": [
            {
                "event_id": f"stockout-{index}",
                "timestamp": datetime(
                    2026,
                    7,
                    17,
                    12,
                    index,
                    tzinfo=timezone.utc,
                ),
                "event_type": "stock_threshold_triggered",
                "tags": {
                    "warehouse": "los_angeles",
                    "client_id": "cosmetics-co",
                },
            }
            for index in range(3)
        ],
        "extracted_records": 3,
        "highest_event_timestamp": None,
    }

    transformed = run_task(
        deduplicate_and_validate_events,
        extraction,
    )

    rows = run_task(
        aggregate_weekly_warehouse_client_metrics,
        transformed,
        TARGET_WEEK,
    )

    assert len(rows) == 1
    assert rows[0]["stockout_events_count"] == 3


def test_discrepancy_rate_matches_hand_calculated_result():
    events = []

    for index in range(8):
        events.append(
            {
                "event_id": f"outbound-{index}",
                "timestamp": datetime(
                    2026,
                    7,
                    18,
                    8,
                    index,
                    tzinfo=timezone.utc,
                ),
                "event_type": "outbound_order_created",
                "tags": {
                    "warehouse": "los_angeles",
                    "client_id": "fashion-co",
                },
            }
        )

    for index in range(2):
        events.append(
            {
                "event_id": f"discrepancy-{index}",
                "timestamp": datetime(
                    2026,
                    7,
                    18,
                    10,
                    index,
                    tzinfo=timezone.utc,
                ),
                "event_type": "inventory_discrepancy_detected",
                "tags": {
                    "warehouse": "los_angeles",
                    "client_id": "fashion-co",
                },
            }
        )

    extraction = {
        "events": events,
        "extracted_records": len(events),
        "highest_event_timestamp": None,
    }

    transformed = run_task(
        deduplicate_and_validate_events,
        extraction,
    )

    rows = run_task(
        aggregate_weekly_warehouse_client_metrics,
        transformed,
        TARGET_WEEK,
    )

    assert len(rows) == 1
    assert rows[0]["discrepancy_events_count"] == 2
    assert rows[0]["outbound_orders_count"] == 8
    assert rows[0]["discrepancy_rate"] == Decimal("0.25")


def test_discrepancy_rate_is_zero_when_no_outbound_orders_exist():
    extraction = {
        "events": [
            {
                "event_id": "discrepancy-only",
                "timestamp": datetime(
                    2026,
                    7,
                    18,
                    10,
                    0,
                    tzinfo=timezone.utc,
                ),
                "event_type": "inventory_discrepancy_detected",
                "tags": {
                    "warehouse": "zaragoza",
                    "client_id": "fashion-co",
                },
            }
        ],
        "extracted_records": 1,
        "highest_event_timestamp": None,
    }

    transformed = run_task(
        deduplicate_and_validate_events,
        extraction,
    )

    rows = run_task(
        aggregate_weekly_warehouse_client_metrics,
        transformed,
        TARGET_WEEK,
    )

    assert rows[0]["discrepancy_rate"] == Decimal("0")


def test_invalid_inbound_quantity_is_rejected():
    extraction = {
        "events": [
            {
                "event_id": "invalid-inbound",
                "timestamp": datetime(
                    2026,
                    7,
                    14,
                    10,
                    0,
                    tzinfo=timezone.utc,
                ),
                "event_type": "inbound_order_created",
                "tags": {
                    "warehouse": "los_angeles",
                    "client_id": "fashion-co",
                    "quantity": "100",
                },
            }
        ],
        "extracted_records": 1,
        "highest_event_timestamp": None,
    }

    transformed = run_task(
        deduplicate_and_validate_events,
        extraction,
    )

    assert transformed["processed_records"] == 0
    assert transformed["rejected_records"] == 1
    assert transformed["events"] == []


def test_duplicate_event_ids_are_deduplicated():
    extraction = {
        "events": [
            {
                "event_id": "same-event",
                "timestamp": datetime(
                    2026,
                    7,
                    14,
                    10,
                    0,
                    tzinfo=timezone.utc,
                ),
                "event_type": "outbound_order_created",
                "tags": {
                    "warehouse": "los_angeles",
                    "client_id": "fashion-co",
                },
            },
            {
                "event_id": "same-event",
                "timestamp": datetime(
                    2026,
                    7,
                    14,
                    11,
                    0,
                    tzinfo=timezone.utc,
                ),
                "event_type": "outbound_order_created",
                "tags": {
                    "warehouse": "los_angeles",
                    "client_id": "fashion-co",
                },
            },
        ],
        "extracted_records": 2,
        "highest_event_timestamp": None,
    }

    transformed = run_task(
        deduplicate_and_validate_events,
        extraction,
    )

    assert transformed["processed_records"] == 1
    assert transformed["duplicate_records"] == 1
