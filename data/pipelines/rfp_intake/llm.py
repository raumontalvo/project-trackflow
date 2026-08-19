"""OpenAI-compatible client helpers for the TrackFlow RFP intake pipeline."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ENV_PATH = PROJECT_ROOT / ".env"

load_dotenv(ENV_PATH)


def required_env(name: str) -> str:
    """Return a required environment variable or raise a useful error."""

    value = os.getenv(name, "").strip()

    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            f"Add it to {ENV_PATH}."
        )

    return value


def openai_client() -> OpenAI:
    """Create the OpenAI-compatible client used by TrackFlow."""

    base_url = required_env("OPENAI_BASE_URL").rstrip("/")

    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"

    return OpenAI(
        api_key=required_env("OPENAI_API_KEY"),
        base_url=base_url,
    )


def generation_model() -> str:
    """Return the configured generation model."""

    return required_env("GENERATION_MODEL")