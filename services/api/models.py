from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
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
