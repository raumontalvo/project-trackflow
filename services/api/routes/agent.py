"""HTTP routes for the TrackFlow LangGraph agent."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.agent.graph import run_agent


router = APIRouter(prefix="/agent", tags=["agent"])


class AgentQueryRequest(BaseModel):
    """Request body for a TrackFlow agent question."""

    question: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        examples=["What is the standard return window?"],
    )
    conversation_id: str | None = Field(
        default=None,
        description=(
            "Stable conversation identifier. Reuse the returned value "
            "on later turns to continue the same agent conversation."
        ),
    )


class AgentQueryResponse(BaseModel):
    """Final response returned by the LangGraph agent."""

    run_id: str
    conversation_id: str
    answer: str
    error: str | None = None


@router.post("/query", response_model=AgentQueryResponse)
async def ask_agent(
    request: AgentQueryRequest,
) -> AgentQueryResponse:
    """Run the compiled TrackFlow LangGraph agent."""
    try:
        result = await run_agent(
            request.question,
            conversation_id=request.conversation_id,
        )

        return AgentQueryResponse(
            run_id=result["run_id"],
            conversation_id=result["conversation_id"],
            answer=result.get("answer", ""),
            error=result.get("error"),
        )

    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="The TrackFlow agent could not answer the question.",
        ) from exc
