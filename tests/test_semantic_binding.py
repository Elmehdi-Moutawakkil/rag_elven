import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import faiss
import numpy as np

from src.citations import resolve_citation_identity
from src.retrieval_adapter import RetrievalStatus, available_citation_records, retrieve_evidence_result
from src.universe_registry import UniverseRegistry, load_semantic_handle


class FakeModel:
    def __init__(self, vector):
        self.vector = vector

    def encode(self, _values, normalize_embeddings=True):
        return np.array([self.vector], dtype="float32")


class SemanticBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self._write_universe("alpha")
        self._write_universe("beta")
        self.registry = UniverseRegistry(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def _write_universe(self, universe_id: str):
        (self.root / "corpus" / "universes" / universe_id).mkdir(parents=True)
        (self.root / "data" / universe_id).mkdir(parents=True)
        (self.root / "data" / universe_id / "source.txt").write_text("source", encoding="utf-8")
        vector_dir = self.root / "vector_db" / universe_id
        vector_dir.mkdir(parents=True)
        index = faiss.IndexFlatL2(2)
        index.add(np.array([[0.0, 0.0], [1.0, 1.0]], dtype="float32"))
        faiss.write_index(index, str(vector_dir / "faiss.index"))
        metadata = [
            {"source": f"data/{universe_id}/source.txt", "text": "same immutable passage", "page": 1, "doc_type": "lore"},
            {"source": f"data/{universe_id}/source.txt", "text": "same immutable passage", "page": 1, "doc_type": "lore"},
        ]
        (vector_dir / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
        manifest = {
            "schema_version": 1,
            "universe_id": universe_id,
            "display_name": universe_id,
            "status": "test",
            "source_files": [f"data/{universe_id}/source.txt"],
            "collections": [{"collection_id": "lore", "source_path": f"data/{universe_id}", "canon_status": "canon"}],
            "indexes": {"text": {"type": "faiss", "index_path": f"vector_db/{universe_id}/faiss.index", "metadata_path": f"vector_db/{universe_id}/metadata.json"}},
        }
        (self.root / "corpus" / "universes" / universe_id / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    def _retrieve(self, **kwargs):
        with patch("src.retrieval_adapter.get_universe_registry", return_value=self.registry):
            return retrieve_evidence_result(**kwargs)

    def test_two_registered_universes_load_bound_handles(self):
        self.assertEqual(self.registry.ids(), ("alpha", "beta"))
        self.assertEqual(load_semantic_handle("alpha", registry=self.registry).index.ntotal, 2)
        self.assertEqual(load_semantic_handle("beta", registry=self.registry).index.ntotal, 2)

    def test_swapped_same_shape_index_is_rejected_before_search(self):
        handle = load_semantic_handle("alpha", registry=self.registry)
        swapped = load_semantic_handle("beta", registry=self.registry).index
        object.__setattr__(handle, "index", swapped)

        result = self._retrieve(query="passage", universe_id="alpha", mode="semantic", model=FakeModel([0, 0]), semantic_handle=handle)

        self.assertEqual(result.status, RetrievalStatus.ERROR)
        self.assertFalse(result.hits)

    def test_metadata_mutation_and_deleted_artifact_are_typed_errors(self):
        handle = load_semantic_handle("alpha", registry=self.registry)
        object.__setattr__(handle, "metadata", [])
        mutated = self._retrieve(query="passage", universe_id="alpha", mode="semantic", model=FakeModel([0, 0]), semantic_handle=handle)
        self.assertEqual(mutated.status, RetrievalStatus.ERROR)

        handle = load_semantic_handle("alpha", registry=self.registry)
        handle.index_path.unlink()
        deleted = self._retrieve(query="passage", universe_id="alpha", mode="semantic", model=FakeModel([0, 0]), semantic_handle=handle)
        self.assertEqual(deleted.status, RetrievalStatus.ERROR)

    def test_rank_change_keeps_semantic_citation_and_exact_resolution(self):
        handle = load_semantic_handle("alpha", registry=self.registry)
        near_zero = self._retrieve(query="first", universe_id="alpha", mode="semantic", model=FakeModel([0, 0]), semantic_handle=handle, k=1)
        near_one = self._retrieve(query="second", universe_id="alpha", mode="semantic", model=FakeModel([1, 1]), semantic_handle=handle, k=1)

        self.assertEqual(near_zero.status, RetrievalStatus.SUCCESS)
        self.assertEqual(near_one.status, RetrievalStatus.SUCCESS)
        self.assertEqual(near_zero.hits[0]["citation"], near_one.hits[0]["citation"])
        with patch("src.retrieval_adapter.get_universe_registry", return_value=self.registry):
            records = available_citation_records("alpha")
        self.assertEqual(resolve_citation_identity(near_zero.hits[0]["citation"], records)["text"], "same immutable passage")

    def test_no_results_is_distinct_from_missing_and_required_hybrid(self):
        handle = load_semantic_handle("alpha", registry=self.registry)
        with patch("src.retrieval_adapter.search_faiss", return_value=[]):
            no_results = self._retrieve(query="absent", universe_id="alpha", mode="semantic", model=FakeModel([0, 0]), semantic_handle=handle)
        missing = self._retrieve(query="absent", universe_id="alpha", mode="semantic")
        hybrid = self._retrieve(query="absent", universe_id="alpha", mode="hybrid", model=FakeModel([0, 0]), semantic_handle=handle)
        auto = self._retrieve(query="passage", universe_id="alpha", mode="auto", model=FakeModel([0, 0]), semantic_handle=handle)

        self.assertEqual(no_results.status, RetrievalStatus.NO_RESULTS)
        self.assertEqual(missing.status, RetrievalStatus.INDEX_MISSING)
        self.assertEqual(hybrid.status, RetrievalStatus.INDEX_MISSING)
        self.assertEqual(auto.status, RetrievalStatus.SUCCESS)
        self.assertTrue(auto.degraded)
        self.assertIn("Lexical index unavailable", auto.warnings)


if __name__ == "__main__":
    unittest.main()
