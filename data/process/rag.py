"""TrackFlow knowledge-base preparation and Qdrant indexing."""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = PROJECT_ROOT / ".env"
KNOWLEDGE_BASE_DIR = PROJECT_ROOT / "docs" / "company-knowledge-base"

COMPANY = "trackflow"
LANGUAGE = "en"

DOCUMENT_IDS = {
    "trackflow-sla-delivery.en.md": "sla-delivery",
    "trackflow-returns-policy.en.md": "returns-policy",
    "trackflow-carrier-coverage.en.md": "carrier-coverage",
    "trackflow-storage-pricing.en.md": "storage-pricing",
}

load_dotenv(ENV_PATH)


def _required_env(name: str) -> str:
    """Return a required environment variable or raise a clear error."""
    value = os.getenv(name, "").strip()

    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            f"Add it to {ENV_PATH}."
        )

    return value


def _openai_client() -> OpenAI:
    """Create the OpenAI-compatible client for the 4Geeks gateway."""
    base_url = _required_env("OPENAI_BASE_URL").rstrip("/")

    # OpenAI-compatible gateways normally expose routes under /v1.
    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"

    return OpenAI(
        api_key=_required_env("OPENAI_API_KEY"),
        base_url=base_url,
    )


def _qdrant_client() -> QdrantClient:
    """Create the Qdrant client from environment configuration."""
    api_key = os.getenv("QDRANT_API_KEY", "").strip() or None

    return QdrantClient(
        url=_required_env("QDRANT_URL"),
        api_key=api_key,
    )


def _normalize_markdown_block(block: str) -> str:
    """
    Normalize hard-wrapped Markdown while preserving list items.

    Consecutive wrapped lines are combined into complete paragraphs.
    Bullet and numbered-list boundaries are preserved.
    """
    normalized_lines: list[str] = []
    current_line = ""

    for raw_line in block.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        is_list_item = bool(re.match(r"^(?:[-*+]|\d+\.)\s+", line))

        if is_list_item:
            if current_line:
                normalized_lines.append(current_line.strip())
                current_line = ""
            normalized_lines.append(line)
        else:
            if current_line:
                current_line = f"{current_line} {line}"
            else:
                current_line = line

    if current_line:
        normalized_lines.append(current_line.strip())

    return "\n".join(normalized_lines).strip()


def _parse_markdown(path: Path) -> tuple[str, list[str]]:
    """
    Parse one Markdown document into a title and semantic chunks.

    Blank-line-separated blocks are used because each TrackFlow document
    groups complete business rules and conditions into coherent paragraphs.
    """
    content = path.read_text(encoding="utf-8").strip()

    if not content:
        raise ValueError(f"Knowledge-base document is empty: {path}")

    lines = content.splitlines()
    title = path.stem

    if lines and lines[0].startswith("# "):
        title = lines[0][2:].strip()
        body = "\n".join(lines[1:]).strip()
    else:
        body = content

    raw_blocks = re.split(r"\n\s*\n", body)

    chunks = [
        _normalize_markdown_block(block)
        for block in raw_blocks
        if _normalize_markdown_block(block)
    ]

    if len(chunks) < 3:
        raise ValueError(
            f"{path.name} produced only {len(chunks)} chunks; "
            "TrackFlow requires at least 3 chunks per document."
        )

    return title, chunks


def load_chunks() -> list[dict[str, Any]]:
    """Load and semantically split all required TrackFlow documents."""
    if not KNOWLEDGE_BASE_DIR.exists():
        raise FileNotFoundError(
            f"Knowledge-base directory not found: {KNOWLEDGE_BASE_DIR}"
        )

    chunks: list[dict[str, Any]] = []

    for filename, source_document in DOCUMENT_IDS.items():
        path = KNOWLEDGE_BASE_DIR / filename

        if not path.exists():
            raise FileNotFoundError(f"Required source document missing: {path}")

        title, document_chunks = _parse_markdown(path)

        for chunk_index, text in enumerate(document_chunks):
            chunks.append(
                {
                    "company": COMPANY,
                    "source_document": source_document,
                    "section": title,
                    "language": LANGUAGE,
                    "chunk_index": chunk_index,
                    "text": text,
                }
            )

    return chunks


def embed(text: str) -> list[float]:
    """Generate an embedding vector for one text value."""
    cleaned_text = text.strip()

    if not cleaned_text:
        raise ValueError("Cannot embed empty text.")

    response = _openai_client().embeddings.create(
        model=_required_env("EMBEDDING_MODEL"),
        input=cleaned_text,
    )

    vector = response.data[0].embedding

    if not vector:
        raise RuntimeError("The embeddings model returned an empty vector.")

    return vector


def _deterministic_point_id(
    source_document: str,
    chunk_index: int,
) -> str:
    """Create a stable UUID so repeated setup runs cannot duplicate points."""
    stable_name = f"{COMPANY}:{source_document}:{chunk_index}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, stable_name))


def setup() -> dict[str, Any]:
    """
    Recreate and populate the TrackFlow Qdrant collection.

    The clear-and-reload strategy makes setup idempotent during development.
    """
    collection_name = _required_env("QDRANT_COLLECTION")
    chunks = load_chunks()

    if not chunks:
        raise RuntimeError("No knowledge-base chunks were generated.")

    vectors = [embed(chunk["text"]) for chunk in chunks]
    vector_size = len(vectors[0])

    if any(len(vector) != vector_size for vector in vectors):
        raise RuntimeError("Embedding vectors have inconsistent dimensions.")

    qdrant = _qdrant_client()

    if qdrant.collection_exists(collection_name):
        qdrant.delete_collection(collection_name)

    qdrant.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=vector_size,
            distance=Distance.COSINE,
        ),
    )

    points = [
        PointStruct(
            id=_deterministic_point_id(
                chunk["source_document"],
                chunk["chunk_index"],
            ),
            vector=vector,
            payload=chunk,
        )
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]

    qdrant.upsert(
        collection_name=collection_name,
        points=points,
        wait=True,
    )

    return {
        "collection_name": collection_name,
        "chunk_count": len(points),
        "vector_size": vector_size,
        "documents": len(DOCUMENT_IDS),
    }


if __name__ == "__main__":
    result = setup()
    print("TrackFlow knowledge base indexed successfully:")
    print(result)
