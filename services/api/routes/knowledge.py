"""HTTP routes for the TrackFlow commercial knowledge assistant."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from data.pipelines.rag import query


router = APIRouter(prefix="/knowledge", tags=["knowledge"])


class KnowledgeQueryRequest(BaseModel):
    """Request body for a TrackFlow knowledge-base question."""

    question: str = Field(
        ...,
        min_length=2,
        max_length=1000,
        examples=["What is the standard return window?"],
    )


class KnowledgeQueryResponse(BaseModel):
    """Generated answer returned to the client."""

    answer: str


@router.post("/query", response_model=KnowledgeQueryResponse)
def ask_knowledge_base(
    request: KnowledgeQueryRequest,
) -> KnowledgeQueryResponse:
    """
    Generate an answer from approved TrackFlow knowledge-base context.

    The client receives only the final model-generated answer.
    """
    try:
        answer = query(request.question)
        return KnowledgeQueryResponse(answer=answer)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="The TrackFlow knowledge assistant could not answer the question.",
        ) from exc
