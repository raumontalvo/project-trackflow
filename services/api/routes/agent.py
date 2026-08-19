"""HTTP routes for the TrackFlow LangGraph agent."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from services.agent.graph import run_agent
from services.agent.trace import get_guardrail_summary
from services.api.auth import get_current_user


router = APIRouter(prefix="/agent", tags=["agent"])


class AgentQueryRequest(BaseModel):
    """Request body for a TrackFlow agent question."""

    question: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        examples=["What is the standard return window?"],
    )


class AgentQueryResponse(BaseModel):
    """Final response returned by the LangGraph agent."""

    run_id: str
    answer: str
    error: str | None = None


@router.post("/query", response_model=AgentQueryResponse)
async def ask_agent(
    request: AgentQueryRequest,
    current_user: dict = Depends(get_current_user),
) -> AgentQueryResponse:
    """Run the compiled TrackFlow LangGraph agent."""
    try:
        result = await run_agent(
            request.question,
            authenticated_user=current_user,
        )

        return AgentQueryResponse(
            run_id=result["run_id"],
            answer=result.get("answer", ""),
            error=result.get("error"),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="The TrackFlow agent could not answer the question.",
        ) from exc


@router.get("/guardrails/summary")
def guardrail_summary() -> dict:
    """Return aggregate TrackFlow guardrail observability metrics."""
    return get_guardrail_summary()