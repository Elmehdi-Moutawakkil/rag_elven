"""Read-only project sanity checks.

This script does not call external APIs and does not modify files. It verifies
that local source files parse, core assets are present, SQLite stores are
readable, metadata files are coherent, and optional runtime dependencies/env
vars are visible.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.settings import (  # noqa: E402
    ANTHROPIC_API_KEY_ENV,
    ELVISH_DICTIONARY_DB_PATH,
    ELVISH_INDEX_PATH,
    ELVISH_KG_DB_PATH,
    ELVISH_METADATA_PATH,
    GROQ_API_KEY_ENV,
    has_env,
)


def _status(ok: bool) -> str:
    return "OK" if ok else "WARN"


def _check_python_syntax() -> list[str]:
    errors: list[str] = []
    ignored_dirs = {".git", ".venv", "venv", "__pycache__", ".pytest_cache"}
    for path in sorted(PROJECT_ROOT.rglob("*.py")):
        if ignored_dirs.intersection(path.parts):
            continue
        try:
            ast.parse(path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - diagnostic path
            errors.append(f"{path.relative_to(PROJECT_ROOT)}: {exc}")
    return errors


def _count_table(db_path: Path, table: str) -> int | None:
    if not db_path.exists():
        return None
    with sqlite3.connect(db_path) as conn:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def _json_count(path: Path) -> int | None:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return len(data) if isinstance(data, list) else None


def _dependency_report() -> list[tuple[str, bool]]:
    modules = [
        "streamlit",
        "sentence_transformers",
        "faiss",
        "groq",
        "anthropic",
        "spacy",
        "pypdf",
        "langchain_text_splitters",
        "dotenv",
        "numpy",
        "pytest",
        "openai",
        "ddgs",
    ]
    return [(module, importlib.util.find_spec(module) is not None) for module in modules]


def main() -> int:
    print("RAGElven sanity check")
    print(f"project: {PROJECT_ROOT}")
    print(f"python:  {sys.version.split()[0]}")
    print()

    failures: list[str] = []

    syntax_errors = _check_python_syntax()
    print(f"[{_status(not syntax_errors)}] python syntax: {0 if not syntax_errors else len(syntax_errors)} error(s)")
    if syntax_errors:
        failures.extend(syntax_errors)

    required_files = [
        ELVISH_INDEX_PATH,
        ELVISH_METADATA_PATH,
        ELVISH_DICTIONARY_DB_PATH,
        ELVISH_KG_DB_PATH,
        PROJECT_ROOT / "vector_db" / "terran_empire" / "faiss.index",
        PROJECT_ROOT / "vector_db" / "terran_empire" / "metadata.json",
        PROJECT_ROOT / "vector_db" / "terran_empire" / "knowledge_graph.sqlite",
    ]
    for path in required_files:
        exists = path.exists()
        rel = path.relative_to(PROJECT_ROOT)
        print(f"[{_status(exists)}] asset: {rel}")
        if not exists:
            failures.append(f"missing asset: {rel}")

    print()
    try:
        dict_count = _count_table(ELVISH_DICTIONARY_DB_PATH, "dictionary_entries")
        kg_entities = _count_table(ELVISH_KG_DB_PATH, "entities")
        terran_kg_entities = _count_table(
            PROJECT_ROOT / "vector_db" / "terran_empire" / "knowledge_graph.sqlite",
            "entities",
        )
        print(f"[{_status(dict_count is not None)}] dictionary entries: {dict_count}")
        print(f"[{_status(kg_entities is not None)}] Tolkien KG entities: {kg_entities}")
        print(f"[{_status(terran_kg_entities is not None)}] Terran KG entities: {terran_kg_entities}")
    except Exception as exc:
        failures.append(f"sqlite check failed: {exc}")
        print(f"[WARN] sqlite check failed: {exc}")

    try:
        elvish_chunks = _json_count(ELVISH_METADATA_PATH)
        terran_chunks = _json_count(PROJECT_ROOT / "vector_db" / "terran_empire" / "metadata.json")
        print(f"[{_status(elvish_chunks is not None)}] Tolkien metadata chunks: {elvish_chunks}")
        print(f"[{_status(terran_chunks is not None)}] Terran metadata chunks: {terran_chunks}")
    except Exception as exc:
        failures.append(f"metadata check failed: {exc}")
        print(f"[WARN] metadata check failed: {exc}")

    print()
    for env_name in (GROQ_API_KEY_ENV, ANTHROPIC_API_KEY_ENV):
        print(f"[{_status(has_env(env_name))}] env: {env_name} {'set' if has_env(env_name) else 'missing'}")

    print()
    print("Dependencies (missing entries are expected before `pip install -r requirements.txt`):")
    for module, ok in _dependency_report():
        print(f"[{_status(ok)}] import: {module}")

    if failures:
        print()
        print("Sanity check completed with blocking issue(s):")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print()
    print("Sanity check completed. Missing API keys/dependencies above are warnings unless you are running the app.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
