"""Dedicated LangGraph workflow for TrackFlow RFP intake."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from data.pipelines.rfp_intake.document import (
    calculate_readability,
    convert_pdf_to_markdown,
)
from data.pipelines.rfp_intake.nodes.classify import (
    classify_rfp_node,
    route_after_classification,
)
from data.pipelines.rfp_intake.nodes.metadata import (
    extract_metadata_node,
)
from data.pipelines.rfp_intake.nodes.orchestrator import (
    orchestrator_node,
)
from data.pipelines.rfp_intake.nodes.synthesizer import (
    synthesizer_node,
)
from data.pipelines.rfp_intake.nodes.worker import (
    department_worker_node,
)
from data.pipelines.rfp_intake.state import RFPIntakeState


def document_node(
    state: RFPIntakeState,
) -> RFPIntakeState:
    """Convert the uploaded PDF to Markdown and calculate readability."""

    raw_pdf_path = state.get("raw_pdf_path")

    if not raw_pdf_path:
        raise ValueError("RFP intake requires raw_pdf_path.")

    markdown = convert_pdf_to_markdown(raw_pdf_path)
    readability_metrics = calculate_readability(markdown)

    return {
        "markdown": markdown,
        "readability_metrics": readability_metrics,
    }


def attach_readability_node(
    state: RFPIntakeState,
) -> RFPIntakeState:
    """Attach readability metrics to the accepted RFP metadata."""

    metadata = dict(
        state.get(
            "rfp_metadata",
            {},
        )
    )

    metadata["readability_metrics"] = state.get(
        "readability_metrics",
        {},
    )

    return {
        "rfp_metadata": metadata,
    }


def discard_node(
    state: RFPIntakeState,
) -> RFPIntakeState:
    """Finish processing when the classifier rejects the document."""

    return {
        "status": "discarded",
        "active_departments": [],
        "department_results": {},
        "summary": {
            "classification": state.get(
                "classification"
            ),
            "reason": state.get(
                "rejection_reason"
            ),
        },
    }


def complete_node(
    state: RFPIntakeState,
) -> RFPIntakeState:
    """Mark successful Part 1 intake as complete."""

    return {
        "status": "intake_complete",
    }


def route_to_department_workers(
    state: RFPIntakeState,
) -> list[Send]:
    """
    Fan out one LangGraph worker branch per active department.

    Each worker receives shared metadata plus only that department's
    relevant extracts.
    """

    active_departments = state.get(
        "active_departments",
        [],
    )

    department_extracts = state.get(
        "department_extracts",
        {},
    )

    if not active_departments:
        raise ValueError(
            "Valid RFP produced no active TrackFlow departments."
        )

    return [
        Send(
            "department_worker",
            {
                "department_id": department_id,
                "rfp_metadata": state.get(
                    "rfp_metadata",
                    {},
                ),
                "department_extract": department_extracts.get(
                    department_id,
                    [],
                ),
            },
        )
        for department_id in active_departments
    ]


def build_graph():
    """Build and compile the dedicated TrackFlow RFP intake graph."""

    builder = StateGraph(RFPIntakeState)

    builder.add_node(
        "document",
        document_node,
    )

    builder.add_node(
        "classifier",
        classify_rfp_node,
    )

    builder.add_node(
        "metadata",
        extract_metadata_node,
    )

    builder.add_node(
        "attach_readability",
        attach_readability_node,
    )

    builder.add_node(
        "orchestrator",
        orchestrator_node,
    )

    builder.add_node(
        "department_worker",
        department_worker_node,
    )

    builder.add_node(
        "synthesizer",
        synthesizer_node,
    )

    builder.add_node(
        "complete",
        complete_node,
    )

    builder.add_node(
        "discard",
        discard_node,
    )

    builder.add_edge(
        START,
        "document",
    )

    builder.add_edge(
        "document",
        "classifier",
    )

    builder.add_conditional_edges(
        "classifier",
        route_after_classification,
        {
            "valid": "metadata",
            "discarded": "discard",
        },
    )

    builder.add_edge(
        "discard",
        END,
    )

    builder.add_edge(
        "metadata",
        "attach_readability",
    )

    builder.add_edge(
        "attach_readability",
        "orchestrator",
    )

    builder.add_conditional_edges(
        "orchestrator",
        route_to_department_workers,
    )

    builder.add_edge(
        "department_worker",
        "synthesizer",
    )

    builder.add_edge(
        "synthesizer",
        "complete",
    )

    builder.add_edge(
        "complete",
        END,
    )

    return builder.compile()


rfp_intake_graph = build_graph()


def run_rfp_intake(
    raw_pdf_path: str,
    ticket_id: str = "local-test",
) -> RFPIntakeState:
    """Run the complete dedicated intake graph for one uploaded PDF."""

    initial_state: RFPIntakeState = {
        "ticket_id": ticket_id,
        "raw_pdf_path": raw_pdf_path,
        "status": "analyzing",
        "department_results": {},
        "error": None,
    }

    return rfp_intake_graph.invoke(initial_state)