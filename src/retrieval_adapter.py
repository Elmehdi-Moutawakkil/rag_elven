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
    normalized.setdefault("relevance_score", float(normalized.get("score", 0.0)))
    normalized.setdefault("lexical_score", float(normalized.get("relevance_score", 0.0)))
    normalized.setdefault("semantic_score", 0.0)
    normalized["retrieval_engine"] = "lexical"
    return normalize_chunk_for_citation(normalized)


def _source_metadata(config: Any, source_path: str) -> dict[str, Any]:
    """Return human-curated per-source metadata declared by the manifest."""
    try:
        manifest = json.loads(config.manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    source_metadata = manifest.get("source_metadata", {})
    if not isinstance(source_metadata, dict):
        return {}
    metadata = source_metadata.get(source_path, {})
    return dict(metadata) if isinstance(metadata, dict) else {}


def _normalize_semantic_hit(
    hit: dict[str, Any],
    universe_id: str,
    *,
    source_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
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
        "relevance_score": score,
        "lexical_score": 0.0,
        "semantic_score": score,
        "match_terms": [],
        "metadata": {
            **{key: value for key, value in hit.items() if key not in {"text", "source", "source_path", "score"}},
            **(source_metadata or {}),
        },
        "retrieval_engine": "faiss",
        "diagnostics": {"semantic_raw_distance": float(hit.get("score", 0.0))},
    }
    return normalize_chunk_for_citation(normalized)


def _source_key(hit: dict[str, Any]) -> str:
    """Canonical source identity used by the user-facing source ranking."""
    return str(hit.get("source_path") or hit.get("source") or "")


def _fuse_ranked_hits(
    lexical_hits: list[dict[str, Any]],
    semantic_hits: list[dict[str, Any]],
    *,
    rrf_k: int = 60,
) -> list[dict[str, Any]]:
    """Fuse engine rankings with normalized reciprocal-rank fusion.

    Raw lexical weights and semantic distances are diagnostics only. ``score``
    and ``relevance_score`` share a documented 0..1 rank-based scale.
    """
    engine_lists = [("lexical", lexical_hits), ("semantic", semantic_hits)]
    if not any(hits for _, hits in engine_lists):
        return []

    fused_by_source: dict[str, dict[str, Any]] = {}
    for engine, ranked_hits in engine_lists:
        seen_sources: set[str] = set()
        source_rank = 0
        for chunk_rank, incoming in enumerate(ranked_hits, start=1):
            source = _source_key(incoming)
            if source in seen_sources:
                existing = fused_by_source.get(source)
                if existing is not None:
                    supporting = existing.setdefault("diagnostics", {}).setdefault("supporting_chunk_ids", [])
                    chunk_id = incoming.get("chunk_id")
                    if chunk_id and chunk_id not in supporting:
                        supporting.append(chunk_id)
                continue
            seen_sources.add(source)
            source_rank += 1
            existing = fused_by_source.get(source)
            if existing is None:
                existing = dict(incoming)
                existing["metadata"] = dict(incoming.get("metadata", {}))
                existing["diagnostics"] = dict(incoming.get("diagnostics", {}))
                existing["diagnostics"]["supporting_chunk_ids"] = [incoming.get("chunk_id")]
                existing["_rrf_raw"] = 0.0
                fused_by_source[source] = existing
            existing["_rrf_raw"] += 1.0 / (rrf_k + source_rank)
            diagnostics = existing.setdefault("diagnostics", {})
            diagnostics[f"{engine}_rank"] = source_rank
            diagnostics[f"{engine}_chunk_rank"] = chunk_rank
            if engine == "lexical":
                diagnostics.setdefault("lexical_raw_score", incoming.get("diagnostics", {}).get("lexical_raw_score"))
                existing["lexical_score"] = float(incoming.get("lexical_score", incoming.get("score", 0.0)))
            else:
                diagnostics.setdefault("semantic_raw_distance", incoming.get("diagnostics", {}).get("semantic_raw_distance"))
                existing["semantic_score"] = float(incoming.get("semantic_score", incoming.get("score", 0.0)))
            incoming_metadata = incoming.get("metadata", {})
            if isinstance(incoming_metadata, dict):
                existing["metadata"].update(incoming_metadata)

    fused = list(fused_by_source.values())
    maximum = max(float(hit["_rrf_raw"]) for hit in fused)
    fused.sort(
        key=lambda hit: (
            -float(hit["_rrf_raw"]),
            int(hit.get("diagnostics", {}).get("lexical_rank", 10**9)),
            int(hit.get("diagnostics", {}).get("semantic_rank", 10**9)),
            _source_key(hit),
        )
    )
    for source_rank, hit in enumerate(fused, start=1):
        # The best final source is the 1.0 reference point. A small rank decay
        # makes tied RRF sources distinguishable without reintroducing raw-score
        # scale dominance.
        normalized_rrf = float(hit.pop("_rrf_raw")) / maximum
        relevance = round(normalized_rrf / (1.0 + 0.02 * (source_rank - 1)), 6)
        hit["score"] = relevance
        hit["relevance_score"] = relevance
        diagnostics = hit.setdefault("diagnostics", {})
        diagnostics["fusion_method"] = "rrf"
        diagnostics["rrf_k"] = rrf_k
        diagnostics["source_rank"] = source_rank
        hit["retrieval_engine"] = "hybrid" if "lexical_rank" in diagnostics and "semantic_rank" in diagnostics else (
            "lexical" if "lexical_rank" in diagnostics else "faiss"
        )
        episode_refs = hit.get("metadata", {}).get("episode_refs", [])
        hit["episode_refs"] = list(episode_refs) if isinstance(episode_refs, list) else []

    return fused


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
            source_path = str(item.get("source") or item.get("source_path") or "")
            records.append(
                _normalize_semantic_hit(
                    {**item, "score": 0.0},
                    config.universe_id,
                    source_metadata=_source_metadata(config, source_path),
                )
            )
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
    lexical_hits: list[dict[str, Any]] = []
    semantic_hits: list[dict[str, Any]] = []
    engines: list[str] = []
    warnings: list[str] = []
    if lexical_ready and mode in {"lexical", "hybrid", "auto"}:
        try:
            for hit in search_chunks(query, _read_manifest_chunks(config.text_chunks_path, config), k=candidate_k, filters=filters):
                normalized = _normalize_lexical_hit(hit.to_dict(), config.universe_id)
                lexical_hits.append(normalized)
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
                source_path = str(raw_hit.get("source") or raw_hit.get("source_path") or "")
                normalized = _normalize_semantic_hit(
                    raw_hit,
                    config.universe_id,
                    source_metadata=_source_metadata(config, source_path),
                )
                if not _passes_filters(normalized, filters):
                    continue
                semantic_hits.append(normalized)
            engines.append("semantic")
        except UniverseRegistryError as exc:
            return _result(RetrievalStatus.ERROR, config.universe_id, engines=engines, error=f"Semantic retrieval failed: {exc}")
        except Exception as exc:
            if mode != "auto" or not engines:
                return _result(RetrievalStatus.ERROR, config.universe_id, engines=engines, error=f"Semantic retrieval failed: {exc}")
            warnings.append(f"Semantic retrieval unavailable: {exc}")
    elif mode == "auto":
        warnings.append("Semantic index unavailable")

    if lexical_hits and semantic_hits:
        hits = _fuse_ranked_hits(lexical_hits, semantic_hits)
    elif lexical_hits:
        hits = lexical_hits
    else:
        hits = semantic_hits
    for hit in hits:
        hit.setdefault("relevance_score", float(hit.get("score", 0.0)))
        hit["score"] = hit["relevance_score"]
        metadata = hit.get("metadata", {})
        episode_refs = metadata.get("episode_refs", []) if isinstance(metadata, dict) else []
        hit["episode_refs"] = list(episode_refs) if isinstance(episode_refs, list) else []
    hits = sorted(
        hits,
        key=lambda hit: (
            -float(hit.get("relevance_score", 0.0)),
            str(hit.get("source_path") or hit.get("source") or ""),
            str(hit.get("chunk_id", "")),
        ),
    )[: max(1, k)]
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
