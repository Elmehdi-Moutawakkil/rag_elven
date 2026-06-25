"""Ingest a universe manifest into normalized document records."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ingestion.documents import write_documents_jsonl  # noqa: E402
from src.ingestion.manifests import ingest_universe_manifest, load_manifest  # noqa: E402
from src.ingestion.loaders import relative_source_path  # noqa: E402


def default_output_path(universe_id: str) -> Path:
    return PROJECT_ROOT / "storage" / "processed" / universe_id / "documents.jsonl"


def default_report_path(universe_id: str) -> Path:
    return PROJECT_ROOT / "storage" / "processed" / universe_id / "ingestion_report.json"


def build_report(manifest_path: Path, output_path: Path, documents: list) -> dict:
    statuses = Counter(document.validation_status for document in documents)
    modalities = Counter(document.modality for document in documents)
    collections = Counter(document.collection_id or "unassigned" for document in documents)
    return {
        "schema_version": 1,
        "manifest_path": relative_source_path(manifest_path, PROJECT_ROOT),
        "output_path": relative_source_path(output_path, PROJECT_ROOT),
        "document_count": len(documents),
        "validation_statuses": dict(sorted(statuses.items())),
        "modalities": dict(sorted(modalities.items())),
        "collections": dict(sorted(collections.items())),
        "documents": [
            {
                "document_id": document.document_id,
                "source_path": document.source_path,
                "sha256": document.sha256,
                "version": document.version,
                "validation_status": document.validation_status,
            }
            for document in documents
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        default="corpus/universes/terran_empire/manifest.json",
        help="Path to a universe manifest, relative to the project root by default.",
    )
    parser.add_argument("--output", default=None, help="Output JSONL path.")
    parser.add_argument("--report", default=None, help="Output ingestion report path.")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = PROJECT_ROOT / manifest_path

    manifest = load_manifest(manifest_path)
    universe_id = manifest["universe_id"]
    output_path = Path(args.output) if args.output else default_output_path(universe_id)
    report_path = Path(args.report) if args.report else default_report_path(universe_id)
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path
    if not report_path.is_absolute():
        report_path = PROJECT_ROOT / report_path

    documents = ingest_universe_manifest(manifest_path, project_root=PROJECT_ROOT)
    write_documents_jsonl(documents, output_path)

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = build_report(manifest_path, output_path, documents)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    print(f"Ingested {len(documents)} document(s)")
    print(f"Documents: {relative_source_path(output_path, PROJECT_ROOT)}")
    print(f"Report:    {relative_source_path(report_path, PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
