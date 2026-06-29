import json
import tempfile
import unittest
from pathlib import Path

from src.ingestion.documents import read_documents_jsonl, write_documents_jsonl
from src.ingestion.loaders import UnsupportedFormatError, load_document, load_media_document, load_text_document
from src.ingestion.manifests import ingest_universe_manifest


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class IngestionTests(unittest.TestCase):
    def test_load_text_document_normalizes_markdown_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "note.md"
            source.write_text("# Title\n\nLine   with    spaces.\n", encoding="utf-8")

            document = load_text_document(
                source,
                project_root=root,
                universe_id="demo",
                collection_id="notes",
                metadata={"canon_status": "draft"},
            )

        self.assertEqual(document.schema_version, 1)
        self.assertEqual(document.universe_id, "demo")
        self.assertEqual(document.collection_id, "notes")
        self.assertEqual(document.source_path, "note.md")
        self.assertEqual(document.modality, "text")
        self.assertEqual(document.validation_status, "pending")
        self.assertEqual(len(document.sha256), 64)
        self.assertTrue(document.version.startswith("sha256:"))
        self.assertIn("Line with spaces.", document.clean_content)
        self.assertEqual(document.metadata["canon_status"], "draft")

    def test_load_media_document_stores_metadata_without_ai_processing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "image.png"
            source.write_bytes(b"not really an image")

            document = load_media_document(
                source,
                project_root=root,
                universe_id="demo",
                collection_id="assets",
                metadata={"canon_status": "draft"},
            )

        self.assertEqual(document.modality, "image")
        self.assertEqual(document.raw_content, "")
        self.assertEqual(document.clean_content, "")
        self.assertEqual(document.metadata["processing_mode"], "metadata_only")
        self.assertEqual(document.metadata["ai_models_used"], [])
        self.assertEqual(
            [item["kind"] for item in document.media["planned_derivatives"]],
            ["ocr_text", "image_description", "image_embedding"],
        )

    def test_loader_dispatches_media_documents(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "voice.wav"
            source.write_bytes(b"not really audio")

            document = load_document(
                source,
                project_root=root,
                universe_id="demo",
                collection_id=None,
            )

        self.assertEqual(document.modality, "audio")

    def test_loader_rejects_unsupported_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "asset.bin"
            source.write_bytes(b"unknown")

            with self.assertRaises(UnsupportedFormatError):
                load_document(
                    source,
                    project_root=root,
                    universe_id="demo",
                    collection_id=None,
                )

    def test_terran_manifest_ingests_all_text_sources(self):
        manifest_path = PROJECT_ROOT / "corpus" / "universes" / "terran_empire" / "manifest.json"

        documents = ingest_universe_manifest(manifest_path, project_root=PROJECT_ROOT)

        self.assertEqual(len(documents), 7)
        self.assertEqual({document.universe_id for document in documents}, {"terran_empire"})
        self.assertEqual({document.collection_id for document in documents}, {"lore"})
        self.assertEqual({document.modality for document in documents}, {"text"})
        self.assertTrue(all(document.clean_content for document in documents))
        self.assertTrue(all(document.metadata["canon_status"] == "canon" for document in documents))

    def test_documents_jsonl_round_trip(self):
        manifest_path = PROJECT_ROOT / "corpus" / "universes" / "terran_empire" / "manifest.json"
        documents = ingest_universe_manifest(manifest_path, project_root=PROJECT_ROOT)[:2]

        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "documents.jsonl"
            write_documents_jsonl(documents, output_path)
            loaded = read_documents_jsonl(output_path)

        self.assertEqual(len(loaded), 2)
        self.assertEqual(loaded[0]["document_id"], documents[0].document_id)
        self.assertIn("raw_content", loaded[0])
        self.assertIn("clean_content", loaded[0])
        json.dumps(loaded, ensure_ascii=False)


if __name__ == "__main__":
    unittest.main()
