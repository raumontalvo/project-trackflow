from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


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
