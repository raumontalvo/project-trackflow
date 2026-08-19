from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


Warehouse = Literal["LA", "ZGZ"]
Category = Literal["fashion", "electronics", "cosmetics"]
ExitType = Literal["dispatch", "loss"]


class SKUCreate(BaseModel):
    name: str = Field(..., min_length=1)
    sku: str = Field(..., min_length=1)
    client_name: str = Field(..., min_length=1)
    category: Category
    warehouse: Warehouse


class SKUResponse(SKUCreate):
    id: int
    current_stock: int


class StockEntryCreate(BaseModel):
    sku_id: int
    quantity: int = Field(..., gt=0)
    reference: str = Field(..., min_length=1)
    warehouse: Warehouse


class StockEntryResponse(StockEntryCreate):
    id: int
    created_at: datetime
    user_uuid: str


class StockExitCreate(BaseModel):
    sku_id: int
    quantity: int = Field(..., gt=0)
    exit_type: ExitType
    tracking_number: str | None = None
    warehouse: Warehouse

    @model_validator(mode="after")
    def validate_tracking_number(self):
        if self.exit_type == "dispatch" and not self.tracking_number:
            raise ValueError("tracking_number is required when exit_type is dispatch")
        if self.exit_type == "loss" and self.tracking_number is not None:
            raise ValueError("tracking_number must be null when exit_type is loss")
        return self


class StockExitResponse(StockExitCreate):
    id: int
    created_at: datetime
    user_uuid: str


class StockMovementResponse(BaseModel):
    id: int
    movement_type: Literal["entry", "exit"]
    sku_id: int
    sku: str
    sku_name: str
    quantity: int
    warehouse: Warehouse
    created_at: datetime
    user_uuid: str
    reference: str | None = None
    exit_type: str | None = None
    tracking_number: str | None = None
