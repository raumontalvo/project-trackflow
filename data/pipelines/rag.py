"""TrackFlow RAG retrieval and answer-generation pipeline."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient

from data.process.rag import embed


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"

load_dotenv(ENV_PATH)

DEFAULT_TOP_K = 3
DEFAULT_SCORE_THRESHOLD = 0.30

NO_CONTEXT_ANSWER = (
    "I couldn't find enough approved TrackFlow information to answer "
    "that confidently. Please confirm the request with the appropriate "
    "operations owner before making a commitment to the client."
)


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()

    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            f"Add it to {ENV_PATH}."
        )

    return value


def _openai_client() -> OpenAI:
    base_url = _required_env("OPENAI_BASE_URL").rstrip("/")

    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"

    return OpenAI(
        api_key=_required_env("OPENAI_API_KEY"),
        base_url=base_url,
    )


def _qdrant_client() -> QdrantClient:
    api_key = os.getenv("QDRANT_API_KEY", "").strip() or None

    return QdrantClient(
        url=_required_env("QDRANT_URL"),
        api_key=api_key,
    )


def retrieve(
    query: str,
    *,
    k: int = 5,
    min_score: float = DEFAULT_SCORE_THRESHOLD,
) -> list[dict[str, Any]]:
    """Retrieve the most relevant TrackFlow knowledge-base chunks."""
    cleaned_query = query.strip()

    if not cleaned_query:
        raise ValueError("Query cannot be empty.")

    if k < 1:
        raise ValueError("k must be at least 1.")

    if not 0.0 <= min_score <= 1.0:
        raise ValueError("min_score must be between 0 and 1.")

    query_vector = embed(cleaned_query)

    response = _qdrant_client().query_points(
        collection_name=_required_env("QDRANT_COLLECTION"),
        query=query_vector,
        limit=k,
        score_threshold=min_score,
        with_payload=True,
        with_vectors=False,
    )

    results: list[dict[str, Any]] = []

    for point in response.points:
        payload = point.payload or {}

        results.append(
            {
                "id": str(point.id),
                "score": float(point.score),
                "company": payload.get("company"),
                "source_document": payload.get("source_document"),
                "section": payload.get("section"),
                "language": payload.get("language"),
                "chunk_index": payload.get("chunk_index"),
                "text": payload.get("text", ""),
            }
        )

    return results


def build_context(chunks: list[dict[str, Any]]) -> str:
    """Format retrieved chunks for the generation prompt."""
    context_parts: list[str] = []

    for index, chunk in enumerate(chunks, start=1):
        context_parts.append(
            "\n".join(
                [
                    f"[Source {index}]",
                    f"Document: {chunk['source_document']}",
                    f"Section: {chunk['section']}",
                    f"Chunk index: {chunk['chunk_index']}",
                    f"Content: {chunk['text']}",
                ]
            )
        )

    return "\n\n".join(context_parts)


def generate_answer(
    question: str,
    context: str,
) -> str:
    """
    Generate the final salesperson-ready answer from already-retrieved context.

    This function performs generation only and never runs retrieval.
    """
    cleaned_question = question.strip()
    cleaned_context = context.strip()

    if not cleaned_question:
        raise ValueError("Question cannot be empty.")

    if not cleaned_context:
        return NO_CONTEXT_ANSWER

    system_prompt = """
You are TrackFlow's internal commercial knowledge assistant.

Answer from the perspective of a careful TrackFlow salesperson speaking with
a prospect or client. Use only the retrieved context. Never invent conditions,
discounts, carrier exceptions, percentages, rates, compensation, delivery
times, or approval rules.

Mandatory business constraints:
- Never promise a delivery SLA during declared high-demand dates such as
  Black Friday, Christmas, or January Sales in Spain.
- International returns are not automatic and must always be described as
  requiring manual handling by Sofía Ramos's team.
- Storage discounts or preferential rates must always mention that negotiation
  requires Miguel Torres's approval.
- Manual carrier selection is only an exception approved by Carlos Vega.
- If the retrieved context does not support the requested condition, say that
  approval or confirmation is required rather than guessing.

Keep the answer concise, client-ready, accurate, and commercially helpful.
Do not mention vector databases, embeddings, retrieval scores, or internal
implementation details.
""".strip()

    user_prompt = f"""
Question:
{cleaned_question}

Retrieved TrackFlow context:
{cleaned_context}

Generate the final answer using only that context.
""".strip()

    response = _openai_client().chat.completions.create(
        model=_required_env("GENERATION_MODEL"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
    )

    answer = response.choices[0].message.content

    if not answer:
        raise RuntimeError("The generation model returned an empty answer.")

    return answer.strip()


def query(question: str) -> str:
    """
    Retrieve relevant context and generate the final salesperson-ready answer.

    External consumers receive only the generated answer string.
    """
    chunks = retrieve(
        question,
        k=DEFAULT_TOP_K,
        min_score=DEFAULT_SCORE_THRESHOLD,
    )

    context = build_context(chunks)

    return generate_answer(question, context)


if __name__ == "__main__":
    test_question = "What is the standard return window?"
    answer = query(test_question)

    print(f"Question: {test_question}")
    print(f"Answer: {answer}")