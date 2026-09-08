"""Versioned, content-addressed identities for retrieval citations.

Citation IDs identify a source, the document version containing an excerpt,
and the excerpt itself. They deliberately do not contain retrieval rank or
FAISS position, which are properties of a search result rather than evidence.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from src.settings import PROJECT_ROOT

CITATION_UNAVAILABLE = "CITATION_UNAVAILABLE"
_CITATION_PREFIX = "citation:v1"


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def stable_source_id(universe_id: str, source_path: str) -> str:
    """Return a stable source identity scoped to one universe."""
    return f"csrc_{_digest({'universe_id': str(universe_id), 'source_path': canonical_source_path(source_path)})[:24]}"


def canonical_source_path(source_path: str) -> str:
    """Use a project-relative source representation for stable citations."""
    path = Path(str(source_path))
    if path.is_absolute():
        try:
            return path.resolve().relative_to(PROJECT_ROOT).as_posix()
        except ValueError:
            return path.as_posix()
    return path.as_posix()


def citation_version_id(
    universe_id: str,
    source_path: str,
    text: str,
    *,
    document_sha256: str | None = None,
) -> str:
    """Return the version identity for an excerpt's source document.

    A supplied document hash intentionally invalidates all excerpts after any
    document edit. The excerpt identity separately hashes its content and span.
    Without a document hash, the content hash is the conservative fallback.
    """
    content_hash = _digest(str(text))
    return f"cver_{_digest({
        'source_id': stable_source_id(universe_id, source_path),
        'document_sha256': str(document_sha256) if document_sha256 else content_hash,
    })[:24]}"


def citation_excerpt_id(
    version_id: str,
    text: str,
    *,
    start_offset: int | None = None,
    end_offset: int | None = None,
    page: int | str | None = None,
) -> str:
    """Return an immutable identity for one versioned excerpt and its span."""
    return f"cexp_{_digest({
        'version_id': str(version_id),
        'text_sha256': _digest(str(text)),
        'start_offset': start_offset,
        'end_offset': end_offset,
        'page': page,
    })[:24]}"


def legacy_faiss_chunk_id(
    source_path: str,
    text: str,
    *,
    universe_id: str = "",
    page: int | str | None = None,
) -> str:
    """Return a rank-independent identity for legacy FAISS metadata."""
    return f"legacy_{_digest({
        'source_id': stable_source_id(universe_id, source_path),
        'text_sha256': _digest(str(text)),
        'page': page,
    })[:24]}"


def _metadata_value(record: Mapping[str, Any], name: str, default: Any = None) -> Any:
    metadata = record.get("metadata", {})
    if name in record:
        return record[name]
    if isinstance(metadata, Mapping) and name in metadata:
        return metadata[name]
    return default


def normalize_chunk_for_citation(record: Mapping[str, Any]) -> dict[str, Any]:
    """Add the versioned citation contract to a chunk without changing its ID.

    This is safe for legacy JSONL and FAISS metadata at read time: it returns a
    copy, preserving the stored chunk ID and all provenance metadata.
    """
    normalized = dict(record)
    metadata = dict(record.get("metadata", {})) if isinstance(record.get("metadata", {}), Mapping) else {}
    text = str(record.get("text", ""))
    universe_id = str(_metadata_value(record, "universe_id", ""))
    source_path = canonical_source_path(str(_metadata_value(record, "source_path", record.get("source", ""))))
    document_sha256 = _metadata_value(record, "document_sha256", record.get("sha256"))
    start_offset = _metadata_value(record, "start_offset")
    end_offset = _metadata_value(record, "end_offset")
    page = _metadata_value(record, "page")

    source_id = stable_source_id(universe_id, source_path)
    version_id = citation_version_id(
        universe_id,
        source_path,
        text,
        document_sha256=str(document_sha256) if document_sha256 else None,
    )
    excerpt_id = citation_excerpt_id(
        version_id,
        text,
        start_offset=start_offset,
        end_offset=end_offset,
        page=page,
    )

    metadata.update(
        {
            "citation_source_id": source_id,
            "citation_version_id": version_id,
            "citation_excerpt_id": excerpt_id,
        }
    )
    if document_sha256 is not None:
        metadata.setdefault("document_sha256", document_sha256)
    normalized["metadata"] = metadata
    normalized["source_path"] = source_path
    normalized.setdefault("source", source_path)
    normalized["citation_source_id"] = source_id
    normalized["citation_version_id"] = version_id
    normalized["citation_excerpt_id"] = excerpt_id
    normalized["citation"] = format_citation_identity(normalized)
    return normalized


def format_citation_identity(record_or_identity: Mapping[str, Any]) -> str:
    """Serialize a canonical citation identity for storage or transport."""
    metadata = record_or_identity.get("metadata", {})
    metadata = metadata if isinstance(metadata, Mapping) else {}
    source_id = record_or_identity.get("citation_source_id", metadata.get("citation_source_id"))
    version_id = record_or_identity.get("citation_version_id", metadata.get("citation_version_id"))
    excerpt_id = record_or_identity.get("citation_excerpt_id", metadata.get("citation_excerpt_id"))
    if not all((source_id, version_id, excerpt_id)):
        raise ValueError("citation identity requires source, version, and excerpt IDs")
    return f"{_CITATION_PREFIX}:{source_id}:{version_id}:{excerpt_id}"


def _is_canonical_citation(citation: str) -> bool:
    parts = citation.split(":")
    return (
        len(parts) == 5
        and parts[:2] == ["citation", "v1"]
        and parts[2].startswith("csrc_")
        and parts[3].startswith("cver_")
        and parts[4].startswith("cexp_")
    )


def resolve_citation_identity(
    citation: str | Mapping[str, Any], available_records: Iterable[Mapping[str, Any]]
) -> dict[str, Any] | str:
    """Resolve only an exact canonical citation from supplied current records.

    No historical store is implied. Unsafe legacy ``source#chunk`` references
    are intentionally unavailable rather than mapped to potentially changed
    text.
    """
    try:
        requested = format_citation_identity(citation) if isinstance(citation, Mapping) else str(citation)
    except ValueError:
        return CITATION_UNAVAILABLE
    if not _is_canonical_citation(requested):
        return CITATION_UNAVAILABLE

    for record in available_records:
        normalized = normalize_chunk_for_citation(record)
        if format_citation_identity(normalized) == requested:
            return normalized
    return CITATION_UNAVAILABLE
