"""Typed, manifest-bound retrieval with versioned provenance."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
import json
from pathlib import Path
from typing import Any, Literal

from src.citations import legacy_faiss_chunk_id, normalize_chunk_for_citation
from src.indexing.chunks import read_chunks_jsonl
from src.retrieval import search_faiss
from src.retrieval_hybrid import search_chunks
from src.universe_registry import (
    SELECTION_REQUIRED,
    UNIVERSE_REQUIRED,
    UNIVERSE_UNKNOWN,
    SemanticIndexHandle,
    UniverseRegistryError,
    get_universe_registry,
    resolve_universe,
    validate_source_path,
)


class RetrievalStatus(StrEnum):
    SUCCESS = "SUCCESS"
    NO_RESULTS = "NO_RESULTS"
    INDEX_MISSING = "INDEX_MISSING"
    UNIVERSE_REQUIRED = UNIVERSE_REQUIRED
    UNIVERSE_UNKNOWN = UNIVERSE_UNKNOWN
    SELECTION_REQUIRED = SELECTION_REQUIRED
    ERROR = "ERROR"


class RetrievalContractError(RuntimeError):
    """Raised by the list compatibility wrapper for a failed retrieval."""

    def __init__(self, result: "RetrievalResult"):
        super().__init__(f"{result.status}: {result.error or 'retrieval failed'}")
        self.result = result


@dataclass(frozen=True)
class RetrievalResult:
    """Versioned outcome shared by retrieval, UI, layers, agents, and MCP."""

    status: RetrievalStatus
    universe_id: str | None
    hits: list[dict[str, Any]] = field(default_factory=list)
    engines: list[str] = field(default_factory=list)
    degraded: bool = False
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    schema_version: int = 2

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


RetrievalMode = Literal["lexical", "semantic", "hybrid", "auto"]


def _result(status: RetrievalStatus, universe_id: str | None, **kwargs: Any) -> RetrievalResult:
    return RetrievalResult(status=status, universe_id=universe_id, **kwargs)


def _semantic_score(distance: float) -> float:
    return 0.0 if distance < 0 else 1.0 / (1.0 + distance)


def _source_name(path: str) -> str:
    return Path(path).name if path else ""


def _normalize_lexical_hit(hit: dict[str, Any], universe_id: str) -> dict[str, Any]:
    normalized = dict(hit)
    source_path = str(normalized.get("source_path") or normalized.get("source") or "")
    normalized["universe_id"] = universe_id
    normalized.setdefault("source_path", source_path)
    normalized.setdefault("source", source_path)
    normalized.setdefault("source_name", _source_name(source_path))
    normalized.setdefault("lexical_score", float(normalized.get("score", 0.0)))
    normalized.setdefault("semantic_score", 0.0)
    normalized["retrieval_engine"] = "lexical"
    return normalize_chunk_for_citation(normalized)


def _normalize_semantic_hit(hit: dict[str, Any], universe_id: str) -> dict[str, Any]:
    source_path = str(hit.get("source") or hit.get("source_path") or "")
    text = str(hit.get("text", ""))
    page = hit.get("page")
    score = round(_semantic_score(float(hit.get("score", 0.0))), 6)
    normalized = {
        "chunk_id": legacy_faiss_chunk_id(source_path, text, universe_id=universe_id, page=page),
        "document_id": "",
        "universe_id": universe_id,
        "collection_id": hit.get("doc_type"),
        "text": text,
        "source_path": source_path,
        "source": source_path,
        "source_name": _source_name(source_path),
        "page": page,
        "score": score,
        "lexical_score": 0.0,
        "semantic_score": score,
        "match_terms": [],
        "metadata": {key: value for key, value in hit.items() if key not in {"text", "source", "source_path", "score"}},
        "retrieval_engine": "faiss",
    }
    return normalize_chunk_for_citation(normalized)


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


def _read_manifest_chunks(path: Path, config: Any) -> list[dict[str, Any]]:
    chunks = read_chunks_jsonl(path)
    normalized: list[dict[str, Any]] = []
    for chunk in chunks:
        if chunk.get("universe_id") != config.universe_id:
            raise UniverseRegistryError("Chunk universe does not match requested universe")
        validate_source_path(config, str(chunk.get("source_path") or chunk.get("source") or ""))
        normalized_chunk = normalize_chunk_for_citation(chunk)
        metadata = normalized_chunk["metadata"]
        if "canon_status" not in metadata:
            source_path = str(normalized_chunk.get("source_path", ""))
            for collection_path, canon_status in config.collection_canon_status:
                if source_path == collection_path or source_path.startswith(collection_path.rstrip("/") + "/"):
                    if canon_status is not None:
                        metadata["canon_status"] = canon_status
                    break
        normalized.append(normalized_chunk)
    return normalized


def available_citation_records(universe_id: str | None) -> list[dict[str, Any]]:
    """Return current lexical and semantic citation records without searching."""
    registry = get_universe_registry()
    resolution = resolve_universe(universe_id, registry=registry)
    if not resolution.ok:
        return []
    config = registry.require(resolution.universe_id or "")
    records: list[dict[str, Any]] = []
    if config.text_chunks_path and config.text_chunks_path.exists():
        records.extend(_read_manifest_chunks(config.text_chunks_path, config))
    if config.semantic_metadata_path and config.semantic_metadata_path.exists():
        metadata = json.loads(config.semantic_metadata_path.read_text(encoding="utf-8"))
        if not isinstance(metadata, list):
            raise UniverseRegistryError("FAISS metadata must be a JSON array")
        for item in metadata:
            if not isinstance(item, dict):
                raise UniverseRegistryError("FAISS metadata entry must be an object")
            validate_source_path(config, str(item.get("source") or item.get("source_path") or ""))
            records.append(_normalize_semantic_hit({**item, "score": 0.0}, config.universe_id))
    return records


def retrieve_evidence_result(
    query: str,
    *,
    universe_id: str | None = None,
    k: int = 5,
    filters: dict[str, Any] | None = None,
    mode: RetrievalMode = "auto",
    chunks_path: Path | None = None,
    semantic_handle: SemanticIndexHandle | None = None,
    model: Any = None,
    index: Any = None,
    metadata: list[dict[str, Any]] | None = None,
) -> RetrievalResult:
    """Retrieve from registered resources; raw semantic triplets are rejected."""
    registry = get_universe_registry()
    resolution = resolve_universe(universe_id, registry=registry)
    if not resolution.ok:
        return _result(RetrievalStatus(resolution.status), None, error=resolution.error)
    assert resolution.universe_id is not None
    config = registry.require(resolution.universe_id)
    if mode not in {"lexical", "semantic", "hybrid", "auto"}:
        return _result(RetrievalStatus.ERROR, config.universe_id, error=f"Unknown retrieval mode: {mode}")
    if index is not None or metadata is not None:
        return _result(RetrievalStatus.ERROR, config.universe_id, error="Raw semantic resources are unsupported; provide a SemanticIndexHandle")
    if chunks_path is not None and (config.text_chunks_path is None or Path(chunks_path).resolve() != config.text_chunks_path):
        return _result(RetrievalStatus.ERROR, config.universe_id, error="Chunks path does not match manifest")

    lexical_ready = config.text_chunks_path is not None and config.text_chunks_path.exists()
    semantic_ready = semantic_handle is not None and model is not None
    if mode == "lexical" and not lexical_ready:
        return _result(RetrievalStatus.INDEX_MISSING, config.universe_id, error="Declared lexical index is missing")
    if mode == "semantic" and not semantic_ready:
        return _result(RetrievalStatus.INDEX_MISSING, config.universe_id, error="A model and SemanticIndexHandle are required")
    if mode == "hybrid" and (not lexical_ready or not semantic_ready):
        return _result(RetrievalStatus.INDEX_MISSING, config.universe_id, error="Hybrid retrieval requires lexical and semantic indexes")
    if mode == "auto" and not lexical_ready and not semantic_ready:
        return _result(RetrievalStatus.INDEX_MISSING, config.universe_id, error="No registered retrieval engine is available")
    if semantic_handle is not None:
        try:
            semantic_handle.validate(config)
        except Exception as exc:
            return _result(RetrievalStatus.ERROR, config.universe_id, error=str(exc))

    candidate_k = max(max(1, k) * 3, 10)
    hits_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    engines: list[str] = []
    warnings: list[str] = []
    if lexical_ready and mode in {"lexical", "hybrid", "auto"}:
        try:
            for hit in search_chunks(query, _read_manifest_chunks(config.text_chunks_path, config), k=candidate_k, filters=filters):
                normalized = _normalize_lexical_hit(hit.to_dict(), config.universe_id)
                hits_by_key[_hit_key(normalized)] = normalized
            engines.append("lexical")
        except UniverseRegistryError as exc:
            return _result(RetrievalStatus.ERROR, config.universe_id, engines=engines, error=f"Lexical retrieval failed: {exc}")
        except Exception as exc:
            if mode != "auto" or not semantic_ready:
                return _result(RetrievalStatus.ERROR, config.universe_id, engines=engines, error=f"Lexical retrieval failed: {exc}")
            warnings.append(f"Lexical retrieval unavailable: {exc}")
    elif mode == "auto":
        warnings.append("Lexical index unavailable")

    if semantic_ready and mode in {"semantic", "hybrid", "auto"}:
        assert semantic_handle is not None
        try:
            for raw_hit in search_faiss(query, model, semantic_handle.index, semantic_handle.metadata, k=candidate_k):
                normalized = _normalize_semantic_hit(raw_hit, config.universe_id)
                if not _passes_filters(normalized, filters):
                    continue
                existing = hits_by_key.get(_hit_key(normalized))
                if existing:
                    existing["semantic_score"] = normalized["semantic_score"]
                    existing["score"] = round(float(existing["lexical_score"]) + float(normalized["semantic_score"]), 6)
                    existing["retrieval_engine"] = "hybrid"
                    existing.setdefault("metadata", {})["faiss_page"] = normalized.get("page")
                else:
                    hits_by_key[_hit_key(normalized)] = normalized
            engines.append("semantic")
        except UniverseRegistryError as exc:
            return _result(RetrievalStatus.ERROR, config.universe_id, engines=engines, error=f"Semantic retrieval failed: {exc}")
        except Exception as exc:
            if mode != "auto" or not engines:
                return _result(RetrievalStatus.ERROR, config.universe_id, engines=engines, error=f"Semantic retrieval failed: {exc}")
            warnings.append(f"Semantic retrieval unavailable: {exc}")
    elif mode == "auto":
        warnings.append("Semantic index unavailable")

    hits = sorted(hits_by_key.values(), key=lambda hit: (float(hit.get("score", 0.0)), float(hit.get("semantic_score", 0.0)), float(hit.get("lexical_score", 0.0))), reverse=True)[: max(1, k)]
    return _result(
        RetrievalStatus.SUCCESS if hits else RetrievalStatus.NO_RESULTS,
        config.universe_id,
        hits=hits,
        engines=engines,
        degraded=mode == "auto" and len(engines) == 1,
        warnings=warnings,
    )


def retrieve_evidence(query: str, **kwargs: Any) -> list[dict[str, Any]]:
    """Compatibility wrapper: only ``NO_RESULTS`` becomes an empty list."""
    result = retrieve_evidence_result(query, **kwargs)
    if result.status == RetrievalStatus.SUCCESS:
        return result.hits
    if result.status == RetrievalStatus.NO_RESULTS:
        return []
    raise RetrievalContractError(result)
