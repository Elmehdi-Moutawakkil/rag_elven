"""Shared runtime settings for RAGElven.

This module centralizes model names, environment variable names, and project
paths. It intentionally avoids importing third-party SDKs so it is safe to use
from tests, scripts, Streamlit, and inspector code.
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*_args, **_kwargs):
        return False

load_dotenv(PROJECT_ROOT / ".env")

DATA_DIR = PROJECT_ROOT / "data"
VECTOR_DB_DIR = PROJECT_ROOT / "vector_db"

ELVISH_INDEX_PATH = VECTOR_DB_DIR / "faiss.index"
ELVISH_METADATA_PATH = VECTOR_DB_DIR / "metadata.json"
ELVISH_DICTIONARY_DB_PATH = VECTOR_DB_DIR / "dictionary.sqlite"
ELVISH_KG_DB_PATH = VECTOR_DB_DIR / "knowledge_graph.sqlite"

GROQ_API_KEY_ENV = "GROQ_API_KEY"
ANTHROPIC_API_KEY_ENV = "ANTHROPIC_API_KEY"

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
ANTHROPIC_LORE_MODEL = os.getenv("ANTHROPIC_LORE_MODEL", "claude-sonnet-4-6")
ANTHROPIC_POLISH_MODEL = os.getenv("ANTHROPIC_POLISH_MODEL", "claude-haiku-4-5-20251001")
ANTHROPIC_JUDGE_MODEL = os.getenv("ANTHROPIC_JUDGE_MODEL", "claude-sonnet-4-6")

LM_STUDIO_BASE_URL = os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1")
LOCAL_MODEL_NAME = os.getenv("LOCAL_MODEL_NAME", "local-model")


def env_value(name: str) -> str:
    """Return a stripped environment variable value, or an empty string."""
    return os.getenv(name, "").strip()


def has_env(name: str) -> bool:
    """True when an environment variable is present and non-empty."""
    return bool(env_value(name))


def missing_key_message(env_name: str, feature: str) -> str:
    """Human-readable API key error without leaking secret values."""
    return (
        f"{env_name} manquante pour {feature}. "
        "Ajoute-la dans .env en local ou dans Streamlit Secrets en deploiement."
    )
