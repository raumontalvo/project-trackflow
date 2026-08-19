"""Compiled LangGraph workflow for the TrackFlow knowledge agent."""

from __future__ import annotations

from uuid import uuid4

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from services.agent.nodes import (
    country_policy_guard_node,
    generate_answer_node,
    generate_combined_answer_node,
    generate_ticket_answer_node,
    guard_input_node,
    no_context_node,
    output_guard_node,
    retrieve_context_node,
    route_after_country_policy,
    route_after_guard,
    route_after_output_guard,
    route_after_request,
    route_after_retrieval,
    route_after_ticket_lookup,
    route_after_tracking_authorization,
    route_after_validation,
    route_request_node,
    ticket_fallback_node,
    ticket_lookup_node,
    tracking_authorization_node,
    validate_question_node,
)
from services.agent.state import AgentState
from services.agent.trace import (
    record_guardrail_event,
    record_trace,
)


def build_graph():
    """Build and compile the TrackFlow support-agent graph."""
    builder = StateGraph(AgentState)

    builder.add_node("validate_question", validate_question_node)
    builder.add_node("guard_input", guard_input_node)
    builder.add_node("tracking_authorization", tracking_authorization_node)
    builder.add_node("country_policy_guard", country_policy_guard_node)
    builder.add_node("route_request", route_request_node)
    builder.add_node("retrieve_context", retrieve_context_node)
    builder.add_node("ticket_lookup", ticket_lookup_node)
    builder.add_node("ticket_fallback", ticket_fallback_node)
    builder.add_node("no_context", no_context_node)
    builder.add_node("generate_answer", generate_answer_node)
    builder.add_node("generate_ticket_answer", generate_ticket_answer_node)
    builder.add_node("generate_combined_answer", generate_combined_answer_node)
    builder.add_node("output_guard", output_guard_node)

    builder.add_edge(START, "validate_question")

    builder.add_conditional_edges(
        "validate_question",
        route_after_validation,
        {
            "valid": "guard_input",
            "invalid": END,
        },
    )

    builder.add_conditional_edges(
        "guard_input",
        route_after_guard,
        {
            "allowed": "tracking_authorization",
            "blocked": END,
        },
    )

    builder.add_conditional_edges(
        "tracking_authorization",
        route_after_tracking_authorization,
        {
            "allowed": "country_policy_guard",
            "blocked": END,
        },
    )

    builder.add_conditional_edges(
        "country_policy_guard",
        route_after_country_policy,
        {
            "allowed": "route_request",
            "blocked": END,
        },
    )

    builder.add_conditional_edges(
        "route_request",
        route_after_request,
        {
            "rag": "retrieve_context",
            "ticket": "ticket_lookup",
            "both": "ticket_lookup",
        },
    )

    builder.add_conditional_edges(
        "ticket_lookup",
        route_after_ticket_lookup,
        {
            "ticket": "generate_ticket_answer",
            "both": "retrieve_context",
            "failed": "ticket_fallback",
        },
    )

    builder.add_conditional_edges(
        "retrieve_context",
        route_after_retrieval,
        {
            "context_found": "generate_answer",
            "combined": "generate_combined_answer",
            "no_context": "no_context",
        },
    )

    # Every normal answer path must pass through output validation.
    builder.add_edge("generate_answer", "output_guard")
    builder.add_edge("generate_ticket_answer", "output_guard")
    builder.add_edge("generate_combined_answer", "output_guard")
    builder.add_edge("ticket_fallback", "output_guard")
    builder.add_edge("no_context", "output_guard")

    builder.add_conditional_edges(
        "output_guard",
        route_after_output_guard,
        {
            "allowed": END,
            "blocked": END,
        },
    )

    checkpointer = MemorySaver()

    return builder.compile(checkpointer=checkpointer)


agent_graph = build_graph()


def record_triggered_guardrail(
    *,
    run_id: str,
    question: str,
    result: AgentState,
) -> None:
    """Record the guardrail that stopped, redirected, or replaced a response."""
    if result.get("guardrail_allowed") is False:
        record_guardrail_event(
            run_id=run_id,
            question=question,
            guardrail_type=str(
                result.get("guardrail_category") or "content"
            ),
            reason=str(
                result.get("guardrail_reason") or "input_guardrail"
            ),
            action="blocked_or_redirected",
        )
        return

    if (
        result.get("tracking_number")
        and result.get("tracking_authorized") is False
    ):
        record_guardrail_event(
            run_id=run_id,
            question=question,
            guardrail_type="authorization",
            reason=str(
                result.get("tracking_authorization_reason")
                or "tracking_authorization_failed"
            ),
            action="blocked",
        )
        return

    if result.get("country_policy_allowed") is False:
        record_guardrail_event(
            run_id=run_id,
            question=question,
            guardrail_type="country_policy",
            reason=str(
                result.get("country_policy_reason")
                or "country_policy_mismatch"
            ),
            action="blocked",
        )
        return

    if result.get("output_guard_allowed") is False:
        record_guardrail_event(
            run_id=run_id,
            question=question,
            guardrail_type=str(
                result.get("output_guard_failure_type") or "content"
            ),
            reason=str(
                result.get("output_guard_reason")
                or "output_validation_failed"
            ),
            action="response_replaced",
        )


async def run_agent(
    question: str,
    authenticated_user: dict | None = None,
) -> AgentState:
    """Run the compiled graph asynchronously and persist a structured trace."""
    run_id = str(uuid4())

    if authenticated_user is None:
        authenticated_user = {
            "id": "test-user",
            "uuid": "test-user",
        }

    authenticated_user_id = str(authenticated_user["id"])
    authenticated_user_uuid = str(
        authenticated_user.get("uuid")
        or authenticated_user.get("user_uuid")
        or authenticated_user["id"]
    )

    initial_state: AgentState = {
        "question": question,
        "run_id": run_id,
        "authenticated_user_id": authenticated_user_id,
        "authenticated_user_uuid": authenticated_user_uuid,
    }

    config = {
        "configurable": {
            "thread_id": run_id,
        }
    }

    events: list[dict] = []
    final_state: AgentState = initial_state.copy()

    async for event in agent_graph.astream(
        initial_state,
        config=config,
        stream_mode="updates",
    ):
        for node_name, update in event.items():
            events.append(
                {
                    "node": node_name,
                    "output": update,
                }
            )

            if isinstance(update, dict):
                final_state.update(update)

    record_triggered_guardrail(
        run_id=run_id,
        question=question,
        result=final_state,
    )

    record_trace(
        run_id=run_id,
        question=question,
        result=final_state,
        events=events,
    )

    return final_state