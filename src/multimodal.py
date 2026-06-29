"""Multimodal asset metadata and processing contracts.

This module intentionally does not call OCR, vision, audio, or embedding
models. It only records media metadata and declares future processing tasks.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import mimetypes
from pathlib import Path
from typing import Any, Literal

from src.settings import PROJECT_ROOT


AssetModality = Literal["text", "image", "audio", "video", "pdf", "unknown"]
ProcessingStatus = Literal["raw", "metadata_extracted", "processed", "unsupported", "failed"]
DerivativeKind = Literal[
    "ocr_text",
    "image_description",
    "image_embedding",
    "audio_transcript",
    "audio_embedding",
    "video_transcript",
    "video_keyframes",
    "pdf_text",
]
DerivativeStatus = Literal["planned", "ready", "failed", "skipped"]

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".tif", ".tiff"}
AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".ogg"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}
TEXT_EXTENSIONS = {".txt", ".md", ".markdown"}


def relative_source_path(path: Path, project_root: Path) -> str:
    """Return a stable POSIX source path relative to the project when possible."""
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


@dataclass(frozen=True)
class MediaDerivative:
    """A planned or produced derivative from a multimodal asset."""

    derivative_id: str
    asset_id: str
    kind: DerivativeKind
    status: DerivativeStatus
    content: str = ""
    source_path: str | None = None
    model: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


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


def stable_derivative_id(asset_id: str, kind: DerivativeKind) -> str:
    digest = hashlib.sha256(f"{asset_id}:{kind}".encode("utf-8")).hexdigest()
    return f"derivative_{digest[:16]}"


def build_planned_derivative(
    asset: AssetRecord,
    kind: DerivativeKind,
    *,
    metadata: dict[str, Any] | None = None,
) -> MediaDerivative:
    """Declare a future processing output without running a model."""
    return MediaDerivative(
        derivative_id=stable_derivative_id(asset.asset_id, kind),
        asset_id=asset.asset_id,
        kind=kind,
        status="planned",
        metadata=metadata or {},
    )


def default_processing_plan(modality: AssetModality) -> list[DerivativeKind]:
    """Return the future processing steps for a media modality."""
    if modality == "image":
        return ["ocr_text", "image_description", "image_embedding"]
    if modality == "audio":
        return ["audio_transcript", "audio_embedding"]
    if modality == "video":
        return ["video_keyframes", "video_transcript"]
    if modality == "pdf":
        return ["pdf_text", "ocr_text"]
    return []


def plan_asset_processing(asset: AssetRecord) -> list[MediaDerivative]:
    """Create planned derivatives for an asset without processing the file."""
    return [build_planned_derivative(asset, kind) for kind in default_processing_plan(asset.modality)]


def attach_derivative(asset: AssetRecord, derivative: MediaDerivative) -> AssetRecord:
    """Return a copy of an asset record with one derivative attached."""
    if derivative.asset_id != asset.asset_id:
        raise ValueError("Derivative asset_id does not match asset")
    return AssetRecord(
        schema_version=asset.schema_version,
        asset_id=asset.asset_id,
        universe_id=asset.universe_id,
        source_path=asset.source_path,
        source_name=asset.source_name,
        modality=asset.modality,
        media_type=asset.media_type,
        sha256=asset.sha256,
        size_bytes=asset.size_bytes,
        processing_status=asset.processing_status,
        derivatives=[*asset.derivatives, derivative.to_dict()],
        metadata=dict(asset.metadata),
    )


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
    asset = AssetRecord(
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
    return asset
