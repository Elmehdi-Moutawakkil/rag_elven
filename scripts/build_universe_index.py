"""Build FAISS index for a specific universe.

Usage:
    python scripts/build_universe_index.py --universe terran_empire
    python scripts/build_universe_index.py --universe terran_empire --data-dir data/universes/terran_empire
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.text_splitter import split_corpus
from src.embeddings import load_model, encode_chunks, save_index
import faiss
import json
import numpy as np


def build_universe_index(universe: str, data_dir: str | None = None, output_dir: str | None = None) -> None:
    data_path   = data_dir   or f"data/universes/{universe}"
    output_path = output_dir or f"vector_db/{universe}"

    Path(output_path).mkdir(parents=True, exist_ok=True)

    index_path = f"{output_path}/faiss.index"
    meta_path  = f"{output_path}/metadata.json"

    print(f"[1/3] Chunking corpus from {data_path}…")
    chunks = split_corpus(data_path)
    print(f"  {len(chunks)} chunks produced")

    if not chunks:
        print("No chunks found — check that lore files exist in the data directory.")
        return

    print("[2/3] Encoding chunks…")
    model   = load_model()
    vectors = encode_chunks(chunks, model)
    print(f"  Vectors shape: {vectors.shape}")

    print(f"[3/3] Saving index to {output_path}…")
    dimension = vectors.shape[1]
    index     = faiss.IndexFlatL2(dimension)
    index.add(vectors)
    faiss.write_index(index, index_path)

    metadata = [c["metadata"] | {"text": c["text"]} for c in chunks]
    Path(meta_path).write_text(json.dumps(metadata, ensure_ascii=False, indent=2))

    print(f"Done. {index.ntotal} vectors → {index_path}")
    print(f"       metadata         → {meta_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe",  required=True, help="Universe identifier (e.g. terran_empire)")
    parser.add_argument("--data-dir",  default=None,  help="Path to corpus data directory")
    parser.add_argument("--output-dir",default=None,  help="Path to output directory for the index")
    args = parser.parse_args()

    build_universe_index(args.universe, args.data_dir, args.output_dir)
