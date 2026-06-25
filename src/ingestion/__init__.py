"""Document ingestion layer."""

from src.ingestion.documents import DocumentRecord, read_documents_jsonl, write_documents_jsonl
from src.ingestion.manifests import ingest_universe_manifest, load_manifest

__all__ = [
    "DocumentRecord",
    "ingest_universe_manifest",
    "load_manifest",
    "read_documents_jsonl",
    "write_documents_jsonl",
]
