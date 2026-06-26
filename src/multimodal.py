"""Multimodal asset metadata primitives."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import mimetypes
from pathlib import Path
from typing import Any, Literal

from src.ingestion.loaders import relative_source_path
from src.settings import PROJECT_ROOT


AssetModality = Literal["text", "image", "audio", "video", "pdf", "unknown"]
ProcessingStatus = Literal["raw", "metadata_extracted", "processed", "unsupported", "failed"]

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".tif", ".tiff"}
AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".ogg"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}
TEXT_EXTENSIONS = {".txt", ".md", ".markdown"}


@dataclass(frozen=True)
class AssetRecord:
    schema_version: int
    asset_id: str
    universe_id: str
    source_path: str
    source_name: str
    modality: AssetModality
    media_type: str
    sha256: str
    size_bytes: int
    processing_status: ProcessingStatus
    derivatives: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def detect_modality(path: Path) -> AssetModality:
    suffix = path.suffix.lower()
    if suffix in TEXT_EXTENSIONS:
        return "text"
    if suffix == ".pdf":
        return "pdf"
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    if suffix in AUDIO_EXTENSIONS:
        return "audio"
    if suffix in VIDEO_EXTENSIONS:
        return "video"
    return "unknown"


def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_asset_id(universe_id: str, source_path: str, source_hash: str) -> str:
    digest = hashlib.sha256(f"{universe_id}:{source_path}:{source_hash}".encode("utf-8")).hexdigest()
    return f"asset_{digest[:16]}"


def build_asset_record(
    path: Path,
    *,
    universe_id: str,
    project_root: Path = PROJECT_ROOT,
    metadata: dict[str, Any] | None = None,
) -> AssetRecord:
    """Build a multimodal asset metadata record without heavy processing."""
    if not path.exists():
        raise FileNotFoundError(path)
    source_hash = hash_file(path)
    source_path = relative_source_path(path, project_root)
    modality = detect_modality(path)
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    status: ProcessingStatus = "metadata_extracted" if modality != "unknown" else "unsupported"
    return AssetRecord(
        schema_version=1,
        asset_id=stable_asset_id(universe_id, source_path, source_hash),
        universe_id=universe_id,
        source_path=source_path,
        source_name=path.name,
        modality=modality,
        media_type=media_type,
        sha256=source_hash,
        size_bytes=path.stat().st_size,
        processing_status=status,
        metadata=metadata or {},
    )
