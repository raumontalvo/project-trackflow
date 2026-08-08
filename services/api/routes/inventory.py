from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, func, select

from services.api.auth import get_current_user
from services.api.database import get_db
from services.api.models import SKU, StockEntry, StockExit
from services.api.schemas import (
    SKUCreate,
    SKUResponse,
    StockEntryCreate,
    StockEntryResponse,
    StockExitCreate,
    StockExitResponse,
    StockMovementResponse,
)

router = APIRouter(prefix="/inventory", tags=["inventory"])


def get_user_uuid(user: dict) -> str:
    return str(user.get("uuid") or user.get("user_uuid") or user.get("id"))


def compute_current_stock(db: Session, sku_id: int, warehouse: str) -> int:
    inbound = db.exec(
        select(func.coalesce(func.sum(StockEntry.quantity), 0)).where(
            StockEntry.sku_id == sku_id,
            StockEntry.warehouse == warehouse,
        )
    ).one()

    outbound = db.exec(
        select(func.coalesce(func.sum(StockExit.quantity), 0)).where(
            StockExit.sku_id == sku_id,
            StockExit.warehouse == warehouse,
        )
    ).one()

    return int(inbound) - int(outbound)


def to_sku_response(db: Session, sku: SKU) -> SKUResponse:
    return SKUResponse(
        id=sku.id,
        name=sku.name,
        sku=sku.sku,
        client_name=sku.client_name,
        category=sku.category,
        warehouse=sku.warehouse,
        current_stock=compute_current_stock(db, sku.id, sku.warehouse),
    )


@router.get("/products", response_model=list[SKUResponse])
def list_products(db: Session = Depends(get_db)):
    skus = db.exec(select(SKU)).all()
    return [to_sku_response(db, sku) for sku in skus]


@router.post("/products", response_model=SKUResponse)
def create_product(
    payload: SKUCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    sku = SKU(**payload.model_dump())
    db.add(sku)
    db.commit()
    db.refresh(sku)
    return to_sku_response(db, sku)


@router.get("/products/{id}", response_model=SKUResponse)
def get_product(id: int, db: Session = Depends(get_db)):
    sku = db.get(SKU, id)
    if not sku:
        raise HTTPException(status_code=404, detail="SKU not found")
    return to_sku_response(db, sku)


@router.post("/orders/inbound", response_model=StockEntryResponse)
def create_inbound_order(
    payload: StockEntryCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    sku = db.get(SKU, payload.sku_id)
    if not sku:
        raise HTTPException(status_code=404, detail="SKU not found")

    entry = StockEntry(**payload.model_dump(), user_uuid=get_user_uuid(current_user))
    db.add(entry)
    db.commit()
    db.refresh(entry)

    return StockEntryResponse(**entry.model_dump())


@router.post("/orders/outbound", response_model=StockExitResponse)
def create_outbound_order(
    payload: StockExitCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    sku = db.get(SKU, payload.sku_id)
    if not sku:
        raise HTTPException(status_code=404, detail="SKU not found")

    available = compute_current_stock(db, payload.sku_id, payload.warehouse)

    if payload.quantity > available:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient stock for SKU '{sku.sku}'. Available: {available}, requested: {payload.quantity}.",
        )

    stock_exit = StockExit(**payload.model_dump(), user_uuid=get_user_uuid(current_user))
    db.add(stock_exit)
    db.commit()
    db.refresh(stock_exit)

    return StockExitResponse(**stock_exit.model_dump())


@router.get("/orders", response_model=list[StockMovementResponse])
def list_orders(db: Session = Depends(get_db)):
    movements = []

    entries = db.exec(select(StockEntry, SKU).join(SKU, StockEntry.sku_id == SKU.id)).all()
    exits = db.exec(select(StockExit, SKU).join(SKU, StockExit.sku_id == SKU.id)).all()

    for entry, sku in entries:
        movements.append(
            StockMovementResponse(
                id=entry.id,
                movement_type="entry",
                sku_id=entry.sku_id,
                sku=sku.sku,
                sku_name=sku.name,
                quantity=entry.quantity,
                warehouse=entry.warehouse,
                created_at=entry.created_at,
                user_uuid=entry.user_uuid,
                reference=entry.reference,
            )
        )

    for exit_order, sku in exits:
        movements.append(
            StockMovementResponse(
                id=exit_order.id,
                movement_type="exit",
                sku_id=exit_order.sku_id,
                sku=sku.sku,
                sku_name=sku.name,
                quantity=exit_order.quantity,
                warehouse=exit_order.warehouse,
                created_at=exit_order.created_at,
                user_uuid=exit_order.user_uuid,
                exit_type=exit_order.exit_type,
                tracking_number=exit_order.tracking_number,
            )
        )

    return sorted(movements, key=lambda movement: movement.created_at)
