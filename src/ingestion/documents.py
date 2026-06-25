"""Canonical document records produced by ingestion."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any, Literal


ValidationStatus = Literal["draft", "pending", "validated", "rejected", "superseded"]
IngestionStatus = Literal["ingested", "unsupported", "failed"]

DOCUMENT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class DocumentRecord:
    """Normalized representation of one ingested source document."""

    schema_version: int
    document_id: str
    universe_id: str
    collection_id: str | None
    source_path: str
    source_name: str
    modality: str
    media_type: str
    raw_content: str
    clean_content: str
    metadata: dict[str, Any]
    sha256: str
    version: str
    validation_status: ValidationStatus = "pending"
    annotations: list[dict[str, Any]] = field(default_factory=list)
    ingestion_status: IngestionStatus = "ingested"
    media: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary."""
        return asdict(self)

    def to_json_line(self) -> str:
        """Return a stable JSONL representation."""
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)


def sha256_bytes(content: bytes) -> str:
    """Hash raw source bytes."""
    return hashlib.sha256(content).hexdigest()


def stable_document_id(universe_id: str, source_path: str) -> str:
    """Create a stable ID from the universe and source path."""
    digest = hashlib.sha256(f"{universe_id}:{source_path}".encode("utf-8")).hexdigest()
    return f"doc_{digest[:16]}"


def version_from_hash(source_hash: str) -> str:
    """Create a deterministic version label from the source hash."""
    return f"sha256:{source_hash[:12]}"


def write_documents_jsonl(documents: list[DocumentRecord], output_path: Path) -> None:
    """Write normalized documents to JSONL."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [document.to_json_line() for document in documents]
    output_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def read_documents_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read normalized documents from JSONL."""
    documents: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            documents.append(json.loads(line))
    return documents
