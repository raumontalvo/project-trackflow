"""Single-responsibility nodes for the TrackFlow LangGraph agent."""

from __future__ import annotations

import re

from data.pipelines.rag import (
    DEFAULT_SCORE_THRESHOLD,
    DEFAULT_TOP_K,
    NO_CONTEXT_ANSWER,
    build_context,
    generate_answer,
    retrieve,
)
from services.agent.memory.decision import classify_memory_decision
from services.agent.memory.evaluator import generate_with_memory
from services.agent.memory.models import (
    MemoryAuditRecord,
    MemoryDecision,
    MemoryProposal,
    ProposalStatus,
)
from services.agent.memory.policy import validate_memory_proposal
from services.agent.memory.store import MemoryStore
from services.agent.state import AgentState
from services.agent.tools import TicketLookupInput, lookup_ticket


TICKET_PATTERN = re.compile(
    r"\b(?:ticket|incident)\s*#?\s*(\d+)\b",
    re.IGNORECASE,
)


def validate_question_node(state: AgentState) -> AgentState:
    """Validate and normalize the incoming question."""
    question = state.get("question", "").strip()

    if not question:
        return {
            "question": "",
            "error": "Question cannot be empty.",
            "answer": "",
        }

    return {
        "question": question,
        "error": None,
    }


def recall_memory_node(state: AgentState) -> AgentState:
    """Recall only approved persistent memory relevant to this request."""

    question = state.get("question", "").strip()

    if not question:
        return {
            "recalled_memories": [],
            "memory_context": "",
        }

    store = MemoryStore()
    recalled = store.recall_relevant(question)

    if not recalled:
        return {
            "recalled_memories": [],
            "memory_context": "",
        }

    context_lines = [
        "APPROVED TRACKFLOW MEMORY:",
    ]

    for index, memory in enumerate(recalled, start=1):
        context_lines.append(
            f"{index}. [{memory.memory_type.value}] {memory.content}"
        )

    return {
        "recalled_memories": [
            memory.model_dump(mode="json")
            for memory in recalled
        ],
        "memory_context": "\n".join(context_lines),
    }



def route_request_node(state: AgentState) -> AgentState:
    """Classify whether the request needs RAG, a ticket lookup, or both."""
    question = state["question"]
    match = TICKET_PATTERN.search(question)

    if not match:
        return {
            "route": "rag",
            "incident_id": None,
        }

    incident_id = int(match.group(1))

    policy_terms = (
        "policy",
        "procedure",
        "according to",
        "what should",
        "how should",
        "escalat",
        "return",
        "sla",
    )

    route = (
        "both"
        if any(term in question.lower() for term in policy_terms)
        else "ticket"
    )

    return {
        "route": route,
        "incident_id": incident_id,
    }


def retrieve_context_node(state: AgentState) -> AgentState:
    """Retrieve and format approved TrackFlow knowledge-base context."""
    question = state["question"]

    chunks = retrieve(
        question,
        k=DEFAULT_TOP_K,
        min_score=DEFAULT_SCORE_THRESHOLD,
    )

    context = build_context(chunks)

    return {
        "chunks": chunks,
        "context": context,
    }


async def ticket_lookup_node(state: AgentState) -> AgentState:
    """Query current ticket data through the TrackFlow MCP server."""
    incident_id = state.get("incident_id")

    if incident_id is None:
        return {
            "ticket_result": None,
            "error": "No incident ID was provided for ticket lookup.",
        }

    result = await lookup_ticket(
        TicketLookupInput(
            incident_id=incident_id,
        )
    )

    return {
        "ticket_result": result.model_dump(mode="json"),
    }


def no_context_node(state: AgentState) -> AgentState:
    """Return the existing safe fallback when retrieval finds no context."""
    return {
        "answer": NO_CONTEXT_ANSWER,
    }


def generate_answer_node(state: AgentState) -> AgentState:
    """Generate the answer and memory proposal in one model call."""
    question = state["question"]
    context = state.get("context", "")
    memory_context = state.get("memory_context", "")
    conversation_id = state["conversation_id"]

    combined_context = "\n\n".join(
        part
        for part in (memory_context, context)
        if part
    )

    answer, proposal = generate_with_memory(
        question=question,
        context=combined_context,
        conversation_id=conversation_id,
    )

    return {
        "answer": answer,
        "memory_proposal": (
            proposal.model_dump(mode="json")
            if proposal is not None
            else None
        ),
    }


def generate_ticket_answer_node(state: AgentState) -> AgentState:
    """Generate a deterministic answer from live incident data."""
    ticket_result = state.get("ticket_result") or {}
    incident = ticket_result["incident"]

    return {
        "answer": (
            f"Incident {incident['id']} is currently "
            f"{incident['status'].replace('_', ' ')}. "
            f"Title: {incident['title']}. "
            f"Branch: {incident['branch']}."
        )
    }


def ticket_fallback_node(state: AgentState) -> AgentState:
    """Return a safe deterministic answer when the incident tool fails."""
    ticket_result = state.get("ticket_result") or {}

    return {
        "answer": (
            ticket_result.get("error")
            or "I could not confirm the current incident status."
        )
    }


def generate_combined_answer_node(state: AgentState) -> AgentState:
    """Answer using both live incident data and approved RAG context."""
    ticket_result = state.get("ticket_result") or {}
    incident = ticket_result["incident"]
    context = state.get("context", "")

    memory_context = state.get("memory_context", "")

    combined_context = (
        f"{memory_context}\n\n" if memory_context else ""
    ) + (
        "LIVE INCIDENT DATA:\n"
        f"ID: {incident['id']}\n"
        f"Title: {incident['title']}\n"
        f"Description: {incident['description']}\n"
        f"Category: {incident['category']}\n"
        f"Status: {incident['status']}\n"
        f"Origin: {incident['origin']}\n"
        f"Branch: {incident['branch']}\n\n"
        "KNOWLEDGE BASE CONTEXT:\n"
        f"{context}"
    )

    answer, proposal = generate_with_memory(
        question=state["question"],
        context=combined_context,
        conversation_id=state["conversation_id"],
    )

    return {
        "answer": answer,
        "memory_proposal": (
            proposal.model_dump(mode="json")
            if proposal is not None
            else None
        ),
    }




def resolve_pending_memory_node(state: AgentState) -> AgentState:
    """Resolve the user's decision for one pending memory proposal."""

    conversation_id = state.get("conversation_id", "").strip()
    user_message = state.get("question", "").strip()

    if not conversation_id:
        return {
            "memory_status": "no_conversation",
            "memory_decision": None,
        }

    store = MemoryStore()
    proposal = store.get_pending(conversation_id)

    if proposal is None:
        return {
            "memory_status": "no_pending",
            "memory_decision": None,
        }

    decision = classify_memory_decision(
        user_message=user_message,
        proposal=proposal,
    )

    if decision.decision == MemoryDecision.APPROVE:
        stored = store.write_memory(proposal)

        store.append_audit(
            MemoryAuditRecord(
                proposal_id=proposal.proposal_id,
                conversation_id=proposal.conversation_id,
                proposed_memory=proposal.content,
                originating_message=proposal.originating_message,
                outcome=ProposalStatus.APPROVED,
                user_decision=MemoryDecision.APPROVE,
                final_memory=stored.content,
                proposed_at=proposal.created_at,
            )
        )

        store.discard_pending(conversation_id)

        if decision.follow_up_question:
            return {
                "question": decision.follow_up_question,
                "memory_notice": (
                    "Got it. I saved that for future TrackFlow conversations."
                ),
                "memory_status": "approved_followup",
                "memory_decision": decision.model_dump(mode="json"),
            }

        return {
            "answer": "Got it. I saved that for future TrackFlow conversations.",
            "memory_status": "approved",
            "memory_decision": decision.model_dump(mode="json"),
        }

    if decision.decision == MemoryDecision.REJECT:
        store.append_audit(
            MemoryAuditRecord(
                proposal_id=proposal.proposal_id,
                conversation_id=proposal.conversation_id,
                proposed_memory=proposal.content,
                originating_message=proposal.originating_message,
                outcome=ProposalStatus.REJECTED,
                user_decision=MemoryDecision.REJECT,
                proposed_at=proposal.created_at,
            )
        )

        store.discard_pending(conversation_id)

        if decision.follow_up_question:
            return {
                "question": decision.follow_up_question,
                "memory_notice": "Understood. I did not save that.",
                "memory_status": "rejected_followup",
                "memory_decision": decision.model_dump(mode="json"),
            }

        return {
            "answer": "Understood. I did not save that.",
            "memory_status": "rejected",
            "memory_decision": decision.model_dump(mode="json"),
        }

    if decision.decision == MemoryDecision.EDIT:
        edited = proposal.model_copy(
            update={
                "content": decision.edited_content.strip(),
                "status": ProposalStatus.EDITED,
            }
        )

        policy_result = validate_memory_proposal(edited)

        if not policy_result.allowed:
            store.append_audit(
                MemoryAuditRecord(
                    proposal_id=proposal.proposal_id,
                    conversation_id=proposal.conversation_id,
                    proposed_memory=proposal.content,
                    originating_message=proposal.originating_message,
                    outcome=ProposalStatus.BLOCKED,
                    user_decision=MemoryDecision.EDIT,
                    proposed_at=proposal.created_at,
                )
            )

            store.discard_pending(conversation_id)

            return {
                "answer": (
                    "I could not save that edited memory because it conflicts "
                    "with TrackFlow memory policy."
                ),
                "memory_status": "blocked",
                "memory_decision": decision.model_dump(mode="json"),
            }

        stored = store.write_memory(edited)

        store.append_audit(
            MemoryAuditRecord(
                proposal_id=proposal.proposal_id,
                conversation_id=proposal.conversation_id,
                proposed_memory=proposal.content,
                originating_message=proposal.originating_message,
                outcome=ProposalStatus.EDITED,
                user_decision=MemoryDecision.EDIT,
                final_memory=stored.content,
                proposed_at=proposal.created_at,
            )
        )

        store.discard_pending(conversation_id)

        if decision.follow_up_question:
            return {
                "question": decision.follow_up_question,
                "memory_notice": (
                    "Got it. I saved the corrected version for future "
                    "TrackFlow conversations."
                ),
                "memory_status": "edited_followup",
                "memory_decision": decision.model_dump(mode="json"),
            }

        return {
            "answer": (
                "Got it. I saved the corrected version for future "
                "TrackFlow conversations."
            ),
            "memory_status": "edited",
            "memory_decision": decision.model_dump(mode="json"),
        }

    # Ambiguous and unrelated responses never authorize persistence.
    store.append_audit(
        MemoryAuditRecord(
            proposal_id=proposal.proposal_id,
            conversation_id=proposal.conversation_id,
            proposed_memory=proposal.content,
            originating_message=proposal.originating_message,
            outcome=ProposalStatus.DISCARDED,
            user_decision=decision.decision,
            proposed_at=proposal.created_at,
        )
    )

    store.discard_pending(conversation_id)

    if decision.decision == MemoryDecision.UNRELATED:
        return {
            "memory_status": "discarded_unrelated",
            "memory_decision": decision.model_dump(mode="json"),
        }

    return {
        "answer": (
            "I could not confidently determine whether you wanted that "
            "memory saved, so I discarded the proposal and did not store it."
        ),
        "memory_status": "discarded_ambiguous",
        "memory_decision": decision.model_dump(mode="json"),
    }



def memory_evaluation_node(state: AgentState) -> AgentState:
    """Validate and present the proposal already produced with the answer."""

    answer = state.get("answer", "").strip()
    raw_proposal = state.get("memory_proposal")
    memory_notice = state.get("memory_notice", "").strip()

    visible_answer = (
        f"{memory_notice}\n\n{answer}"
        if memory_notice and answer
        else memory_notice or answer
    )

    if not answer or raw_proposal is None:
        return {
            "answer": visible_answer,
            "memory_proposal": None,
            "memory_status": "not_proposed",
        }

    proposal = MemoryProposal.model_validate(raw_proposal)

    policy_result = validate_memory_proposal(proposal)
    store = MemoryStore()

    if not policy_result.allowed:
        store.append_audit(
            MemoryAuditRecord(
                proposal_id=proposal.proposal_id,
                conversation_id=proposal.conversation_id,
                proposed_memory=proposal.content,
                originating_message=proposal.originating_message,
                outcome=ProposalStatus.BLOCKED,
                proposed_at=proposal.created_at,
            )
        )

        return {
            "answer": visible_answer,
            "memory_proposal": None,
            "memory_status": "blocked",
        }

    store.append_audit(
        MemoryAuditRecord(
            proposal_id=proposal.proposal_id,
            conversation_id=proposal.conversation_id,
            proposed_memory=proposal.content,
            originating_message=proposal.originating_message,
            outcome=ProposalStatus.PENDING,
            proposed_at=proposal.created_at,
        )
    )

    store.save_pending(proposal)

    confirmation_prompt = (
        f'{visible_answer}\n\n'
        f'I noticed something that may be useful in future conversations: '
        f'"{proposal.content}" '
        f'Would you like me to remember this for next time?'
    )

    return {
        "answer": confirmation_prompt,
        "memory_proposal": proposal.model_dump(mode="json"),
        "memory_status": "pending",
    }


def route_after_pending_memory(state: AgentState) -> str:
    """Decide whether to continue normally after checking pending memory."""

    status = state.get("memory_status")

    if status in {
        "no_pending",
        "discarded_unrelated",
        "approved_followup",
        "rejected_followup",
        "edited_followup",
    }:
        return "continue"

    return "resolved"



def route_after_validation(state: AgentState) -> str:
    """Route invalid questions directly to the end."""
    if state.get("error"):
        return "invalid"

    return "valid"


def route_after_request(state: AgentState) -> str:
    """Route the request to the appropriate capability."""
    return state.get("route", "rag")


def route_after_retrieval(state: AgentState) -> str:
    """Route based on retrieved context and requested capability."""
    if not state.get("context"):
        return "no_context"

    if state.get("route") == "both":
        return "combined"

    return "context_found"


def route_after_ticket_lookup(state: AgentState) -> str:
    """Route successful tool calls onward and failures to recovery."""
    ticket_result = state.get("ticket_result") or {}

    if not ticket_result.get("success"):
        return "failed"

    if state.get("route") == "both":
        return "both"

    return "ticket"
