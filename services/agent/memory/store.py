"""Persistent TrackFlow agent memory store with audit logging and consolidation."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Iterable

from services.agent.memory.models import (
    MemoryAuditRecord,
    MemoryProposal,
    MemoryRecord,
    MemoryType,
    ProposalStatus,
    utc_now,
)


DEFAULT_MEMORY_PATH = Path("data/agent_memory")


class MemoryStore:
    """Explicit read/write interface for TrackFlow persistent memory."""

    def __init__(self, base_path: Path | str = DEFAULT_MEMORY_PATH) -> None:
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

        self.memories_path = self.base_path / "memories.json"
        self.pending_path = self.base_path / "pending.json"
        self.audit_path = self.base_path / "audit.jsonl"

        self._ensure_files()

    def _ensure_files(self) -> None:
        if not self.memories_path.exists():
            self.memories_path.write_text("[]", encoding="utf-8")

        if not self.pending_path.exists():
            self.pending_path.write_text("{}", encoding="utf-8")

        if not self.audit_path.exists():
            self.audit_path.touch()

    def _read_json(self, path: Path, default):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, FileNotFoundError):
            return default

    def _write_json(self, path: Path, payload) -> None:
        path.write_text(
            json.dumps(payload, indent=2, default=str),
            encoding="utf-8",
        )

    def list_memories(self) -> list[MemoryRecord]:
        """Return all persistent memories."""
        raw = self._read_json(self.memories_path, [])
        return [MemoryRecord.model_validate(item) for item in raw]

    def read_memories(
        self,
        *,
        memory_type: MemoryType | None = None,
        country: str | None = None,
        carrier: str | None = None,
        b2b_client: str | None = None,
        active_only: bool = True,
    ) -> list[MemoryRecord]:
        """Read memories matching optional structured filters."""
        records = self.list_memories()

        def matches(record: MemoryRecord) -> bool:
            if active_only and not record.active:
                return False
            if memory_type is not None and record.memory_type != memory_type:
                return False
            if country is not None and record.country != country:
                return False
            if carrier is not None and record.carrier != carrier:
                return False
            if b2b_client is not None and record.b2b_client != b2b_client:
                return False
            if record.expires_at is not None and record.expires_at <= utc_now():
                return False
            return True

        return [record for record in records if matches(record)]

    def write_memory(self, proposal: MemoryProposal) -> MemoryRecord:
        """Persist an approved proposal, consolidating where appropriate."""

        expires_at = None

        if proposal.memory_type == MemoryType.RECURRING_INCIDENT:
            expires_at = utc_now() + timedelta(days=14)

        new_record = MemoryRecord(
            memory_type=proposal.memory_type,
            content=proposal.content,
            country=proposal.country,
            carrier=proposal.carrier,
            b2b_client=proposal.b2b_client,
            source_proposal_id=proposal.proposal_id,
            expires_at=expires_at,
        )

        memories = self.list_memories()

        consolidated = False

        for index, existing in enumerate(memories):
            if self._same_memory_scope(existing, new_record):
                new_record.memory_id = existing.memory_id
                new_record.created_at = existing.created_at
                new_record.updated_at = utc_now()
                memories[index] = new_record
                consolidated = True
                break

        if not consolidated:
            memories.append(new_record)

        self._write_json(
            self.memories_path,
            [memory.model_dump(mode="json") for memory in memories],
        )

        return new_record

    def _same_memory_scope(
        self,
        existing: MemoryRecord,
        incoming: MemoryRecord,
    ) -> bool:
        """Determine whether a new memory should replace an older one."""

        if existing.memory_type != incoming.memory_type:
            return False

        if incoming.memory_type == MemoryType.CARRIER_RULE:
            return (
                existing.country == incoming.country
                and existing.carrier == incoming.carrier
            )

        if incoming.memory_type == MemoryType.B2B_REPORT_PREFERENCE:
            return existing.b2b_client == incoming.b2b_client

        return False

    def save_pending(self, proposal: MemoryProposal) -> None:
        """Store at most one pending proposal per conversation."""
        pending = self._read_json(self.pending_path, {})
        pending[proposal.conversation_id] = proposal.model_dump(mode="json")
        self._write_json(self.pending_path, pending)

    def get_pending(self, conversation_id: str) -> MemoryProposal | None:
        """Return the pending proposal for a conversation, if one exists."""
        pending = self._read_json(self.pending_path, {})
        raw = pending.get(conversation_id)

        if raw is None:
            return None

        return MemoryProposal.model_validate(raw)

    def discard_pending(self, conversation_id: str) -> None:
        """Remove a pending proposal without approving it."""
        pending = self._read_json(self.pending_path, {})
        pending.pop(conversation_id, None)
        self._write_json(self.pending_path, pending)

    def append_audit(self, record: MemoryAuditRecord) -> None:
        """Append an immutable proposal decision record."""
        with self.audit_path.open("a", encoding="utf-8") as file:
            file.write(
                json.dumps(record.model_dump(mode="json"), default=str) + "\n"
            )

    def list_audit_records(self) -> list[MemoryAuditRecord]:
        """Return all audit records."""
        records: list[MemoryAuditRecord] = []

        if not self.audit_path.exists():
            return records

        for line in self.audit_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue

            records.append(
                MemoryAuditRecord.model_validate(json.loads(line))
            )

        return records

    def cleanup(self) -> int:
        """Deactivate expired recurring-incident memories."""
        memories = self.list_memories()
        now = utc_now()
        changed = 0

        for memory in memories:
            if (
                memory.active
                and memory.expires_at is not None
                and memory.expires_at <= now
            ):
                memory.active = False
                memory.updated_at = now
                changed += 1

        if changed:
            self._write_json(
                self.memories_path,
                [memory.model_dump(mode="json") for memory in memories],
            )

        return changed

    def recall_relevant(
        self,
        query: str,
        *,
        limit: int = 5,
    ) -> list[MemoryRecord]:
        """Recall active memories relevant to the current user query."""

        query_terms = {
            term
            for term in query.lower().replace("-", " ").split()
            if len(term) >= 3
        }

        if not query_terms:
            return []

        scored: list[tuple[int, MemoryRecord]] = []

        for memory in self.read_memories():
            searchable = " ".join(
                value
                for value in (
                    memory.content,
                    memory.country,
                    memory.carrier,
                    memory.b2b_client,
                )
                if value
            ).lower().replace("-", " ")

            score = sum(
                1
                for term in query_terms
                if term in searchable
            )

            if score > 0:
                scored.append((score, memory))

        scored.sort(
            key=lambda item: (
                item[0],
                item[1].updated_at,
            ),
            reverse=True,
        )

        return [
            memory
            for _, memory in scored[:limit]
        ]



    def replace_memories(self, records: Iterable[MemoryRecord]) -> None:
        """Testing helper for explicitly replacing persistent memory state."""
        self._write_json(
            self.memories_path,
            [record.model_dump(mode="json") for record in records],
        )
