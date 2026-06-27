"""Unified evidence retrieval facade.

This module is the stable boundary for Step 8. It keeps the new normalized
chunk index as the provenance source and can fuse legacy FAISS scores when a
caller already has vector resources loaded.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from typing import Any

from src.indexing.build import default_text_index_dir
from src.indexing.chunks import read_chunks_jsonl
from src.retrieval import search_faiss
from src.retrieval_hybrid import search_chunks


def _semantic_score(distance: float) -> float:
    """Convert a FAISS L2 distance into a higher-is-better score."""
    if distance < 0:
        return 0.0
    return 1.0 / (1.0 + distance)


def _source_name(path: str) -> str:
    return Path(path).name if path else ""


def _legacy_chunk_id(source_path: str, text: str, index: int) -> str:
    digest = sha256(f"{source_path}:{index}:{text}".encode("utf-8")).hexdigest()
    return f"legacy_{digest[:16]}"


def _normalize_lexical_hit(hit: dict[str, Any]) -> dict[str, Any]:
    source_path = str(hit.get("source_path") or hit.get("source") or "")
    normalized = dict(hit)
    normalized.setdefault("source_path", source_path)
    normalized.setdefault("source", source_path)
    normalized.setdefault("source_name", _source_name(source_path))
    normalized.setdefault("citation", f"{source_path}#{normalized.get('chunk_id', '')}")
    normalized.setdefault("lexical_score", float(normalized.get("score", 0.0)))
    normalized.setdefault("semantic_score", 0.0)
    normalized.setdefault("retrieval_engine", "lexical")
    return normalized


def _normalize_semantic_hit(hit: dict[str, Any], *, universe_id: str, index: int) -> dict[str, Any]:
    source_path = str(hit.get("source") or hit.get("source_path") or "")
    text = str(hit.get("text", ""))
    distance = float(hit.get("score", 0.0))
    score = round(_semantic_score(distance), 6)
    chunk_id = _legacy_chunk_id(source_path, text, index)
    return {
        "chunk_id": chunk_id,
        "document_id": "",
        "universe_id": universe_id,
        "collection_id": hit.get("doc_type"),
        "text": text,
        "source_path": source_path,
        "source": source_path,
        "source_name": _source_name(source_path),
        "page": hit.get("page"),
        "score": score,
        "lexical_score": 0.0,
        "semantic_score": score,
        "match_terms": [],
        "citation": f"{source_path}#{chunk_id}",
        "metadata": {
            key: value
            for key, value in hit.items()
            if key not in {"text", "source", "source_path", "score"}
        },
        "retrieval_engine": "faiss",
    }


def _hit_key(hit: dict[str, Any]) -> tuple[str, str]:
    return (str(hit.get("source_path") or hit.get("source") or ""), str(hit.get("text", "")))


def _passes_filters(hit: dict[str, Any], filters: dict[str, Any] | None) -> bool:
    if not filters:
        return True
    metadata = hit.get("metadata", {})
    for key, expected in filters.items():
        actual = hit.get(key, metadata.get(key))
        if isinstance(expected, (list, tuple, set)):
            if actual not in expected:
                return False
        elif actual != expected:
            return False
    return True


def retrieve_evidence(
    query: str,
    *,
    universe_id: str = "terran_empire",
    k: int = 5,
    filters: dict[str, Any] | None = None,
    chunks_path: Path | None = None,
    model: Any = None,
    index: Any = None,
    metadata: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Return ranked evidence with provenance.

    The normalized JSONL chunk index is used when available. Legacy FAISS is
    fused only when the caller passes `model`, `index`, and `metadata`, avoiding
    hidden model loads in MCP or agent tools.
    """
    requested_k = max(1, k)
    candidate_k = max(requested_k * 3, 10)
    hits_by_key: dict[tuple[str, str], dict[str, Any]] = {}

    chunks_path = chunks_path or (default_text_index_dir(universe_id) / "chunks.jsonl")
    if chunks_path.exists():
        chunks = read_chunks_jsonl(chunks_path)
        lexical_hits = search_chunks(query, chunks, k=candidate_k, filters=filters)
        for hit in lexical_hits:
            normalized = _normalize_lexical_hit(hit.to_dict())
            hits_by_key[_hit_key(normalized)] = normalized

    if model is not None and index is not None and metadata:
        for position, raw_hit in enumerate(search_faiss(query, model, index, metadata, k=candidate_k)):
            normalized = _normalize_semantic_hit(raw_hit, universe_id=universe_id, index=position)
            if not _passes_filters(normalized, filters):
                continue
            key = _hit_key(normalized)
            existing = hits_by_key.get(key)
            if existing:
                semantic_score = float(normalized.get("semantic_score", 0.0))
                existing["semantic_score"] = semantic_score
                existing["score"] = round(float(existing.get("lexical_score", 0.0)) + semantic_score, 6)
                existing["retrieval_engine"] = "hybrid"
                existing.setdefault("metadata", {})["faiss_page"] = normalized.get("page")
            else:
                hits_by_key[key] = normalized

    hits = sorted(
        hits_by_key.values(),
        key=lambda hit: (
            float(hit.get("score", 0.0)),
            float(hit.get("semantic_score", 0.0)),
            float(hit.get("lexical_score", 0.0)),
        ),
        reverse=True,
    )
    return hits[:requested_k]
