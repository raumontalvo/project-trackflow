"""Persistent LangGraph checkpointing for TrackFlow RFP workflows."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

from langgraph.checkpoint.postgres import PostgresSaver

from services.api.database import DATABASE_URL


@contextmanager
def get_rfp_checkpointer() -> Iterator[PostgresSaver]:
    """
    Yield a Postgres-backed LangGraph checkpointer.

    Prepared statements are disabled because Supabase transaction-mode
    pooling does not support them safely across pooled server sessions.
    """

    with psycopg.connect(
        DATABASE_URL,
        autocommit=True,
        row_factory=dict_row,
        prepare_threshold=None,
    ) as connection:
        yield PostgresSaver(connection)


def setup_rfp_checkpointer() -> None:
    """Create or migrate LangGraph checkpoint tables."""

    with psycopg.connect(
        DATABASE_URL,
        autocommit=True,
        row_factory=dict_row,
        prepare_threshold=None,
    ) as connection:
        checkpointer = PostgresSaver(connection)
        checkpointer.setup()


def approval_thread_id(
    ticket_id: str,
) -> str:
    """
    Return the legacy ticket-level approval thread ID.

    Kept for compatibility with checkpoints created before department
    approvals were separated into independent threads.
    """

    return f"rfp-approval-{ticket_id}"


def department_approval_thread_id(
    ticket_id: str,
    department_id: str,
) -> str:
    """
    Return a stable checkpoint identity for one department approval branch.

    Each active department gets an independent LangGraph thread so one
    interrupted human approval cannot block another department from
    continuing through revisions or approval.
    """

    if not ticket_id:
        raise ValueError(
            "ticket_id is required for approval checkpoint identity."
        )

    if not department_id:
        raise ValueError(
            "department_id is required for approval checkpoint identity."
        )

    return (
        f"rfp-approval-{ticket_id}-"
        f"{department_id}"
    )


def approval_config(
    ticket_id: str,
    department_id: str,
) -> dict:
    """Build LangGraph config for one department approval thread."""

    return {
        "configurable": {
            "thread_id": department_approval_thread_id(
                ticket_id,
                department_id,
            )
        }
    }
