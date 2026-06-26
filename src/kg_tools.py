"""Sourced Knowledge Graph tools."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.knowledge_graph import KnowledgeGraph
from src.retrieval_hybrid import search_corpus
from src.settings import PROJECT_ROOT


def kg_path_for_universe(universe_id: str) -> Path:
    """Return the current KG SQLite path for a universe."""
    if universe_id == "terran_empire":
        return PROJECT_ROOT / "vector_db" / "terran_empire" / "knowledge_graph.sqlite"
    return PROJECT_ROOT / "vector_db" / "knowledge_graph.sqlite"


def _decode_aliases(entity: dict[str, Any]) -> dict[str, Any]:
    aliases = entity.get("aliases", "[]")
    if isinstance(aliases, str):
        try:
            entity["aliases"] = json.loads(aliases)
        except json.JSONDecodeError:
            entity["aliases"] = []
    return entity


def get_kg(universe_id: str = "terran_empire") -> KnowledgeGraph:
    """Open a KnowledgeGraph for a universe."""
    return KnowledgeGraph(kg_path_for_universe(universe_id)).connect()


def list_entities(universe_id: str = "terran_empire", entity_type: str | None = None) -> list[dict[str, Any]]:
    """List KG entities as JSON-compatible dictionaries."""
    with get_kg(universe_id) as kg:
        if entity_type:
            rows = kg.conn.execute(
                "SELECT * FROM entities WHERE entity_type = ? ORDER BY name",
                (entity_type,),
            ).fetchall()
        else:
            rows = kg.conn.execute("SELECT * FROM entities ORDER BY name").fetchall()
        return [_decode_aliases(dict(row)) for row in rows]


def find_entity(name: str, universe_id: str = "terran_empire") -> dict[str, Any] | None:
    """Find one entity by exact name or alias."""
    with get_kg(universe_id) as kg:
        entity = kg.get_entity(name)
        return _decode_aliases(entity) if entity else None


def list_relations(
    entity_name: str,
    *,
    universe_id: str = "terran_empire",
    relation_type: str | None = None,
) -> list[dict[str, Any]]:
    """List outgoing relations for one entity."""
    with get_kg(universe_id) as kg:
        return kg.get_relations(entity_name, relation_type=relation_type)


def source_evidence_for_entity(
    entity_name: str,
    *,
    universe_id: str = "terran_empire",
    k: int = 3,
) -> list[dict[str, Any]]:
    """Retrieve source chunks that mention an entity."""
    return search_corpus(entity_name, universe_id=universe_id, k=k)


def validate_assertion(assertion: str, *, universe_id: str = "terran_empire") -> dict[str, Any]:
    """Validate an assertion or generated passage against the universe KG."""
    with get_kg(universe_id) as kg:
        result = kg.validate_story(assertion)

    evidence: dict[str, list[dict[str, Any]]] = {}
    for entity_name in result.get("entities_found", []):
        evidence[entity_name] = source_evidence_for_entity(entity_name, universe_id=universe_id, k=2)

    hard = sum(1 for violation in result.get("violations", []) if violation.get("severity") == "HARD")
    soft = sum(1 for violation in result.get("violations", []) if violation.get("severity") == "SOFT")
    status = "validated" if hard == 0 else "hard_contradiction"
    if hard == 0 and soft:
        status = "attention"

    return {
        "universe_id": universe_id,
        "assertion": assertion,
        "status": status,
        "score": result.get("score", 0),
        "is_valid": result.get("is_valid", False),
        "hard_violations": hard,
        "soft_violations": soft,
        "violations": result.get("violations", []),
        "entities_found": result.get("entities_found", []),
        "source_evidence": evidence,
        "method": "sourced_knowledge_graph",
    }
