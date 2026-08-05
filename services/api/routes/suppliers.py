from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from services.api.database import suppliers_table
from services.api.models import RateUpdate, StatusUpdate, Supplier, SupplierCreate

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


def with_id(document):
    data = document.copy()
    data["id"] = document.doc_id
    return data


@router.post("", response_model=Supplier, status_code=201)
def create_supplier(supplier: SupplierCreate):
    data = supplier.model_dump()
    data["rate_updated_at"] = datetime.now(timezone.utc).isoformat()

    doc_id = suppliers_table.insert(data)

    return {"id": doc_id, **data}


@router.get("", response_model=list[Supplier])
def list_suppliers(
    country: str | None = None,
    category: str | None = Query(default=None),
):
    documents = suppliers_table.all()

    if country:
        documents = [doc for doc in documents if doc.get("country") == country]

    if category:
        documents = [doc for doc in documents if category in doc.get("categories", [])]

    return [with_id(doc) for doc in documents]


@router.get("/{supplier_id}", response_model=Supplier)
def get_supplier(supplier_id: int):
    document = suppliers_table.get(doc_id=supplier_id)

    if not document:
        raise HTTPException(status_code=404, detail="Supplier not found")

    return with_id(document)


@router.patch("/{supplier_id}/rate", response_model=Supplier)
def update_supplier_rate(supplier_id: int, payload: RateUpdate):
    document = suppliers_table.get(doc_id=supplier_id)

    if not document:
        raise HTTPException(status_code=404, detail="Supplier not found")

    suppliers_table.update(
        {
            "rate_per_shipment": payload.rate_per_shipment,
            "rate_updated_at": datetime.now(timezone.utc).isoformat(),
        },
        doc_ids=[supplier_id],
    )

    updated = suppliers_table.get(doc_id=supplier_id)
    return with_id(updated)


@router.patch("/{supplier_id}/status", response_model=Supplier)
def update_supplier_status(supplier_id: int, payload: StatusUpdate):
    document = suppliers_table.get(doc_id=supplier_id)

    if not document:
        raise HTTPException(status_code=404, detail="Supplier not found")

    suppliers_table.update({"status": payload.status}, doc_ids=[supplier_id])

    updated = suppliers_table.get(doc_id=supplier_id)
    return with_id(updated)


@router.delete("/{supplier_id}")
def delete_supplier(supplier_id: int):
    document = suppliers_table.get(doc_id=supplier_id)

    if not document:
        raise HTTPException(status_code=404, detail="Supplier not found")

    suppliers_table.remove(doc_ids=[supplier_id])
    return {"message": "Supplier deleted"}