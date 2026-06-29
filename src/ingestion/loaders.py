"""Load raw files into normalized document records."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any

from src.ingestion.documents import (
    DOCUMENT_SCHEMA_VERSION,
    DocumentRecord,
    sha256_bytes,
    stable_document_id,
    version_from_hash,
)
from src.multimodal import build_asset_record, detect_modality, plan_asset_processing
from src.text_splitter import clean_text


TEXT_EXTENSIONS = {".md", ".markdown", ".txt"}
MEDIA_DOCUMENT_MODALITIES = {"image", "audio"}


class IngestionError(RuntimeError):
    """Base ingestion error."""


class UnsupportedFormatError(IngestionError):
    """Raised when no loader exists for a source file."""


def is_text_document(path: Path) -> bool:
    """Return whether the file extension is supported by the text loader."""
    return path.suffix.lower() in TEXT_EXTENSIONS


def is_media_document(path: Path) -> bool:
    """Return whether the file can be stored as an unprocessed media document."""
    return detect_modality(path) in MEDIA_DOCUMENT_MODALITIES


def relative_source_path(path: Path, project_root: Path) -> str:
    """Return a stable POSIX source path relative to the project when possible."""
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def load_text_document(
    path: Path,
    *,
    project_root: Path,
    universe_id: str,
    collection_id: str | None,
    metadata: dict[str, Any] | None = None,
) -> DocumentRecord:
    """Read a Markdown or plain-text file into a normalized document record."""
    if not is_text_document(path):
        raise UnsupportedFormatError(f"Unsupported text ingestion format: {path.suffix or '<none>'}")
    if not path.exists():
        raise IngestionError(f"Source file does not exist: {path}")

    raw_bytes = path.read_bytes()
    raw_content = raw_bytes.decode("utf-8")
    clean_content = clean_text(raw_content)
    source_hash = sha256_bytes(raw_bytes)
    source_path = relative_source_path(path, project_root)
    media_type = mimetypes.guess_type(path.name)[0] or "text/plain"
    line_count = 0 if not raw_content else raw_content.count("\n") + 1

    merged_metadata: dict[str, Any] = {
        "extension": path.suffix.lower(),
        "file_name": path.name,
        "size_bytes": len(raw_bytes),
        "line_count": line_count,
        "raw_character_count": len(raw_content),
        "clean_character_count": len(clean_content),
    }
    if metadata:
        merged_metadata.update(metadata)

    return DocumentRecord(
        schema_version=DOCUMENT_SCHEMA_VERSION,
        document_id=stable_document_id(universe_id, source_path),
        universe_id=universe_id,
        collection_id=collection_id,
        source_path=source_path,
        source_name=path.name,
        modality="text",
        media_type=media_type,
        raw_content=raw_content,
        clean_content=clean_content,
        metadata=merged_metadata,
        sha256=source_hash,
        version=version_from_hash(source_hash),
    )


def load_media_document(
    path: Path,
    *,
    project_root: Path,
    universe_id: str,
    collection_id: str | None,
    metadata: dict[str, Any] | None = None,
) -> DocumentRecord:
    """Create a normalized media document without OCR, captioning, or transcription."""
    if not is_media_document(path):
        raise UnsupportedFormatError(f"Unsupported media ingestion format: {path.suffix or '<none>'}")
    if not path.exists():
        raise IngestionError(f"Source file does not exist: {path}")

    asset = build_asset_record(
        path,
        universe_id=universe_id,
        project_root=project_root,
        metadata=metadata,
    )
    planned_derivatives = [derivative.to_dict() for derivative in plan_asset_processing(asset)]
    media_metadata: dict[str, Any] = {
        "extension": path.suffix.lower(),
        "file_name": path.name,
        "size_bytes": asset.size_bytes,
        "processing_mode": "metadata_only",
        "ai_models_used": [],
    }
    if metadata:
        media_metadata.update(metadata)

    return DocumentRecord(
        schema_version=DOCUMENT_SCHEMA_VERSION,
        document_id=stable_document_id(universe_id, asset.source_path),
        universe_id=universe_id,
        collection_id=collection_id,
        source_path=asset.source_path,
        source_name=asset.source_name,
        modality=asset.modality,
        media_type=asset.media_type,
        raw_content="",
        clean_content="",
        metadata=media_metadata,
        sha256=asset.sha256,
        version=version_from_hash(asset.sha256),
        media={
            "asset": asset.to_dict(),
            "planned_derivatives": planned_derivatives,
        },
    )


def load_document(
    path: Path,
    *,
    project_root: Path,
    universe_id: str,
    collection_id: str | None,
    metadata: dict[str, Any] | None = None,
) -> DocumentRecord:
    """Dispatch a source file to the supported loader."""
    if is_text_document(path):
        return load_text_document(
            path,
            project_root=project_root,
            universe_id=universe_id,
            collection_id=collection_id,
            metadata=metadata,
        )
    if is_media_document(path):
        return load_media_document(
            path,
            project_root=project_root,
            universe_id=universe_id,
            collection_id=collection_id,
            metadata=metadata,
        )
    raise UnsupportedFormatError(f"No ingestion loader for: {path}")
