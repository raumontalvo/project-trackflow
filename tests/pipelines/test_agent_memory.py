"""Tests for TrackFlow agent memory policy, persistence, and consolidation."""

from __future__ import annotations

from tempfile import TemporaryDirectory

from services.agent.memory.models import (
    MemoryAuditRecord,
    MemoryDecision,
    MemoryDecisionResult,
    MemoryProposal,
    MemoryType,
    ProposalStatus,
    utc_now,
)
from services.agent.memory.policy import validate_memory_proposal
from services.agent.memory.store import MemoryStore


def build_proposal(
    *,
    conversation_id: str = "conversation-1",
    memory_type: MemoryType = MemoryType.CARRIER_RULE,
    content: str = "SEUR no longer covers rural Zaragoza.",
    country: str | None = "ES",
    carrier: str | None = "SEUR",
    b2b_client: str | None = None,
    reason: str = "Recurring carrier correction.",
) -> MemoryProposal:
    return MemoryProposal(
        conversation_id=conversation_id,
        memory_type=memory_type,
        content=content,
        country=country,
        carrier=carrier,
        b2b_client=b2b_client,
        originating_message=content,
        reason=reason,
    )


def test_valid_carrier_rule_is_allowed() -> None:
    proposal = build_proposal()

    result = validate_memory_proposal(proposal)

    assert result.allowed is True


def test_exact_customer_address_is_blocked() -> None:
    proposal = build_proposal(
        content="Deliver this recurring client order to 123 Main Street.",
    )

    result = validate_memory_proposal(proposal)

    assert result.allowed is False
    assert "addresses" in result.reason.lower()


def test_internal_warehouse_route_is_blocked() -> None:
    proposal = build_proposal(
        content="Use the internal warehouse route through dock 4.",
    )

    result = validate_memory_proposal(proposal)

    assert result.allowed is False
    assert "warehouse" in result.reason.lower()


def test_active_contract_negotiation_is_blocked() -> None:
    proposal = build_proposal(
        memory_type=MemoryType.B2B_REPORT_PREFERENCE,
        content="The client is in an active contract negotiation for lower pricing.",
        carrier=None,
        b2b_client="CosmeticsCo",
    )

    result = validate_memory_proposal(proposal)

    assert result.allowed is False
    assert "crm" in result.reason.lower()


def test_one_off_incident_is_not_memorable() -> None:
    proposal = build_proposal(
        memory_type=MemoryType.RECURRING_INCIDENT,
        content="Package XJ4471 was delayed.",
        carrier=None,
        reason="Single package complaint.",
    )

    result = validate_memory_proposal(proposal)

    assert result.allowed is False


def test_pending_proposal_round_trip() -> None:
    with TemporaryDirectory() as tmp:
        store = MemoryStore(tmp)
        proposal = build_proposal()

        store.save_pending(proposal)

        loaded = store.get_pending(proposal.conversation_id)

        assert loaded is not None
        assert loaded.proposal_id == proposal.proposal_id
        assert loaded.content == proposal.content


def test_only_one_pending_proposal_per_conversation() -> None:
    with TemporaryDirectory() as tmp:
        store = MemoryStore(tmp)

        first = build_proposal(content="First carrier correction.")
        second = build_proposal(content="Second carrier correction.")

        store.save_pending(first)
        store.save_pending(second)

        loaded = store.get_pending(first.conversation_id)

        assert loaded is not None
        assert loaded.proposal_id == second.proposal_id


def test_approved_memory_can_be_persisted_and_recalled() -> None:
    with TemporaryDirectory() as tmp:
        store = MemoryStore(tmp)
        proposal = build_proposal()

        stored = store.write_memory(proposal)

        recalled = store.read_memories(
            memory_type=MemoryType.CARRIER_RULE,
            country="ES",
            carrier="SEUR",
        )

        assert len(recalled) == 1
        assert recalled[0].memory_id == stored.memory_id
        assert recalled[0].content == proposal.content


def test_carrier_rules_are_consolidated_by_carrier_and_country() -> None:
    with TemporaryDirectory() as tmp:
        store = MemoryStore(tmp)

        first = build_proposal(
            content="SEUR covers rural Zaragoza.",
        )
        second = build_proposal(
            content="SEUR no longer covers rural Zaragoza.",
        )

        first_record = store.write_memory(first)
        second_record = store.write_memory(second)

        memories = store.read_memories(
            memory_type=MemoryType.CARRIER_RULE,
            country="ES",
            carrier="SEUR",
        )

        assert len(memories) == 1
        assert memories[0].memory_id == first_record.memory_id
        assert memories[0].memory_id == second_record.memory_id
        assert memories[0].content == second.content


def test_b2b_preferences_are_consolidated_by_client() -> None:
    with TemporaryDirectory() as tmp:
        store = MemoryStore(tmp)

        first = build_proposal(
            memory_type=MemoryType.B2B_REPORT_PREFERENCE,
            content="Put shipment volume first.",
            country=None,
            carrier=None,
            b2b_client="CosmeticsCo",
        )
        second = build_proposal(
            memory_type=MemoryType.B2B_REPORT_PREFERENCE,
            content="Put returns breakdown first.",
            country=None,
            carrier=None,
            b2b_client="CosmeticsCo",
        )

        store.write_memory(first)
        store.write_memory(second)

        memories = store.read_memories(
            memory_type=MemoryType.B2B_REPORT_PREFERENCE,
            b2b_client="CosmeticsCo",
        )

        assert len(memories) == 1
        assert memories[0].content == second.content


def test_audit_log_preserves_rejected_proposal() -> None:
    with TemporaryDirectory() as tmp:
        store = MemoryStore(tmp)
        proposal = build_proposal()

        audit = MemoryAuditRecord(
            proposal_id=proposal.proposal_id,
            conversation_id=proposal.conversation_id,
            proposed_memory=proposal.content,
            originating_message=proposal.originating_message,
            outcome=ProposalStatus.REJECTED,
            user_decision=MemoryDecision.REJECT,
            proposed_at=proposal.created_at,
        )

        store.append_audit(audit)

        records = store.list_audit_records()

        assert len(records) == 1
        assert records[0].proposal_id == proposal.proposal_id
        assert records[0].outcome == ProposalStatus.REJECTED
        assert records[0].user_decision == MemoryDecision.REJECT


def test_memory_evaluation_node_returns_no_proposal(
    monkeypatch,
) -> None:
    """Non-memorable interactions should not create pending memory."""
    from services.agent import nodes

    result = nodes.memory_evaluation_node(
        {
            "question": "Great, that's resolved.",
            "answer": "Glad I could help.",
            "conversation_id": "conversation-none",
            "memory_proposal": None,
        }
    )

    assert result["memory_proposal"] is None
    assert result["memory_status"] == "not_proposed"


def test_memory_evaluation_node_saves_allowed_proposal(
    monkeypatch,
    tmp_path,
) -> None:
    """An allowed proposal should become pending, not persistent."""
    from services.agent import nodes

    store = MemoryStore(tmp_path)

    proposal = build_proposal(
        conversation_id="conversation-allowed",
        content="SEUR no longer covers rural Zaragoza.",
        country="ES",
        carrier="SEUR",
    )

    monkeypatch.setattr(
        nodes,
        "MemoryStore",
        lambda: store,
    )

    result = nodes.memory_evaluation_node(
        {
            "question": proposal.originating_message,
            "answer": "Thanks for the correction.",
            "conversation_id": proposal.conversation_id,
            "memory_proposal": proposal.model_dump(mode="json"),
        }
    )

    pending = store.get_pending(proposal.conversation_id)

    assert result["memory_status"] == "pending"
    assert result["memory_proposal"] is not None
    assert "Would you like me to remember this" in result["answer"]

    assert pending is not None
    assert pending.proposal_id == proposal.proposal_id

    # A proposal must never be persisted before user approval.
    assert store.list_memories() == []


def test_memory_evaluation_node_blocks_forbidden_proposal(
    monkeypatch,
    tmp_path,
) -> None:
    """Forbidden information must never become pending or persistent memory."""
    from services.agent import nodes

    store = MemoryStore(tmp_path)

    proposal = build_proposal(
        conversation_id="conversation-blocked",
        content="Use the internal warehouse route through dock 4.",
    )

    monkeypatch.setattr(
        nodes,
        "MemoryStore",
        lambda: store,
    )

    result = nodes.memory_evaluation_node(
        {
            "question": proposal.originating_message,
            "answer": "I understand.",
            "conversation_id": proposal.conversation_id,
            "memory_proposal": proposal.model_dump(mode="json"),
        }
    )

    assert result["memory_status"] == "blocked"
    assert result["memory_proposal"] is None

    assert store.get_pending(proposal.conversation_id) is None
    assert store.list_memories() == []

    audit = store.list_audit_records()

    assert len(audit) == 1
    assert audit[0].outcome == ProposalStatus.BLOCKED
    assert audit[0].proposal_id == proposal.proposal_id


def test_decision_classifier_approves_clear_confirmation(
    monkeypatch,
) -> None:
    """Clear authorization should classify as approve."""
    from services.agent.memory import decision as decision_module

    class FakeMessage:
        content = (
            '{"decision":"approve","edited_content":null,"confidence":0.99}'
        )

    class FakeChoice:
        message = FakeMessage()

    class FakeResponse:
        choices = [FakeChoice()]

    class FakeCompletions:
        def create(self, **kwargs):
            return FakeResponse()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    monkeypatch.setattr(
        decision_module,
        "_openai_client",
        lambda: FakeClient(),
    )
    monkeypatch.setattr(
        decision_module,
        "_required_env",
        lambda name: "test-model",
    )

    result = decision_module.classify_memory_decision(
        user_message="Yes, remember that.",
        proposal=build_proposal(),
    )

    assert result.decision == MemoryDecision.APPROVE


def test_decision_classifier_rejects_low_confidence_approval(
    monkeypatch,
) -> None:
    """Low-confidence interpretation must fail closed to ambiguous."""
    from services.agent.memory import decision as decision_module

    class FakeMessage:
        content = (
            '{"decision":"approve","edited_content":null,"confidence":0.55}'
        )

    class FakeChoice:
        message = FakeMessage()

    class FakeResponse:
        choices = [FakeChoice()]

    class FakeCompletions:
        def create(self, **kwargs):
            return FakeResponse()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    monkeypatch.setattr(
        decision_module,
        "_openai_client",
        lambda: FakeClient(),
    )
    monkeypatch.setattr(
        decision_module,
        "_required_env",
        lambda name: "test-model",
    )

    result = decision_module.classify_memory_decision(
        user_message="Okay I guess.",
        proposal=build_proposal(),
    )

    assert result.decision == MemoryDecision.AMBIGUOUS


def test_decision_classifier_requires_content_for_edit(
    monkeypatch,
) -> None:
    """Edit without corrected content must fail closed."""
    from services.agent.memory import decision as decision_module

    class FakeMessage:
        content = (
            '{"decision":"edit","edited_content":null,"confidence":0.95}'
        )

    class FakeChoice:
        message = FakeMessage()

    class FakeResponse:
        choices = [FakeChoice()]

    class FakeCompletions:
        def create(self, **kwargs):
            return FakeResponse()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    monkeypatch.setattr(
        decision_module,
        "_openai_client",
        lambda: FakeClient(),
    )
    monkeypatch.setattr(
        decision_module,
        "_required_env",
        lambda name: "test-model",
    )

    result = decision_module.classify_memory_decision(
        user_message="Remember it, but change it.",
        proposal=build_proposal(),
    )

    assert result.decision == MemoryDecision.AMBIGUOUS


def test_pending_approval_persists_memory_and_audits(
    monkeypatch,
    tmp_path,
) -> None:
    from services.agent import nodes

    store = MemoryStore(tmp_path)
    proposal = build_proposal(conversation_id="conv-approve")
    store.save_pending(proposal)

    monkeypatch.setattr(nodes, "MemoryStore", lambda: store)
    monkeypatch.setattr(
        nodes,
        "classify_memory_decision",
        lambda **kwargs: MemoryDecisionResult(
            decision=MemoryDecision.APPROVE,
            confidence=0.99,
        ),
    )

    result = nodes.resolve_pending_memory_node(
        {
            "conversation_id": "conv-approve",
            "question": "Yes, remember it.",
        }
    )

    assert result["memory_status"] == "approved"
    assert store.get_pending("conv-approve") is None
    assert len(store.list_memories()) == 1

    audit = store.list_audit_records()
    assert len(audit) == 1
    assert audit[0].outcome == ProposalStatus.APPROVED


def test_pending_rejection_does_not_persist_memory(
    monkeypatch,
    tmp_path,
) -> None:
    from services.agent import nodes

    store = MemoryStore(tmp_path)
    proposal = build_proposal(conversation_id="conv-reject")
    store.save_pending(proposal)

    monkeypatch.setattr(nodes, "MemoryStore", lambda: store)
    monkeypatch.setattr(
        nodes,
        "classify_memory_decision",
        lambda **kwargs: MemoryDecisionResult(
            decision=MemoryDecision.REJECT,
            confidence=0.99,
        ),
    )

    result = nodes.resolve_pending_memory_node(
        {
            "conversation_id": "conv-reject",
            "question": "No, don't save that.",
        }
    )

    assert result["memory_status"] == "rejected"
    assert store.list_memories() == []
    assert store.get_pending("conv-reject") is None

    audit = store.list_audit_records()
    assert audit[0].outcome == ProposalStatus.REJECTED


def test_ambiguous_pending_response_is_discarded(
    monkeypatch,
    tmp_path,
) -> None:
    from services.agent import nodes

    store = MemoryStore(tmp_path)
    proposal = build_proposal(conversation_id="conv-ambiguous")
    store.save_pending(proposal)

    monkeypatch.setattr(nodes, "MemoryStore", lambda: store)
    monkeypatch.setattr(
        nodes,
        "classify_memory_decision",
        lambda **kwargs: MemoryDecisionResult(
            decision=MemoryDecision.AMBIGUOUS,
            confidence=0.50,
        ),
    )

    result = nodes.resolve_pending_memory_node(
        {
            "conversation_id": "conv-ambiguous",
            "question": "Maybe.",
        }
    )

    assert result["memory_status"] == "discarded_ambiguous"
    assert store.list_memories() == []
    assert store.get_pending("conv-ambiguous") is None

    audit = store.list_audit_records()
    assert audit[0].outcome == ProposalStatus.DISCARDED
    assert audit[0].user_decision == MemoryDecision.AMBIGUOUS


def test_recall_returns_relevant_approved_memory() -> None:
    """Approved carrier memory should be recalled for a related later query."""
    with TemporaryDirectory() as tmp:
        store = MemoryStore(tmp)

        proposal = build_proposal(
            content="SEUR no longer covers rural Zaragoza.",
            country="ES",
            carrier="SEUR",
        )

        store.write_memory(proposal)

        recalled = store.recall_relevant(
            "Does SEUR still cover rural Zaragoza?"
        )

        assert len(recalled) == 1
        assert recalled[0].content == proposal.content


def test_recall_ignores_unrelated_memory() -> None:
    """Stored memory should not be injected into unrelated conversations."""
    with TemporaryDirectory() as tmp:
        store = MemoryStore(tmp)

        proposal = build_proposal(
            content="SEUR no longer covers rural Zaragoza.",
            country="ES",
            carrier="SEUR",
        )

        store.write_memory(proposal)

        recalled = store.recall_relevant(
            "What is the standard return window?"
        )

        assert recalled == []


def test_rejected_proposal_is_never_recalled() -> None:
    """A rejected proposal must not become usable persistent memory."""
    with TemporaryDirectory() as tmp:
        store = MemoryStore(tmp)

        proposal = build_proposal(
            conversation_id="rejected-recall",
        )

        store.save_pending(proposal)
        store.discard_pending(proposal.conversation_id)

        recalled = store.recall_relevant(
            "Does SEUR cover rural Zaragoza?"
        )

        assert recalled == []


def test_full_approved_memory_cycle_recall(
    monkeypatch,
    tmp_path,
) -> None:
    """Approved memory should persist and be recalled in a later interaction."""
    from services.agent import nodes

    store = MemoryStore(tmp_path)

    proposal = build_proposal(
        conversation_id="conv-full-approve",
        content="SEUR no longer covers rural Zaragoza.",
        country="ES",
        carrier="SEUR",
    )

    store.save_pending(proposal)

    monkeypatch.setattr(nodes, "MemoryStore", lambda: store)
    monkeypatch.setattr(
        nodes,
        "classify_memory_decision",
        lambda **kwargs: MemoryDecisionResult(
            decision=MemoryDecision.APPROVE,
            confidence=0.99,
        ),
    )

    resolution = nodes.resolve_pending_memory_node(
        {
            "conversation_id": "conv-full-approve",
            "question": "Yes, remember that.",
        }
    )

    assert resolution["memory_status"] == "approved"

    recall = nodes.recall_memory_node(
        {
            "question": "Does SEUR still cover rural Zaragoza?",
            "conversation_id": "future-conversation",
        }
    )

    assert len(recall["recalled_memories"]) == 1
    assert "SEUR no longer covers rural Zaragoza." in recall["memory_context"]


def test_full_rejected_memory_cycle_not_recalled(
    monkeypatch,
    tmp_path,
) -> None:
    """Rejected proposals must never influence later conversations."""
    from services.agent import nodes

    store = MemoryStore(tmp_path)

    proposal = build_proposal(
        conversation_id="conv-full-reject",
        content="SEUR no longer covers rural Zaragoza.",
        country="ES",
        carrier="SEUR",
    )

    store.save_pending(proposal)

    monkeypatch.setattr(nodes, "MemoryStore", lambda: store)
    monkeypatch.setattr(
        nodes,
        "classify_memory_decision",
        lambda **kwargs: MemoryDecisionResult(
            decision=MemoryDecision.REJECT,
            confidence=0.99,
        ),
    )

    resolution = nodes.resolve_pending_memory_node(
        {
            "conversation_id": "conv-full-reject",
            "question": "No, do not remember that.",
        }
    )

    assert resolution["memory_status"] == "rejected"

    recall = nodes.recall_memory_node(
        {
            "question": "Does SEUR still cover rural Zaragoza?",
            "conversation_id": "future-conversation",
        }
    )

    assert recall["recalled_memories"] == []
    assert recall["memory_context"] == ""


def test_cleanup_deactivates_expired_recurring_incident() -> None:
    """Expired recurring incident memory should be deactivated by cleanup."""
    from datetime import timedelta

    with TemporaryDirectory() as tmp:
        store = MemoryStore(tmp)

        proposal = build_proposal(
            memory_type=MemoryType.RECURRING_INCIDENT,
            content=(
                "Los Angeles delays this week are caused by the port strike."
            ),
            country="US",
            carrier=None,
            reason="Repeated incident pattern across multiple tickets.",
        )

        record = store.write_memory(proposal)
        record.expires_at = utc_now() - timedelta(minutes=1)

        store.replace_memories([record])

        changed = store.cleanup()

        assert changed == 1

        all_memories = store.list_memories()

        assert len(all_memories) == 1
        assert all_memories[0].active is False

        assert store.read_memories() == []


def test_cleanup_keeps_nonexpired_memory_active() -> None:
    """Cleanup must not remove valid long-lived carrier memory."""
    with TemporaryDirectory() as tmp:
        store = MemoryStore(tmp)

        proposal = build_proposal(
            content="SEUR no longer covers rural Zaragoza.",
            country="ES",
            carrier="SEUR",
        )

        store.write_memory(proposal)

        changed = store.cleanup()

        assert changed == 0

        active = store.read_memories(
            memory_type=MemoryType.CARRIER_RULE,
            country="ES",
            carrier="SEUR",
        )

        assert len(active) == 1
        assert active[0].active is True


def test_approval_with_follow_up_continues_conversation(
    monkeypatch,
    tmp_path,
) -> None:
    """Approval plus a new question should save memory and continue."""
    from services.agent import nodes

    store = MemoryStore(tmp_path)
    proposal = build_proposal(
        conversation_id="conv-approve-followup",
    )
    store.save_pending(proposal)

    monkeypatch.setattr(nodes, "MemoryStore", lambda: store)
    monkeypatch.setattr(
        nodes,
        "classify_memory_decision",
        lambda **kwargs: MemoryDecisionResult(
            decision=MemoryDecision.APPROVE,
            confidence=0.99,
            follow_up_question="What is the standard return policy?",
        ),
    )

    result = nodes.resolve_pending_memory_node(
        {
            "conversation_id": "conv-approve-followup",
            "question": (
                "Yes, remember that. "
                "Also, what is the standard return policy?"
            ),
        }
    )

    assert result["memory_status"] == "approved_followup"
    assert result["question"] == "What is the standard return policy?"
    assert "saved that" in result["memory_notice"]
    assert len(store.list_memories()) == 1
    assert store.get_pending("conv-approve-followup") is None

    assert nodes.route_after_pending_memory(result) == "continue"


def test_rejection_with_follow_up_continues_without_saving(
    monkeypatch,
    tmp_path,
) -> None:
    """Rejection plus a new question should continue without persistence."""
    from services.agent import nodes

    store = MemoryStore(tmp_path)
    proposal = build_proposal(
        conversation_id="conv-reject-followup",
    )
    store.save_pending(proposal)

    monkeypatch.setattr(nodes, "MemoryStore", lambda: store)
    monkeypatch.setattr(
        nodes,
        "classify_memory_decision",
        lambda **kwargs: MemoryDecisionResult(
            decision=MemoryDecision.REJECT,
            confidence=0.99,
            follow_up_question="What is the standard return policy?",
        ),
    )

    result = nodes.resolve_pending_memory_node(
        {
            "conversation_id": "conv-reject-followup",
            "question": (
                "No, don't remember that. "
                "What is the standard return policy?"
            ),
        }
    )

    assert result["memory_status"] == "rejected_followup"
    assert result["question"] == "What is the standard return policy?"
    assert "did not save" in result["memory_notice"]
    assert store.list_memories() == []
    assert store.get_pending("conv-reject-followup") is None

    assert nodes.route_after_pending_memory(result) == "continue"


def test_pending_proposal_is_logged_when_created(
    monkeypatch,
    tmp_path,
) -> None:
    """Creating a pending proposal must immediately leave an audit record."""
    from services.agent import nodes

    store = MemoryStore(tmp_path)

    proposal = build_proposal(
        conversation_id="conv-proposal-audit",
        content="SEUR no longer covers rural Zaragoza.",
        country="ES",
        carrier="SEUR",
    )

    monkeypatch.setattr(nodes, "MemoryStore", lambda: store)

    result = nodes.memory_evaluation_node(
        {
            "question": proposal.originating_message,
            "answer": "Thanks for the correction.",
            "conversation_id": proposal.conversation_id,
            "memory_proposal": proposal.model_dump(mode="json"),
        }
    )

    assert result["memory_status"] == "pending"

    audit = store.list_audit_records()

    assert len(audit) == 1
    assert audit[0].proposal_id == proposal.proposal_id
    assert audit[0].outcome == ProposalStatus.PENDING
    assert audit[0].originating_message == proposal.originating_message
    assert audit[0].proposed_at == proposal.created_at


def test_generation_prompt_prioritizes_rag_and_mcp_over_memory(
    monkeypatch,
) -> None:
    """Approved memory must never outrank trusted RAG or live MCP facts."""
    from services.agent.memory import evaluator as evaluator_module

    captured = {}

    class FakeMessage:
        content = (
            '{"answer":"Use the trusted source.",'
            '"memory_proposal":{"should_propose":false,'
            '"memory_type":null,"content":null,"country":null,'
            '"carrier":null,"b2b_client":null,'
            '"reason":"Nothing durable to remember."}}'
        )

    class FakeChoice:
        message = FakeMessage()

    class FakeResponse:
        choices = [FakeChoice()]

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return FakeResponse()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    monkeypatch.setattr(
        evaluator_module,
        "_openai_client",
        lambda: FakeClient(),
    )
    monkeypatch.setattr(
        evaluator_module,
        "_required_env",
        lambda name: "test-model",
    )

    answer, proposal = evaluator_module.generate_with_memory(
        question="Which source should I trust?",
        context=(
            "APPROVED TRACKFLOW MEMORY:\n"
            "1. Old remembered rule.\n\n"
            "KNOWLEDGE BASE CONTEXT:\n"
            "Current approved policy."
        ),
        conversation_id="conv-trust",
    )

    messages = captured["messages"]
    prompt_text = "\n".join(
        message["content"]
        for message in messages
    )

    assert "LIVE INCIDENT DATA from MCP is authoritative" in prompt_text
    assert "KNOWLEDGE BASE CONTEXT" in prompt_text
    assert "APPROVED TRACKFLOW MEMORY is advisory context only" in prompt_text
    assert "ignore the conflicting memory" in prompt_text

    assert answer == "Use the trusted source."
    assert proposal is None
