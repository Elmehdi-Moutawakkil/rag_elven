"""Build retrieval chunks for a universe."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.indexing.build import build_text_index  # noqa: E402
from src.ingestion.loaders import relative_source_path  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe", default="terran_empire")
    parser.add_argument("--documents", default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--chunk-size", type=int, default=900)
    parser.add_argument("--overlap", type=int, default=120)
    args = parser.parse_args()

    documents_path = Path(args.documents) if args.documents else None
    output_dir = Path(args.output_dir) if args.output_dir else None
    if documents_path is not None and not documents_path.is_absolute():
        documents_path = PROJECT_ROOT / documents_path
    if output_dir is not None and not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir

    manifest = build_text_index(
        universe_id=args.universe,
        documents_path=documents_path,
        output_dir=output_dir,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
    )
    print(f"Built {manifest['chunk_count']} chunk(s) from {manifest['document_count']} document(s)")
    print(f"Chunks: {manifest['chunks_path']}")
    print(f"Manifest: {relative_source_path((output_dir or PROJECT_ROOT / 'indexes' / args.universe / 'text') / 'manifest.json', PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
