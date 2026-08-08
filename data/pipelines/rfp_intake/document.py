"""Document ingestion helpers for the TrackFlow RFP intake pipeline."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from markitdown import MarkItDown
from readability import Readability


def convert_pdf_to_markdown(pdf_path: str | Path) -> str:
    """
    Convert an uploaded PDF to Markdown before any LLM reads it.

    Raises:
        FileNotFoundError: if the PDF does not exist.
        ValueError: if the path is not a PDF or conversion returns no text.
    """

    path = Path(pdf_path)

    if not path.exists():
        raise FileNotFoundError(f"RFP PDF not found: {path}")

    if path.suffix.lower() != ".pdf":
        raise ValueError("RFP intake only accepts PDF documents.")

    converter = MarkItDown()
    result = converter.convert(str(path))

    markdown = (result.text_content or "").strip()

    if not markdown:
        raise ValueError(
            f"PDF conversion produced no readable Markdown: {path}"
        )

    return markdown


def calculate_readability(markdown: str) -> dict[str, Any]:
    """
    Calculate readability metrics from converted Markdown.

    Readability metrics are used as processing-complexity indicators,
    not as judgments of writing quality.

    Some py-readability-metrics formulas can fail on short or unusual
    documents, so each metric is calculated independently.
    """

    text = markdown.strip()

    metrics: dict[str, Any] = {
        "flesch_reading_ease": None,
        "flesch_kincaid_grade": None,
        "gunning_fog": None,
        "coleman_liau": None,
        "word_count": len(text.split()) if text else 0,
    }

    if not text:
        return metrics

    try:
        readability = Readability(text)

    except LookupError as exc:
        raise RuntimeError(
            "NLTK tokenizer data is missing. "
            "Run: uv run python -m nltk.downloader punkt_tab"
        ) from exc

    except Exception:
        return metrics

    try:
        metrics["flesch_reading_ease"] = float(
            readability.flesch().score
        )
    except Exception:
        pass

    try:
        metrics["flesch_kincaid_grade"] = float(
            readability.flesch_kincaid().score
        )
    except Exception:
        pass

    try:
        metrics["gunning_fog"] = float(
            readability.gunning_fog().score
        )
    except Exception:
        pass

    try:
        metrics["coleman_liau"] = float(
            readability.coleman_liau().score
        )
    except Exception:
        pass

    return metrics


def process_document(
    pdf_path: str | Path,
) -> tuple[str, dict[str, Any]]:
    """
    Convert a PDF to Markdown and calculate readability metrics.

    Returns:
        tuple:
            - converted Markdown text
            - readability metrics
    """

    markdown = convert_pdf_to_markdown(pdf_path)
    readability_metrics = calculate_readability(markdown)

    return markdown, readability_metrics