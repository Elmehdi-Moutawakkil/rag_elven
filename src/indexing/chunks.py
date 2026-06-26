"""Chunk normalized documents for retrieval indexes."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


CHUNK_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ChunkRecord:
    """A traceable text chunk derived from a normalized document."""

    schema_version: int
    chunk_id: str
    document_id: str
    universe_id: str
    collection_id: str | None
    source_path: str
    source_name: str
    modality: str
    text: str
    start_offset: int
    end_offset: int
    metadata: dict[str, Any] = field(default_factory=dict)
    validation_status: str = "pending"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json_line(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)


def stable_chunk_id(document_id: str, index: int, start_offset: int, end_offset: int) -> str:
    digest = hashlib.sha256(f"{document_id}:{index}:{start_offset}:{end_offset}".encode("utf-8")).hexdigest()
    return f"chk_{digest[:16]}"


def chunk_text(text: str, *, chunk_size: int = 900, overlap: int = 120) -> list[tuple[str, int, int]]:
    """Split text into deterministic chunks with offsets."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0:
        raise ValueError("overlap must be non-negative")
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    text = text.strip()
    if not text:
        return []

    chunks: list[tuple[str, int, int]] = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(text_len, start + chunk_size)
        if end < text_len:
            lower_bound = start + max(1, chunk_size // 2)
            paragraph_break = text.rfind("\n\n", lower_bound, end)
            word_break = text.rfind(" ", lower_bound, end)
            split_at = max(paragraph_break, word_break)
            if split_at > start:
                end = split_at

        raw_chunk = text[start:end]
        stripped = raw_chunk.strip()
        if stripped:
            actual_start = text.find(stripped, start, end + 1)
            if actual_start == -1:
                actual_start = start
            actual_end = actual_start + len(stripped)
            chunks.append((stripped, actual_start, actual_end))

        if end >= text_len:
            break
        start = max(0, end - overlap)

    return chunks


def chunk_document(document: dict[str, Any], *, chunk_size: int = 900, overlap: int = 120) -> list[ChunkRecord]:
    """Create chunk records from one normalized document dictionary."""
    clean_content = str(document.get("clean_content", ""))
    records: list[ChunkRecord] = []
    for index, (text, start_offset, end_offset) in enumerate(
        chunk_text(clean_content, chunk_size=chunk_size, overlap=overlap)
    ):
        metadata = {
            "chunk_index": index,
            "chunk_size": chunk_size,
            "chunk_overlap": overlap,
            "document_version": document.get("version"),
            "document_sha256": document.get("sha256"),
        }
        records.append(
            ChunkRecord(
                schema_version=CHUNK_SCHEMA_VERSION,
                chunk_id=stable_chunk_id(str(document["document_id"]), index, start_offset, end_offset),
                document_id=str(document["document_id"]),
                universe_id=str(document["universe_id"]),
                collection_id=document.get("collection_id"),
                source_path=str(document["source_path"]),
                source_name=str(document.get("source_name", Path(str(document["source_path"])).name)),
                modality=str(document.get("modality", "text")),
                text=text,
                start_offset=start_offset,
                end_offset=end_offset,
                metadata=metadata,
                validation_status=str(document.get("validation_status", "pending")),
            )
        )
    return records


def chunk_documents(
    documents: Iterable[dict[str, Any]],
    *,
    chunk_size: int = 900,
    overlap: int = 120,
) -> list[ChunkRecord]:
    """Chunk a sequence of normalized documents."""
    chunks: list[ChunkRecord] = []
    for document in documents:
        chunks.extend(chunk_document(document, chunk_size=chunk_size, overlap=overlap))
    return chunks


def write_chunks_jsonl(chunks: list[ChunkRecord], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [chunk.to_json_line() for chunk in chunks]
    output_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def read_chunks_jsonl(path: Path) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            chunks.append(json.loads(line))
    return chunks
