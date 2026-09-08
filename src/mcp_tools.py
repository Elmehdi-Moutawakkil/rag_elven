"""Stable tool handlers intended for MCP exposure."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any, Callable

from src.ingestion.documents import read_documents_jsonl
from src.kg_tools import find_entity, list_entities, list_relations, validate_assertion
from src.output_validation import validate_generated_output
from src.citations import CITATION_UNAVAILABLE, resolve_citation_identity
from src.retrieval_adapter import RetrievalStatus, available_citation_records, retrieve_evidence_result
from src.settings import PROJECT_ROOT
from src.universe_registry import get_universe_registry, resolve_universe


ToolHandler = Callable[..., dict[str, Any]]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    category: str
    read_only: bool = True
    side_effects: bool = False
    stability: str = "stable"
    arguments: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def tool_result(data: Any = None, *, status: str = "ok", warnings: list[str] | None = None) -> dict[str, Any]:
    return {
        "status": status,
        "data": data,
        "warnings": warnings or [],
    }


def list_tools() -> dict[str, Any]:
    """List public MCP-ready tool contracts."""
    return tool_result([spec.to_dict() for spec in TOOL_SPECS.values()])


def list_universes() -> dict[str, Any]:
    manifests = []
    for config in get_universe_registry().list():
        manifests.append(
            {
                "universe_id": config.universe_id,
                "display_name": config.display_name,
                "status": config.status,
                "manifest_path": config.manifest_path.relative_to(PROJECT_ROOT).as_posix(),
                "semantic_available": bool(config.semantic_index_path and config.semantic_index_path.exists()),
                "lexical_available": bool(config.text_chunks_path and config.text_chunks_path.exists()),
            }
        )
    return tool_result(manifests)


def read_document(
    *,
    universe_id: str | None = None,
    document_id: str | None = None,
    source_path: str | None = None,
) -> dict[str, Any]:
    if not document_id and not source_path:
        return tool_result(None, status="error", warnings=["document_id or source_path is required"])
    resolution = resolve_universe(universe_id)
    if not resolution.ok:
        return tool_result(None, status="error", warnings=[f"{resolution.status}: {resolution.error}"])
    assert resolution.universe_id is not None
    path = PROJECT_ROOT / "storage" / "processed" / resolution.universe_id / "documents.jsonl"
    if not path.exists():
        return tool_result(None, status="not_found", warnings=[f"No processed documents for universe: {resolution.universe_id}"])
    for document in read_documents_jsonl(path):
        if document_id and document.get("document_id") == document_id:
            return tool_result(document)
        if source_path and document.get("source_path") == source_path:
            return tool_result(document)
    return tool_result(None, status="not_found")


def search_corpus_tool(
    *,
    query: str,
    universe_id: str | None = None,
    k: int = 5,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = retrieve_evidence_result(query, universe_id=universe_id, k=k, filters=filters)
    status = "ok" if result.status in {RetrievalStatus.SUCCESS, RetrievalStatus.NO_RESULTS} else "error"
    warnings = list(result.warnings)
    if result.error:
        warnings.append(f"{result.status}: {result.error}")
    return tool_result(result.to_dict(), status=status, warnings=warnings)


def resolve_citation_tool(*, citation: str, universe_id: str | None = None) -> dict[str, Any]:
    """Resolve only an exact versioned citation from current registered chunks."""
    resolution = resolve_universe(universe_id)
    if not resolution.ok:
        return tool_result(CITATION_UNAVAILABLE, status="error", warnings=[f"{resolution.status}: {resolution.error}"])
    try:
        resolved = resolve_citation_identity(citation, available_citation_records(resolution.universe_id))
    except Exception as exc:
        return tool_result(CITATION_UNAVAILABLE, status="error", warnings=[str(exc)])
    return tool_result(resolved, status="ok" if resolved != CITATION_UNAVAILABLE else "not_found")


def _resolve_tool_universe(universe_id: str | None) -> tuple[str | None, dict[str, Any] | None]:
    resolution = resolve_universe(universe_id)
    if not resolution.ok:
        return None, tool_result(None, status="error", warnings=[f"{resolution.status}: {resolution.error}"])
    return resolution.universe_id, None


def list_entities_tool(*, universe_id: str | None = None, entity_type: str | None = None) -> dict[str, Any]:
    resolved, error = _resolve_tool_universe(universe_id)
    return error or tool_result(list_entities(universe_id=resolved, entity_type=entity_type))


def get_entity_tool(*, name: str, universe_id: str | None = None) -> dict[str, Any]:
    resolved, error = _resolve_tool_universe(universe_id)
    if error:
        return error
    entity = find_entity(name, universe_id=resolved)
    return tool_result(entity, status="ok" if entity else "not_found")


def list_relations_tool(
    *,
    entity_name: str,
    universe_id: str | None = None,
    relation_type: str | None = None,
) -> dict[str, Any]:
    resolved, error = _resolve_tool_universe(universe_id)
    return error or tool_result(list_relations(entity_name, universe_id=resolved, relation_type=relation_type))


def validate_assertion_tool(*, assertion: str, universe_id: str | None = None) -> dict[str, Any]:
    resolved, error = _resolve_tool_universe(universe_id)
    return error or tool_result(validate_assertion(assertion, universe_id=resolved))


def validate_generated_output_tool(
    *,
    text: str,
    universe_id: str | None = None,
    retrieval_hits: list[dict[str, Any]] | None = None,
    require_citations: bool = True,
    check_kg: bool = True,
    check_memory: bool = True,
) -> dict[str, Any]:
    resolved, error = _resolve_tool_universe(universe_id)
    if error:
        return error
    return tool_result(
        validate_generated_output(
            text,
            universe_id=resolved,
            retrieval_hits=retrieval_hits or [],
            require_citations=require_citations,
            check_kg=check_kg,
            check_memory=check_memory,
        )
    )


TOOL_REGISTRY: dict[str, ToolHandler] = {
    "list_tools": list_tools,
    "list_universes": list_universes,
    "read_document": read_document,
    "search_corpus": search_corpus_tool,
    "resolve_citation": resolve_citation_tool,
    "list_entities": list_entities_tool,
    "get_entity": get_entity_tool,
    "list_relations": list_relations_tool,
    "validate_assertion": validate_assertion_tool,
    "validate_generated_output": validate_generated_output_tool,
}


TOOL_SPECS: dict[str, ToolSpec] = {
    "list_tools": ToolSpec(
        name="list_tools",
        description="List MCP-ready tool contracts exposed by RAGElven.",
        category="meta",
        arguments={},
    ),
    "list_universes": ToolSpec(
        name="list_universes",
        description="List available universe manifests.",
        category="corpus",
        arguments={},
    ),
    "read_document": ToolSpec(
        name="read_document",
        description="Read one processed document by document_id or source_path.",
        category="corpus",
        arguments={
            "universe_id": "string, required",
            "document_id": "string, optional",
            "source_path": "string, optional",
        },
    ),
    "search_corpus": ToolSpec(
        name="search_corpus",
        description="Search a registered corpus and return a versioned retrieval result.",
        category="retrieval",
        arguments={
            "query": "string, required",
            "universe_id": "string, required",
            "k": "integer, default 5",
            "filters": "object, optional",
        },
    ),
    "resolve_citation": ToolSpec(
        name="resolve_citation",
        description="Resolve one exact current versioned citation, or report it unavailable.",
        category="retrieval",
        arguments={"citation": "string, required", "universe_id": "string, required"},
    ),
    "list_entities": ToolSpec(
        name="list_entities",
        description="List Knowledge Graph entities, optionally filtered by type.",
        category="knowledge_graph",
        arguments={
            "universe_id": "string, default terran_empire",
            "entity_type": "string, optional",
        },
    ),
    "get_entity": ToolSpec(
        name="get_entity",
        description="Find one Knowledge Graph entity by name or alias.",
        category="knowledge_graph",
        arguments={
            "name": "string, required",
            "universe_id": "string, default terran_empire",
        },
    ),
    "list_relations": ToolSpec(
        name="list_relations",
        description="List outgoing Knowledge Graph relations for one entity.",
        category="knowledge_graph",
        arguments={
            "entity_name": "string, required",
            "universe_id": "string, default terran_empire",
            "relation_type": "string, optional",
        },
    ),
    "validate_assertion": ToolSpec(
        name="validate_assertion",
        description="Validate one assertion against deterministic KG rules.",
        category="validation",
        arguments={
            "assertion": "string, required",
            "universe_id": "string, default terran_empire",
        },
    ),
    "validate_generated_output": ToolSpec(
        name="validate_generated_output",
        description="Validate generated text against retrieval hits, citations, KG, and memory.",
        category="validation",
        arguments={
            "text": "string, required",
            "universe_id": "string, default terran_empire",
            "retrieval_hits": "array, optional",
            "require_citations": "boolean, default true",
            "check_kg": "boolean, default true",
            "check_memory": "boolean, default true",
        },
    ),
}


def call_tool(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Call a registered tool by name."""
    if name not in TOOL_REGISTRY:
        return tool_result(None, status="error", warnings=[f"Unknown tool: {name}"])
    return TOOL_REGISTRY[name](**(arguments or {}))
