from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field as SQLField
from sqlmodel import Relationship, SQLModel


VALID_CATEGORIES = [
    "carrier_last_mile",
    "carrier_international",
    "warehouse_supplies",
    "packaging_materials",
    "reverse_logistics",
    "fleet_maintenance",
    "it_and_wms_software",
    "cleaning_and_facilities",
]


class SupplierBase(BaseModel):
    name: str = Field(..., min_length=1)
    country: Literal["USA", "Spain"]
    categories: list[str] = Field(..., min_length=1)
    rate_per_shipment: float = Field(..., gt=0)
    currency: Literal["USD", "EUR"]
    status: Literal["active", "suspended"]
    service_zone: str | None = None
    contact_email: EmailStr | None = None
    notes: str | None = None

    @field_validator("categories")
    @classmethod
    def validate_categories(cls, categories: list[str]) -> list[str]:
        for category in categories:
            if category not in VALID_CATEGORIES:
                raise ValueError(f"Invalid category: {category}")
        return categories

    @model_validator(mode="after")
    def validate_currency_by_country(self):
        if self.country == "USA" and self.currency != "USD":
            raise ValueError("USA suppliers must use USD currency")
        if self.country == "Spain" and self.currency != "EUR":
            raise ValueError("Spain suppliers must use EUR currency")
        return self


class SupplierCreate(SupplierBase):
    pass


class Supplier(SupplierBase):
    id: int
    rate_updated_at: datetime


class RateUpdate(BaseModel):
    rate_per_shipment: float = Field(..., gt=0)


class StatusUpdate(BaseModel):
    status: Literal["active", "suspended"]


class IncidentBase(BaseModel):
    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    category: Literal[
        "lost_parcel",
        "delivery_failure",
        "inventory_discrepancy",
        "carrier_issue",
        "returns_issue",
        "warehouse_incident",
        "system_failure",
        "client_complaint",
        "other",
    ]
    status: Literal["open", "in_progress", "resolved", "discarded"]
    origin: Literal["customer", "branch", "internal"]
    branch: Literal[
        "central",
        "la_warehouse",
        "la_office",
        "zaragoza_warehouse",
        "zaragoza_office",
    ]


class IncidentCreate(IncidentBase):
    pass


class Incident(IncidentBase):
    id: int
    created_at: datetime
    updated_at: datetime


class IncidentStatusUpdate(BaseModel):
    status: Literal["open", "in_progress", "resolved", "discarded"]


class SKU(SQLModel, table=True):
    id: int | None = SQLField(default=None, primary_key=True)
    name: str
    sku: str
    client_name: str
    category: str
    warehouse: str

    stock_entries: list["StockEntry"] = Relationship(back_populates="sku_item")
    stock_exits: list["StockExit"] = Relationship(back_populates="sku_item")


class StockEntry(SQLModel, table=True):
    id: int | None = SQLField(default=None, primary_key=True)
    sku_id: int = SQLField(foreign_key="sku.id")
    quantity: int
    reference: str
    warehouse: str
    created_at: datetime = SQLField(default_factory=datetime.utcnow)
    user_uuid: str

    sku_item: SKU | None = Relationship(back_populates="stock_entries")


class StockExit(SQLModel, table=True):
    id: int | None = SQLField(default=None, primary_key=True)
    sku_id: int = SQLField(foreign_key="sku.id")
    quantity: int
    exit_type: str
    tracking_number: str | None = None
    warehouse: str
    created_at: datetime = SQLField(default_factory=datetime.utcnow)
    user_uuid: str

    sku_item: SKU | None = Relationship(back_populates="stock_exits")


class TelemetryEventRecord(SQLModel, table=True):
    __tablename__ = "telemetry_events"

    event_id: str = SQLField(primary_key=True)

    timestamp: datetime = SQLField(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
        )
    )

    session_id: str
    user_id: str
    event_type: str
    schema_version: str
    request_id: str

    tags: dict[str, Any] = SQLField(
        sa_column=Column(
            JSONB,
            nullable=False,
        )
    )

    __table_args__ = (
        Index(
            "ix_telemetry_events_timestamp",
            "timestamp",
        ),
        Index(
            "ix_telemetry_events_event_type",
            "event_type",
        ),
        Index(
            "ix_telemetry_events_tags_gin",
            "tags",
            postgresql_using="gin",
        ),
    )


class WeeklyWarehouseClientPerformance(SQLModel, table=True):
    __tablename__ = "weekly_warehouse_client_performance"
    __table_args__ = (
        UniqueConstraint(
            "warehouse",
            "client_id",
            "week_start",
            name="uq_weekly_warehouse_client_performance",
        ),
        {"schema": "reporting"},
    )

    id: UUID = SQLField(default_factory=uuid4, primary_key=True)
    warehouse: str
    client_id: str
    week_start: date = SQLField(
        sa_column=Column(Date, nullable=False)
    )
    inbound_units_count: int = SQLField(default=0)
    outbound_orders_count: int = SQLField(default=0)
    stockout_events_count: int = SQLField(default=0)
    discrepancy_events_count: int = SQLField(default=0)
    discrepancy_rate: Decimal = SQLField(
        default=Decimal("0"),
        sa_column=Column(Numeric, nullable=False),
    )
    computed_at: datetime = SQLField(
        default_factory=datetime.utcnow,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
        ),
    )


class PipelineRun(SQLModel, table=True):
    __tablename__ = "pipeline_runs"
    __table_args__ = {"schema": "reporting"}

    id: UUID = SQLField(default_factory=uuid4, primary_key=True)
    pipeline_name: str
    target_week_start: date | None = SQLField(
        default=None,
        sa_column=Column(Date, nullable=True),
    )
    trigger_type: str
    status: str
    started_at: datetime = SQLField(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
        )
    )
    ended_at: datetime | None = SQLField(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=True,
        ),
    )
    extracted_records: int = SQLField(default=0)
    processed_records: int = SQLField(default=0)
    loaded_records: int = SQLField(default=0)
    rejected_records: int = SQLField(default=0)
    duplicate_records: int = SQLField(default=0)
    source_interval_start: datetime | None = SQLField(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=True,
        ),
    )
    source_interval_end: datetime | None = SQLField(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=True,
        ),
    )
    highest_event_timestamp: datetime | None = SQLField(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=True,
        ),
    )
    checkpoint_value: str | None = SQLField(
        default=None,
        sa_column=Column(Text, nullable=True),
    )
    error_message: str | None = SQLField(
        default=None,
        sa_column=Column(Text, nullable=True),
    )
    prefect_flow_run_id: str | None = SQLField(
        default=None,
        sa_column=Column(Text, nullable=True),
    )
    created_at: datetime = SQLField(
        default_factory=datetime.utcnow,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
        ),
    )


class JobRun(SQLModel, table=True):
    """
    Records independent background orchestration executions.

    PipelineRun records the internal ETL lifecycle. JobRun records the
    nightly export, pipeline trigger, locking, and orchestration result.
    """

    __tablename__ = "job_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed')",
            name="ck_job_runs_status",
        ),
        Index(
            "ix_job_runs_job_name_target_date",
            "job_name",
            "target_date",
        ),
        Index(
            "uq_job_runs_single_processing_job",
            "job_name",
            unique=True,
            postgresql_where=text("status = 'processing'"),
        ),
        {"schema": "reporting"},
    )

    id: UUID = SQLField(default_factory=uuid4, primary_key=True)

    job_name: str = SQLField(
        sa_column=Column(
            String(100),
            nullable=False,
        )
    )

    target_date: date = SQLField(
        sa_column=Column(
            Date,
            nullable=False,
        )
    )

    status: str = SQLField(
        default="pending",
        sa_column=Column(
            String(20),
            nullable=False,
        ),
    )

    started_at: datetime | None = SQLField(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=True,
        ),
    )

    finished_at: datetime | None = SQLField(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            nullable=True,
        ),
    )

    error_message: str | None = SQLField(
        default=None,
        sa_column=Column(
            Text,
            nullable=True,
        ),
    )

    created_at: datetime = SQLField(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True),
            nullable=False,
        ),
    )

