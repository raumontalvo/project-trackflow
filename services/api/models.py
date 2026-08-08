from datetime import date, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from sqlalchemy import Column, JSON, UniqueConstraint
from sqlmodel import Field as SQLField
from sqlmodel import Relationship, SQLModel


# ---------------------------------------------------------------------------
# Existing supplier models
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Existing incident models
# ---------------------------------------------------------------------------

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

    status: Literal[
        "open",
        "in_progress",
        "resolved",
        "discarded",
    ]

    origin: Literal[
        "customer",
        "branch",
        "internal",
    ]

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
    status: Literal[
        "open",
        "in_progress",
        "resolved",
        "discarded",
    ]


# ---------------------------------------------------------------------------
# Existing inventory SQLModel tables
# ---------------------------------------------------------------------------

class SKU(SQLModel, table=True):
    id: int | None = SQLField(default=None, primary_key=True)
    name: str
    sku: str
    client_name: str
    category: str
    warehouse: str

    stock_entries: list["StockEntry"] = Relationship(
        back_populates="sku_item"
    )
    stock_exits: list["StockExit"] = Relationship(
        back_populates="sku_item"
    )


class StockEntry(SQLModel, table=True):
    id: int | None = SQLField(default=None, primary_key=True)
    sku_id: int = SQLField(foreign_key="sku.id")
    quantity: int
    reference: str
    warehouse: str
    created_at: datetime = SQLField(default_factory=datetime.utcnow)
    user_uuid: str

    sku_item: SKU | None = Relationship(
        back_populates="stock_entries"
    )


class StockExit(SQLModel, table=True):
    id: int | None = SQLField(default=None, primary_key=True)
    sku_id: int = SQLField(foreign_key="sku.id")
    quantity: int
    exit_type: str
    tracking_number: str | None = None
    warehouse: str
    created_at: datetime = SQLField(default_factory=datetime.utcnow)
    user_uuid: str

    sku_item: SKU | None = Relationship(
        back_populates="stock_exits"
    )


# ---------------------------------------------------------------------------
# Milestone 9 Part 1 — RFP intake SQLModel tables
# ---------------------------------------------------------------------------

class RFP(SQLModel, table=True):
    """
    Persisted metadata for a valid TrackFlow RFP.

    Business metadata should only be trusted after the document has been
    classified as a legitimate TrackFlow RFP.
    """

    __tablename__ = "rfps"

    rfp_id: str = SQLField(
        default_factory=lambda: str(uuid4()),
        primary_key=True,
    )

    client_name: str | None = None
    client_country: str | None = None

    services_requested: list[str] = SQLField(
        default_factory=list,
        sa_column=Column(JSON),
    )

    monthly_volume: int | None = None
    deadline: date | None = None
    budget_range: str | None = None

    departments_needed: list[str] = SQLField(
        default_factory=list,
        sa_column=Column(JSON),
    )

    readability_metrics: dict = SQLField(
        default_factory=dict,
        sa_column=Column(JSON),
    )

    intake_summary: dict = SQLField(
        default_factory=dict,
        sa_column=Column(JSON),
    )

    created_at: datetime = SQLField(default_factory=datetime.utcnow)
    updated_at: datetime = SQLField(default_factory=datetime.utcnow)


class Ticket(SQLModel, table=True):
    """
    Lifecycle record for an uploaded RFP document.

    Part 1 statuses:
    - analyzing
    - discarded
    - intake_complete

    The same ticket will later continue through Parts 2 and 3.
    """

    __tablename__ = "rfp_tickets"

    ticket_id: str = SQLField(
        default_factory=lambda: str(uuid4()),
        primary_key=True,
    )

    rfp_id: str | None = SQLField(
        default=None,
        foreign_key="rfps.rfp_id",
    )

    status: str = SQLField(
        default="analyzing",
        index=True,
    )

    raw_pdf_path: str
    error_message: str | None = None

    created_at: datetime = SQLField(default_factory=datetime.utcnow)
    updated_at: datetime = SQLField(default_factory=datetime.utcnow)


class DepartmentSection(SQLModel, table=True):
    """
    Per-department RFP analysis.

    Part 1 persists key_aspects.
    Fields for Parts 2 and 3 are included so the same entity can continue
    through proposal generation, evaluation, and approval.
    """

    __tablename__ = "rfp_department_sections"

    __table_args__ = (
        UniqueConstraint(
            "rfp_id",
            "department_id",
            name="uq_rfp_department",
        ),
    )

    id: str = SQLField(
        default_factory=lambda: str(uuid4()),
        primary_key=True,
    )

    rfp_id: str = SQLField(
        foreign_key="rfps.rfp_id",
        index=True,
    )

    department_id: str = SQLField(index=True)
    owner: str

    key_aspects: dict = SQLField(
        default_factory=dict,
        sa_column=Column(JSON),
    )

    # Part 2
    draft_content: str | None = None

    evaluation_results: dict | None = SQLField(
        default=None,
        sa_column=Column(JSON),
    )

    # Part 3
    approval_status: str | None = None
    approver: str | None = None
    approved_at: datetime | None = None

    created_at: datetime = SQLField(default_factory=datetime.utcnow)
    updated_at: datetime = SQLField(default_factory=datetime.utcnow)