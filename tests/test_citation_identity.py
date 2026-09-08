import unittest

from src.citations import (
    CITATION_UNAVAILABLE,
    citation_excerpt_id,
    citation_version_id,
    format_citation_identity,
    legacy_faiss_chunk_id,
    normalize_chunk_for_citation,
    resolve_citation_identity,
    stable_source_id,
)
from src.indexing.chunks import chunk_document


class CitationIdentityTests(unittest.TestCase):
    def _document(self, content: str, sha256: str = "a" * 64) -> dict:
        return {
            "document_id": "doc_1",
            "universe_id": "mirror",
            "collection_id": "lore",
            "source_path": "lore/history.txt",
            "source_name": "history.txt",
            "clean_content": content,
            "sha256": sha256,
            "version": f"sha256:{sha256[:12]}",
            "metadata": {"canon_status": "canon", "topic": "history"},
        }

    def test_rebuild_of_same_document_has_identical_citation_identity(self):
        document = self._document("Alpha beta gamma. " * 30)

        first = chunk_document(document, chunk_size=80, overlap=10)
        second = chunk_document(document, chunk_size=80, overlap=10)

        self.assertEqual([chunk.to_dict() for chunk in first], [chunk.to_dict() for chunk in second])
        self.assertTrue(first[0].metadata["citation_version_id"].startswith("cver_"))
        self.assertTrue(first[0].metadata["citation_excerpt_id"].startswith("cexp_"))
        self.assertEqual(len({chunk.metadata["citation_version_id"] for chunk in first}), 1)
        self.assertEqual(first[0].metadata["canon_status"], "canon")
        self.assertEqual(first[0].metadata["document_sha256"], "a" * 64)

    def test_same_length_content_change_changes_chunk_and_citation_versions(self):
        first_document = self._document("A" * 80, sha256="a" * 64)
        second_document = self._document("B" * 80, sha256="b" * 64)

        first = chunk_document(first_document, chunk_size=80, overlap=0)[0]
        second = chunk_document(second_document, chunk_size=80, overlap=0)[0]

        self.assertNotEqual(first.chunk_id, second.chunk_id)
        self.assertNotEqual(first.metadata["citation_version_id"], second.metadata["citation_version_id"])
        self.assertNotEqual(first.metadata["citation_excerpt_id"], second.metadata["citation_excerpt_id"])

    def test_source_identity_isolated_by_universe(self):
        self.assertNotEqual(
            stable_source_id("mirror", "lore/history.txt"),
            stable_source_id("prime", "lore/history.txt"),
        )

    def test_document_hash_versions_even_when_excerpt_is_unchanged(self):
        first = citation_version_id("mirror", "lore/history.txt", "same excerpt", document_sha256="a" * 64)
        second = citation_version_id("mirror", "lore/history.txt", "same excerpt", document_sha256="b" * 64)

        self.assertNotEqual(first, second)
        self.assertNotEqual(
            citation_excerpt_id(first, "same excerpt", start_offset=0, end_offset=12),
            citation_excerpt_id(second, "same excerpt", start_offset=0, end_offset=12),
        )

    def test_identity_golden_values_are_stable_across_compatibility_fix(self):
        version = citation_version_id("mirror", "lore/history.txt", "same excerpt", document_sha256="a" * 64)

        self.assertEqual(version, "cver_f90cf96644409841b63107b6")
        self.assertEqual(
            citation_excerpt_id(version, "same excerpt", start_offset=0, end_offset=12),
            "cexp_fbb9245ce1e35424d208db38",
        )
        self.assertEqual(
            legacy_faiss_chunk_id("notes.txt", "same evidence", universe_id="mirror", page=4),
            "legacy_abbced0b45223dffa0c95ed1",
        )

    def test_legacy_faiss_identity_ignores_search_rank(self):
        first = legacy_faiss_chunk_id("notes.txt", "same evidence", universe_id="mirror", page=4)
        second = legacy_faiss_chunk_id("notes.txt", "same evidence", universe_id="mirror", page=4)

        self.assertEqual(first, second)

    def test_normalizer_preserves_provenance_and_resolves_only_exact_version(self):
        raw = {
            "chunk_id": "legacy_unsafe_id",
            "document_id": "doc_1",
            "universe_id": "mirror",
            "source_path": "lore/history.txt",
            "text": "immutable excerpt",
            "start_offset": 8,
            "end_offset": 25,
            "metadata": {"canon_status": "canon", "document_sha256": "a" * 64},
        }
        normalized = normalize_chunk_for_citation(raw)
        citation = format_citation_identity(normalized)

        self.assertEqual(normalized["metadata"]["canon_status"], "canon")
        self.assertEqual(normalized["metadata"]["document_sha256"], "a" * 64)
        self.assertEqual(resolve_citation_identity(citation, [raw])["text"], "immutable excerpt")
        self.assertEqual(resolve_citation_identity("lore/history.txt#legacy_unsafe_id", [raw]), CITATION_UNAVAILABLE)

        changed = dict(raw, text="changed!! excerpt")
        self.assertEqual(resolve_citation_identity(citation, [changed]), CITATION_UNAVAILABLE)


if __name__ == "__main__":
    unittest.main()
