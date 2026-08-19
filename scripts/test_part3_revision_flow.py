"""End-to-end test of TrackFlow Part 3 request_changes revision flow."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from sqlmodel import Session, select

from data.pipelines.rfp_intake.approval_graph import (
    get_approval_workflow_state,
)
from services.api.database import engine
from services.api.models import RFP, Ticket


BASE_URL = "http://127.0.0.1:8000"
POLL_SECONDS = 5
MAX_POLLS = 30


def request_json(
    method: str,
    path: str,
    payload: dict | None = None,
) -> dict:
    """Call the local FastAPI server and decode JSON."""

    url = f"{BASE_URL}{path}"

    data = None
    headers = {}

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=30,
        ) as response:
            return json.loads(
                response.read().decode("utf-8")
            )

    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")

        raise RuntimeError(
            f"{method} {path} failed "
            f"with HTTP {exc.code}: {body}"
        ) from exc

    except urllib.error.URLError as exc:
        raise RuntimeError(
            "Cannot reach FastAPI at "
            f"{BASE_URL}. Make sure Uvicorn is running."
        ) from exc


def find_fresh_luna_ticket() -> str:
    """Find an untouched Luna Cosmetics intake_complete ticket."""

    with Session(engine) as session:
        tickets = list(
            session.exec(
                select(Ticket).order_by(
                    Ticket.created_at.desc()
                )
            ).all()
        )

        for ticket in tickets:
            if ticket.status != "intake_complete":
                continue

            if not ticket.rfp_id:
                continue

            rfp = session.get(
                RFP,
                ticket.rfp_id,
            )

            if rfp is None:
                continue

            if rfp.client_name != "Luna Cosmetics":
                continue

            departments = set(
                rfp.departments_needed or []
            )

            if departments != {
                "warehouse",
                "lastmile",
            }:
                continue

            return ticket.ticket_id

    raise RuntimeError(
        "No untouched Luna Cosmetics intake_complete "
        "ticket is available."
    )


def main() -> None:
    print("=== TrackFlow Part 3 revision test ===")

    # ---------------------------------------------------------
    # 1. Find clean real ticket
    # ---------------------------------------------------------

    ticket_id = find_fresh_luna_ticket()

    print("ticket:", ticket_id)

    initial = request_json(
        "GET",
        f"/rfp-intake/{ticket_id}",
    )

    print("initial status:", initial["status"])

    if initial["status"] != "intake_complete":
        raise RuntimeError(
            "Selected ticket is not intake_complete."
        )

    print(
        "departments:",
        initial["rfp"]["departments_needed"],
    )

    # ---------------------------------------------------------
    # 2. Start Part 2
    # ---------------------------------------------------------

    generation = request_json(
        "POST",
        f"/rfp-intake/{ticket_id}/generate",
    )

    print(
        "generation started:",
        generation["status"],
    )

    # ---------------------------------------------------------
    # 3. Wait for automatic Part 2 -> Part 3 transition
    # ---------------------------------------------------------

    ticket = {}

    for attempt in range(
        1,
        MAX_POLLS + 1,
    ):
        time.sleep(POLL_SECONDS)

        ticket = request_json(
            "GET",
            f"/rfp-intake/{ticket_id}",
        )

        print(
            f"poll {attempt}:",
            ticket["status"],
        )

        if ticket["status"] == "waiting_for_approval":
            break

        if ticket.get("error_message"):
            raise RuntimeError(
                f"Workflow error: "
                f"{ticket['error_message']}"
            )

        if ticket["status"] in {
            "needs_human_review",
            "discarded",
            "done",
        }:
            raise RuntimeError(
                "Unexpected workflow state while "
                f"waiting for Part 3: {ticket['status']}"
            )

    else:
        raise RuntimeError(
            "Timed out waiting for waiting_for_approval."
        )

    print(
        "\nautomatic Part 2 -> Part 3 handoff: OK"
    )

    # ---------------------------------------------------------
    # 4. Get real pending approvals
    # ---------------------------------------------------------

    approvals = request_json(
        "GET",
        f"/rfp-intake/{ticket_id}/approvals",
    )

    pending = approvals[
        "pending_approvals"
    ]

    print("\ninitial pending approvals:")

    for approval in pending:
        print(
            approval["department_id"],
            "->",
            approval["approver"],
            "->",
            approval["interrupt_id"],
        )

    ana_approval = next(
        (
            approval
            for approval in pending
            if approval["department_id"]
            == "warehouse"
            and approval["approver"]
            == "Ana Whitfield"
        ),
        None,
    )

    carlos_approval = next(
        (
            approval
            for approval in pending
            if approval["department_id"]
            == "lastmile"
            and approval["approver"]
            == "Carlos Vega"
        ),
        None,
    )

    if ana_approval is None:
        raise RuntimeError(
            "Ana Whitfield warehouse interrupt missing."
        )

    if carlos_approval is None:
        raise RuntimeError(
            "Carlos Vega lastmile interrupt missing."
        )

    original_carlos_interrupt = (
        carlos_approval["interrupt_id"]
    )

    # ---------------------------------------------------------
    # 5. Ana requests changes
    # ---------------------------------------------------------

    print(
        "\nsubmitting warehouse request_changes..."
    )

    decision = request_json(
        "POST",
        (
            f"/rfp-intake/{ticket_id}/approvals/"
            f"{ana_approval['interrupt_id']}"
        ),
        {
            "action": "request_changes",
            "approver": "Ana Whitfield",
            "comment": (
                "Revise the warehouse section "
                "before approval."
            ),
        },
    )

    print(
        "decision workflow status:",
        decision.get(
            "workflow_status"
        ),
    )

    # ---------------------------------------------------------
    # 6. Inspect persisted LangGraph state
    # ---------------------------------------------------------

    snapshot = get_approval_workflow_state(
        ticket_id
    )

    revision_counts = snapshot.values.get(
        "revision_counts",
        {},
    )

    print("\nrevision counts:")
    print(
        json.dumps(
            revision_counts,
            indent=2,
            ensure_ascii=False,
        )
    )

    print("\ntrace:")

    for event in snapshot.values.get(
        "trace_events",
        [],
    ):
        print(
            event.get("event"),
            event.get(
                "department_id",
                "",
            ),
            event.get(
                "revision_count",
                "",
            ),
        )

    # ---------------------------------------------------------
    # 7. Verify pending branch behavior
    # ---------------------------------------------------------

    approvals_after = request_json(
        "GET",
        f"/rfp-intake/{ticket_id}/approvals",
    )

    pending_after = approvals_after[
        "pending_approvals"
    ]

    print("\npending approvals after revision:")

    for approval in pending_after:
        print(
            approval["department_id"],
            "->",
            approval["approver"],
            "->",
            approval["interrupt_id"],
        )

    warehouse_after = [
        approval
        for approval in pending_after
        if approval["department_id"]
        == "warehouse"
    ]

    lastmile_after = [
        approval
        for approval in pending_after
        if approval["department_id"]
        == "lastmile"
    ]

    # ---------------------------------------------------------
    # 8. Assertions
    # ---------------------------------------------------------

    assert revision_counts.get(
        "warehouse"
    ) == 1, (
        "warehouse revision_count should be 1"
    )

    assert revision_counts.get(
        "lastmile",
        0,
    ) == 0, (
        "lastmile revision_count should remain 0"
    )

    assert len(
        warehouse_after
    ) == 1, (
        "warehouse should have a fresh approval interrupt"
    )

    assert len(
        lastmile_after
    ) == 1, (
        "lastmile should remain independently pending"
    )

    assert (
        warehouse_after[0]["interrupt_id"]
        != ana_approval["interrupt_id"]
    ), (
        "warehouse should receive a NEW interrupt ID"
    )

    assert (
        lastmile_after[0]["interrupt_id"]
        == original_carlos_interrupt
    ), (
        "Carlos's lastmile interrupt should remain unchanged"
    )

    trace_events = [
        event.get("event")
        for event in snapshot.values.get(
            "trace_events",
            [],
        )
    ]

    assert "section_revised" in trace_events, (
        "section_revised trace event missing"
    )

    print(
        "\nSUCCESS: warehouse revised independently, "
        "received a new Ana interrupt, and Carlos's "
        "lastmile branch remained untouched."
    )


if __name__ == "__main__":
    main()
