import unittest
from unittest.mock import patch

from src.citations import resolve_citation_identity
from src.indexing.chunks import read_chunks_jsonl
from src.retrieval_adapter import (
    RetrievalStatus,
    _fuse_ranked_hits,
    available_citation_records,
    retrieve_evidence_result,
)
from src.universe_registry import UniverseRegistryError, get_universe_registry, validate_source_path


class RetrievalContractTests(unittest.TestCase):
    def test_rrf_fusion_uses_rank_not_incompatible_raw_score_scales(self):
        lexical = [
            {"chunk_id": "a", "source_path": "a.txt", "text": "A", "lexical_score": 99.0},
            {"chunk_id": "a2", "source_path": "a.txt", "text": "A second passage", "lexical_score": 80.0},
            {"chunk_id": "b", "source_path": "b.txt", "text": "B", "lexical_score": 50.0},
        ]
        semantic = [
            {"chunk_id": "b", "source_path": "b.txt", "text": "B", "semantic_score": 0.8},
            {"chunk_id": "a", "source_path": "a.txt", "text": "A", "semantic_score": 0.9},
        ]

        fused = _fuse_ranked_hits(lexical, semantic)

        self.assertEqual({hit["chunk_id"] for hit in fused}, {"a", "b"})
        self.assertEqual(len({hit["source_path"] for hit in fused}), len(fused))
        self.assertTrue(all(0.0 <= hit["relevance_score"] <= 1.0 for hit in fused))
        self.assertTrue(all(hit["score"] == hit["relevance_score"] for hit in fused))
        self.assertEqual(fused[0]["relevance_score"], 1.0)
        self.assertLess(fused[1]["relevance_score"], 1.0)
        self.assertEqual(fused[0]["diagnostics"]["fusion_method"], "rrf")
        self.assertEqual(fused[0]["diagnostics"]["lexical_chunk_rank"], 1)

    def test_missing_and_unknown_universe_return_typed_results_before_lookup(self):
        self.assertEqual(retrieve_evidence_result("question", universe_id=None).status, RetrievalStatus.UNIVERSE_REQUIRED)
        self.assertEqual(retrieve_evidence_result("question", universe_id="missing").status, RetrievalStatus.UNIVERSE_UNKNOWN)

    def test_registered_terran_lexical_search_has_versioned_citations(self):
        result = retrieve_evidence_result("Mirror Spock reforms", universe_id="terran_empire", mode="lexical", k=2)

        self.assertEqual(result.status, RetrievalStatus.SUCCESS)
        self.assertEqual(result.universe_id, "terran_empire")
        self.assertTrue(result.hits)
        self.assertTrue(result.hits[0]["citation"].startswith("citation:v1:"))
        self.assertEqual(result.hits[0]["metadata"]["canon_status"], "canon")
        records = read_chunks_jsonl(get_universe_registry().require("terran_empire").text_chunks_path)
        self.assertEqual(resolve_citation_identity(result.hits[0]["citation"], records)["text"], result.hits[0]["text"])

    def test_intendant_retrieval_exposes_curated_episode_provenance(self):
        result = retrieve_evidence_result("who is the intendant?", universe_id="terran_empire", mode="lexical", k=1)

        self.assertEqual(result.status, RetrievalStatus.SUCCESS)
        hit = result.hits[0]
        self.assertEqual(hit["source_name"], "key_figures.txt")
        self.assertEqual(hit["episode_refs"][0]["title"], "Crossover")
        self.assertEqual(hit["episode_refs"][0]["series"], "Star Trek: Deep Space Nine")
        self.assertEqual(hit["episode_refs"][0]["provenance_version"], 1)
        self.assertEqual(hit["metadata"]["episode_refs"], hit["episode_refs"])

    def test_cross_universe_and_traversal_chunk_sources_are_rejected(self):
        config = get_universe_registry().require("terran_empire")
        with self.assertRaises(UniverseRegistryError):
            validate_source_path(config, "data/universes/terran_empire/lore/../../tolkien/private.txt")

    def test_current_semantic_metadata_citation_resolves_exactly(self):
        semantic = next(record for record in available_citation_records("terran_empire") if record.get("retrieval_engine") == "faiss")
        resolved = resolve_citation_identity(semantic["citation"], available_citation_records("terran_empire"))

        self.assertEqual(resolved["text"], semantic["text"])

    def test_semantic_records_receive_manifest_episode_provenance(self):
        semantic = next(
            record
            for record in available_citation_records("terran_empire")
            if record.get("retrieval_engine") == "faiss" and record.get("source_name") == "key_figures.txt"
        )

        self.assertEqual(semantic["episode_refs"][0]["title"], "Crossover")
        self.assertEqual(semantic["metadata"]["episode_refs"], semantic["episode_refs"])

    def test_semantic_mode_requires_a_bound_handle(self):
        result = retrieve_evidence_result("question", universe_id="tolkien", mode="semantic")

        self.assertEqual(result.status, RetrievalStatus.INDEX_MISSING)

    def test_raw_semantic_triplet_is_rejected_even_if_metadata_is_present(self):
        result = retrieve_evidence_result(
            "question",
            universe_id="tolkien",
            mode="semantic",
            model=object(),
            index=object(),
            metadata=[{"text": "unsafe"}],
        )

        self.assertEqual(result.status, RetrievalStatus.ERROR)
        self.assertIn("SemanticIndexHandle", result.error)

    def test_l02_failure_stops_l13_before_answer_provider(self):
        from src.pipeline_executor import execute_pipeline

        with patch("src.llm.answer") as answer:
            result = execute_pipeline(["L02", "L13"], "question", resources={"universe_id": None})

        self.assertIsNotNone(result["error"])
        self.assertIn("UNIVERSE_REQUIRED", result["error"])
        answer.assert_not_called()

    def test_executor_preflight_stops_l01_before_query_rewriter(self):
        from src.pipeline_executor import execute_pipeline

        with patch("src.query_rewriter.rewrite_query") as rewriter:
            result = execute_pipeline(["L01", "L02"], "question", resources={"universe_id": None})

        self.assertIn("UNIVERSE_REQUIRED", result["error"])
        rewriter.assert_not_called()

    def test_executor_blocks_terran_translation_layers_before_parser(self):
        from src.pipeline_executor import execute_pipeline

        with patch("src.ir.parse_english") as parser:
            result = execute_pipeline(["L04", "L05", "L06"], "warrior walks", resources={"universe_id": "terran_empire"})

        self.assertIn("CAPABILITY_UNSUPPORTED", result["error"])
        parser.assert_not_called()

    def test_tolkien_dictionary_evidence_can_continue_after_lexical_no_results(self):
        from src.pipeline_executor import execute_pipeline
        from src.retrieval_adapter import RetrievalResult

        no_results = RetrievalResult(status=RetrievalStatus.NO_RESULTS, universe_id="tolkien", engines=["semantic"])
        with patch("src.retrieval_adapter.retrieve_evidence_result", return_value=no_results), patch("src.llm.answer", return_value="dictionary-backed answer") as answer:
            result = execute_pipeline(["L02", "L03", "L13"], "elda", resources={"universe_id": "tolkien"})

        self.assertIsNone(result["error"])
        self.assertEqual(result["final_output"], "dictionary-backed answer")
        answer.assert_called_once()


if __name__ == "__main__":
    unittest.main()
