"""Stable tool handlers intended for MCP exposure."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from src.ingestion.documents import read_documents_jsonl
from src.kg_tools import find_entity, list_entities, list_relations, validate_assertion
from src.retrieval_adapter import retrieve_evidence
from src.settings import PROJECT_ROOT


ToolHandler = Callable[..., dict[str, Any]]


def tool_result(data: Any = None, *, status: str = "ok", warnings: list[str] | None = None) -> dict[str, Any]:
    return {
        "status": status,
        "data": data,
        "warnings": warnings or [],
    }


def list_universes() -> dict[str, Any]:
    manifests = []
    for path in sorted((PROJECT_ROOT / "corpus" / "universes").glob("*/manifest.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        manifests.append(
            {
                "universe_id": data.get("universe_id"),
                "display_name": data.get("display_name"),
                "status": data.get("status"),
                "manifest_path": path.relative_to(PROJECT_ROOT).as_posix(),
                "summary_path": data.get("summary_path"),
            }
        )
    return tool_result(manifests)


def read_document(
    *,
    universe_id: str = "terran_empire",
    document_id: str | None = None,
    source_path: str | None = None,
) -> dict[str, Any]:
    if not document_id and not source_path:
        return tool_result(None, status="error", warnings=["document_id or source_path is required"])
    path = PROJECT_ROOT / "storage" / "processed" / universe_id / "documents.jsonl"
    for document in read_documents_jsonl(path):
        if document_id and document.get("document_id") == document_id:
            return tool_result(document)
        if source_path and document.get("source_path") == source_path:
            return tool_result(document)
    return tool_result(None, status="not_found")


def search_corpus_tool(
    *,
    query: str,
    universe_id: str = "terran_empire",
    k: int = 5,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return tool_result(retrieve_evidence(query, universe_id=universe_id, k=k, filters=filters))


def list_entities_tool(*, universe_id: str = "terran_empire", entity_type: str | None = None) -> dict[str, Any]:
    return tool_result(list_entities(universe_id=universe_id, entity_type=entity_type))


def get_entity_tool(*, name: str, universe_id: str = "terran_empire") -> dict[str, Any]:
    entity = find_entity(name, universe_id=universe_id)
    return tool_result(entity, status="ok" if entity else "not_found")


def list_relations_tool(
    *,
    entity_name: str,
    universe_id: str = "terran_empire",
    relation_type: str | None = None,
) -> dict[str, Any]:
    return tool_result(list_relations(entity_name, universe_id=universe_id, relation_type=relation_type))


def validate_assertion_tool(*, assertion: str, universe_id: str = "terran_empire") -> dict[str, Any]:
    return tool_result(validate_assertion(assertion, universe_id=universe_id))


TOOL_REGISTRY: dict[str, ToolHandler] = {
    "list_universes": list_universes,
    "read_document": read_document,
    "search_corpus": search_corpus_tool,
    "list_entities": list_entities_tool,
    "get_entity": get_entity_tool,
    "list_relations": list_relations_tool,
    "validate_assertion": validate_assertion_tool,
}


def call_tool(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Call a registered tool by name."""
    if name not in TOOL_REGISTRY:
        return tool_result(None, status="error", warnings=[f"Unknown tool: {name}"])
    return TOOL_REGISTRY[name](**(arguments or {}))
