from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class WeeklyPerformanceEntry(BaseModel):
    warehouse: str
    client_id: str
    inbound_units_count: int
    outbound_orders_count: int
    stockout_events_count: int
    discrepancy_events_count: int
    discrepancy_rate: float


class WeeklyPerformanceResponse(BaseModel):
    week_start: str | None
    entries: list[WeeklyPerformanceEntry]


class PipelineRunResponse(BaseModel):
    id: str
    pipeline_name: str
    target_week_start: str | None
    trigger_type: str
    status: str
    started_at: str
    ended_at: str | None
    extracted_records: int
    processed_records: int
    loaded_records: int
    rejected_records: int
    duplicate_records: int
    source_interval_start: str | None
    source_interval_end: str | None
    highest_event_timestamp: str | None
    checkpoint_value: str | None
    error_message: str | None
    prefect_flow_run_id: str | None


class ManualPipelineRunRequest(BaseModel):
    week_start: date = Field(
        ...,
        description="ISO week start date. Must be a Monday.",
    )


class ManualPipelineRunResponse(BaseModel):
    status: Literal["accepted"]
    week_start: str
    pipeline: str
    run_id: str