import tempfile
import unittest
from pathlib import Path

from src.indexing.build import build_text_index
from src.indexing.chunks import chunk_text, read_chunks_jsonl
from src.retrieval_hybrid import search_chunks


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class IndexingRetrievalTests(unittest.TestCase):
    def test_chunk_text_keeps_offsets_and_overlap_controlled(self):
        text = "Alpha beta gamma. " * 80

        chunks = chunk_text(text, chunk_size=120, overlap=20)

        self.assertGreater(len(chunks), 1)
        for chunk, start, end in chunks:
            self.assertEqual(text.strip()[start:end], chunk)
            self.assertLessEqual(len(chunk), 120)

    def test_build_text_index_from_processed_documents(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "index"
            manifest = build_text_index(
                universe_id="terran_empire",
                documents_path=PROJECT_ROOT / "storage" / "processed" / "terran_empire" / "documents.jsonl",
                output_dir=output_dir,
                chunk_size=700,
                overlap=80,
            )
            chunks = read_chunks_jsonl(output_dir / "chunks.jsonl")

        self.assertEqual(manifest["document_count"], 7)
        self.assertGreater(manifest["chunk_count"], 7)
        self.assertEqual(len(chunks), manifest["chunk_count"])
        first = chunks[0]
        self.assertIn("chunk_id", first)
        self.assertIn("document_id", first)
        self.assertIn("source_path", first)
        self.assertIn("start_offset", first)
        self.assertIn("end_offset", first)

    def test_search_chunks_returns_scored_sourced_hits(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "index"
            build_text_index(
                universe_id="terran_empire",
                documents_path=PROJECT_ROOT / "storage" / "processed" / "terran_empire" / "documents.jsonl",
                output_dir=output_dir,
                chunk_size=800,
                overlap=100,
            )
            chunks = read_chunks_jsonl(output_dir / "chunks.jsonl")

        hits = search_chunks("Spock reforms weakened the Empire", chunks, k=3)

        self.assertGreaterEqual(len(hits), 1)
        self.assertGreater(hits[0].score, 0)
        self.assertIn("Spock", hits[0].text)
        self.assertTrue(hits[0].citation)
        self.assertIn("spock", hits[0].match_terms)

    def test_search_chunks_filters_by_collection(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "index"
            build_text_index(
                universe_id="terran_empire",
                documents_path=PROJECT_ROOT / "storage" / "processed" / "terran_empire" / "documents.jsonl",
                output_dir=output_dir,
            )
            chunks = read_chunks_jsonl(output_dir / "chunks.jsonl")

        hits = search_chunks("Alliance Cardassian Klingon", chunks, k=5, filters={"collection_id": "lore"})

        self.assertTrue(hits)
        self.assertEqual({hit.collection_id for hit in hits}, {"lore"})


if __name__ == "__main__":
    unittest.main()
