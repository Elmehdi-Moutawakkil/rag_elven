"""Build retrieval indexes from normalized documents."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any

from src.indexing.chunks import chunk_documents, write_chunks_jsonl
from src.ingestion.documents import read_documents_jsonl
from src.ingestion.loaders import relative_source_path
from src.settings import PROJECT_ROOT


def default_documents_path(universe_id: str) -> Path:
    return PROJECT_ROOT / "storage" / "processed" / universe_id / "documents.jsonl"


def default_text_index_dir(universe_id: str) -> Path:
    return PROJECT_ROOT / "indexes" / universe_id / "text"


def build_text_index(
    *,
    universe_id: str,
    documents_path: Path | None = None,
    output_dir: Path | None = None,
    chunk_size: int = 900,
    overlap: int = 120,
) -> dict[str, Any]:
    """Build chunk metadata for text retrieval."""
    documents_path = documents_path or default_documents_path(universe_id)
    output_dir = output_dir or default_text_index_dir(universe_id)

    documents = read_documents_jsonl(documents_path)
    chunks = chunk_documents(documents, chunk_size=chunk_size, overlap=overlap)

    chunks_path = output_dir / "chunks.jsonl"
    manifest_path = output_dir / "manifest.json"
    write_chunks_jsonl(chunks, chunks_path)

    by_collection = Counter(chunk.collection_id or "unassigned" for chunk in chunks)
    by_source = Counter(chunk.source_path for chunk in chunks)
    manifest = {
        "schema_version": 1,
        "universe_id": universe_id,
        "documents_path": relative_source_path(documents_path, PROJECT_ROOT),
        "chunks_path": relative_source_path(chunks_path, PROJECT_ROOT),
        "document_count": len(documents),
        "chunk_count": len(chunks),
        "chunk_size": chunk_size,
        "chunk_overlap": overlap,
        "collections": dict(sorted(by_collection.items())),
        "sources": dict(sorted(by_source.items())),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return manifest
