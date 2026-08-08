"""FastAPI routes for TrackFlow RFP intake tickets."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    HTTPException,
    UploadFile,
    status,
)
from sqlmodel import Session, select

from data.pipelines.rfp_intake.config import COUNTRY_TO_CURRENCY
from data.pipelines.rfp_intake.graph import run_rfp_intake
from data.pipelines.rfp_intake.persistence import (
    create_ticket,
    mark_ticket_discarded,
    mark_ticket_error,
    persist_valid_rfp,
)
from data.pipelines.rfp_intake.response_service import (
    generate_ticket_response,
)
from services.api.database import engine
from services.api.models import DepartmentSection, RFP, Ticket


router = APIRouter(
    prefix="/rfp-intake",
    tags=["rfp-intake"],
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = PROJECT_ROOT / "data" / "raw"

MAX_PDF_SIZE_BYTES = 25 * 1024 * 1024


def _run_intake_background(
    ticket_id: str,
    raw_pdf_path: str,
) -> None:
    """
    Execute the RFP intake graph after the upload response returns.

    PostgreSQL remains the source of truth for ticket lifecycle state.
    """

    try:
        result = run_rfp_intake(
            raw_pdf_path=raw_pdf_path,
            ticket_id=ticket_id,
        )

        if result.get("status") == "discarded":
            mark_ticket_discarded(ticket_id)
            return

        if result.get("status") != "intake_complete":
            raise RuntimeError(
                "RFP intake graph finished without a valid terminal status."
            )

        metadata = result.get("rfp_metadata") or {}

        department_results = result.get(
            "department_results",
            {},
        )

        summary = result.get("summary") or {}

        persist_valid_rfp(
            ticket_id=ticket_id,
            metadata=metadata,
            department_results=department_results,
            summary=summary,
        )

    except Exception as exc:
        mark_ticket_error(
            ticket_id=ticket_id,
            error_message=str(exc),
        )


def _run_response_generation_background(
    ticket_id: str,
) -> None:
    """
    Run Part 2 proposal generation and evaluation in the background.
    """

    try:
        generate_ticket_response(
            ticket_id
        )

    except Exception as exc:
        mark_ticket_error(
            ticket_id=ticket_id,
            error_message=str(exc),
        )


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_rfp(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> dict[str, str]:
    """
    Accept one PDF and immediately create an analyzing ticket.

    The full RFP pipeline runs in the background.
    """

    filename = file.filename or ""

    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="RFP intake accepts PDF files only.",
        )

    if file.content_type not in {
        "application/pdf",
        "application/octet-stream",
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must be a PDF.",
        )

    contents = await file.read()

    if not contents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded PDF is empty.",
        )

    if len(contents) > MAX_PDF_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Uploaded PDF exceeds the 25 MB limit.",
        )

    if not contents.startswith(b"%PDF"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file does not appear to be a valid PDF.",
        )

    RAW_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    stored_filename = f"{uuid4()}.pdf"
    raw_path = RAW_DIR / stored_filename

    raw_path.write_bytes(contents)

    try:
        ticket = create_ticket(
            raw_pdf_path=str(raw_path),
        )

    except Exception:
        raw_path.unlink(missing_ok=True)
        raise

    background_tasks.add_task(
        _run_intake_background,
        ticket.ticket_id,
        str(raw_path),
    )

    return {
        "ticket_id": ticket.ticket_id,
        "status": "analyzing",
    }


@router.post(
    "/{ticket_id}/generate",
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_rfp_response(
    ticket_id: str,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """
    Start Part 2 response generation for an intake-complete RFP ticket.
    """

    with Session(engine) as session:
        ticket = session.get(
            Ticket,
            ticket_id,
        )

        if ticket is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="RFP ticket not found.",
            )

        if ticket.status != "intake_complete":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "RFP response generation requires "
                    "an intake_complete ticket."
                ),
            )

    background_tasks.add_task(
        _run_response_generation_background,
        ticket_id,
    )

    return {
        "ticket_id": ticket_id,
        "status": "drafting",
    }


@router.get("/{ticket_id}")
def get_rfp_ticket(
    ticket_id: str,
) -> dict:
    """
    Return current ticket status and RFP results when available.
    """

    with Session(engine) as session:
        ticket = session.get(
            Ticket,
            ticket_id,
        )

        if ticket is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="RFP ticket not found.",
            )

        response: dict = {
            "ticket_id": ticket.ticket_id,
            "status": ticket.status,
            "rfp_id": ticket.rfp_id,
            "raw_pdf_path": ticket.raw_pdf_path,
            "error_message": ticket.error_message,
            "created_at": ticket.created_at,
            "updated_at": ticket.updated_at,
            "rfp": None,
            "departments": [],
            "summary": None,
        }

        if not ticket.rfp_id:
            return response

        rfp = session.get(
            RFP,
            ticket.rfp_id,
        )

        if rfp is None:
            return response

        sections = session.exec(
            select(DepartmentSection).where(
                DepartmentSection.rfp_id == rfp.rfp_id
            )
        ).all()

        currency = COUNTRY_TO_CURRENCY.get(
            rfp.client_country
        )

        response["rfp"] = {
            "rfp_id": rfp.rfp_id,
            "client_name": rfp.client_name,
            "client_country": rfp.client_country,
            "currency": currency,
            "services_requested": rfp.services_requested,
            "monthly_volume": rfp.monthly_volume,
            "deadline": rfp.deadline,
            "budget_range": rfp.budget_range,
            "departments_needed": rfp.departments_needed,
            "readability_metrics": rfp.readability_metrics,
            "created_at": rfp.created_at,
            "updated_at": rfp.updated_at,
        }

        response["departments"] = [
            {
                "id": section.id,
                "rfp_id": section.rfp_id,
                "department_id": section.department_id,
                "owner": section.owner,
                "key_aspects": section.key_aspects,
                "draft_content": section.draft_content,
                "evaluation_results": section.evaluation_results,
                "approval_status": section.approval_status,
                "approver": section.approver,
                "approved_at": section.approved_at,
                "created_at": section.created_at,
                "updated_at": section.updated_at,
            }
            for section in sections
        ]

        response["summary"] = rfp.intake_summary

        return response