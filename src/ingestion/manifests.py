"""Universe manifest ingestion helpers."""

from __future__ import annotations

from collections.abc import Iterable
import json
from pathlib import Path
from typing import Any

from src.ingestion.documents import DocumentRecord
from src.ingestion.loaders import load_document, relative_source_path


def load_manifest(manifest_path: Path) -> dict[str, Any]:
    """Load and minimally validate a universe manifest."""
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Manifest must be a JSON object: {manifest_path}")
    if not isinstance(data.get("universe_id"), str):
        raise ValueError(f"Manifest is missing string universe_id: {manifest_path}")
    if not isinstance(data.get("source_files"), list):
        raise ValueError(f"Manifest is missing source_files list: {manifest_path}")
    return data


def collection_for_source(manifest: dict[str, Any], source_file: str) -> dict[str, Any] | None:
    """Find the collection that owns a source file."""
    source_path = Path(source_file)
    for collection in manifest.get("collections", []):
        if not isinstance(collection, dict):
            continue
        collection_source = collection.get("source_path")
        if not isinstance(collection_source, str):
            continue
        try:
            source_path.relative_to(Path(collection_source))
            return collection
        except ValueError:
            continue
    return None


def iter_manifest_sources(
    manifest: dict[str, Any],
    *,
    project_root: Path,
) -> Iterable[tuple[Path, str, dict[str, Any] | None]]:
    """Yield absolute path, relative path, and owning collection for each source."""
    for source_file in manifest["source_files"]:
        if not isinstance(source_file, str):
            raise ValueError("Manifest source_files entries must be strings")
        yield project_root / source_file, source_file, collection_for_source(manifest, source_file)


def metadata_for_source(
    manifest: dict[str, Any],
    manifest_path: Path,
    project_root: Path,
    source_index: int,
    collection: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build provenance metadata for one manifest source."""
    metadata: dict[str, Any] = {
        "manifest_path": relative_source_path(manifest_path, project_root),
        "manifest_schema_version": manifest.get("schema_version"),
        "universe_display_name": manifest.get("display_name"),
        "source_index": source_index,
        "summary_path": manifest.get("summary_path"),
    }
    if collection:
        metadata.update(
            {
                "collection_label": collection.get("label"),
                "canon_status": collection.get("canon_status"),
                "themes": collection.get("themes", []),
            }
        )
    return metadata


def ingest_universe_manifest(
    manifest_path: Path,
    *,
    project_root: Path,
) -> list[DocumentRecord]:
    """Ingest all supported source files referenced by a universe manifest."""
    manifest = load_manifest(manifest_path)
    universe_id = manifest["universe_id"]
    documents: list[DocumentRecord] = []

    for source_index, (path, _source_file, collection) in enumerate(
        iter_manifest_sources(manifest, project_root=project_root)
    ):
        collection_id = collection.get("collection_id") if collection else None
        metadata = metadata_for_source(manifest, manifest_path, project_root, source_index, collection)
        documents.append(
            load_document(
                path,
                project_root=project_root,
                universe_id=universe_id,
                collection_id=collection_id,
                metadata=metadata,
            )
        )
    return documents
