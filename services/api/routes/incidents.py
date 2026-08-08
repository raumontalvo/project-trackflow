from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from tinydb import Query

from services.api.database import incidents_table
from services.api.models import IncidentCreate, IncidentStatusUpdate
from packages.shared.incident_validation import ValidationError, validate_status_transition

router = APIRouter(prefix="/api/incidents", tags=["incidents"])

IncidentQuery = Query()


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def public_incident(doc):
    return {**doc, "id": doc.doc_id}


@router.post("")
def create_incident(payload: IncidentCreate):
    data = payload.model_dump()
    timestamp = now_iso()

    data["created_at"] = timestamp
    data["updated_at"] = timestamp

    doc_id = incidents_table.insert(data)
    return {**data, "id": doc_id}


@router.get("")
def list_incidents(
    status: str | None = None,
    origin: str | None = None,
    branch: str | None = None,
    category: str | None = None,
):
    incidents = incidents_table.all()

    if status:
        incidents = [item for item in incidents if item.get("status") == status]
    if origin:
        incidents = [item for item in incidents if item.get("origin") == origin]
    if branch:
        incidents = [item for item in incidents if item.get("branch") == branch]
    if category:
        incidents = [item for item in incidents if item.get("category") == category]

    return [public_incident(item) for item in incidents]


@router.get("/summary")
def incident_summary():
    incidents = incidents_table.all()

    summary = {
        "total": len(incidents),
        "by_status": {},
        "by_category": {},
        "by_origin": {},
        "by_branch": {},
    }

    for incident in incidents:
        for field, key in [
            ("status", "by_status"),
            ("category", "by_category"),
            ("origin", "by_origin"),
            ("branch", "by_branch"),
        ]:
            value = incident.get(field)
            if value:
                summary[key][value] = summary[key].get(value, 0) + 1

    return summary


@router.get("/{incident_id}")
def get_incident(incident_id: int):
    incident = incidents_table.get(doc_id=incident_id)

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found.")

    return public_incident(incident)


@router.patch("/{incident_id}/status")
def update_incident_status(incident_id: int, payload: IncidentStatusUpdate):
    incident = incidents_table.get(doc_id=incident_id)

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found.")

    try:
        validate_status_transition(incident.get("status"), payload.status)
    except ValidationError as error:
        raise HTTPException(
            status_code=400,
            detail={"field": error.field, "message": error.message},
        )

    incidents_table.update(
        {"status": payload.status, "updated_at": now_iso()},
        doc_ids=[incident_id],
    )

    updated = incidents_table.get(doc_id=incident_id)
    return public_incident(updated)
