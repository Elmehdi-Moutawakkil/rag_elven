import tempfile
import unittest
from pathlib import Path

from src.multimodal import (
    attach_derivative,
    build_asset_record,
    build_planned_derivative,
    detect_modality,
    plan_asset_processing,
)


class MultimodalTests(unittest.TestCase):
    def test_detect_modality_by_extension(self):
        self.assertEqual(detect_modality(Path("image.png")), "image")
        self.assertEqual(detect_modality(Path("voice.wav")), "audio")
        self.assertEqual(detect_modality(Path("book.pdf")), "pdf")
        self.assertEqual(detect_modality(Path("notes.md")), "text")
        self.assertEqual(detect_modality(Path("asset.bin")), "unknown")

    def test_build_asset_record_hashes_and_types_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "frame.png"
            image.write_bytes(b"fake image bytes")

            record = build_asset_record(image, universe_id="demo", project_root=root)

        self.assertEqual(record.universe_id, "demo")
        self.assertEqual(record.source_path, "frame.png")
        self.assertEqual(record.modality, "image")
        self.assertEqual(record.processing_status, "metadata_extracted")
        self.assertEqual(len(record.sha256), 64)
        self.assertTrue(record.asset_id.startswith("asset_"))

    def test_plan_image_processing_without_running_models(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "frame.png"
            image.write_bytes(b"fake image bytes")
            record = build_asset_record(image, universe_id="demo", project_root=root)

            plan = plan_asset_processing(record)

        self.assertEqual([item.kind for item in plan], ["ocr_text", "image_description", "image_embedding"])
        self.assertEqual({item.status for item in plan}, {"planned"})
        self.assertEqual({item.model for item in plan}, {None})

    def test_attach_derivative_records_external_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio = root / "voice.wav"
            audio.write_bytes(b"fake audio bytes")
            record = build_asset_record(audio, universe_id="demo", project_root=root)

            derivative = build_planned_derivative(record, "audio_transcript")
            updated = attach_derivative(record, derivative)

        self.assertEqual(len(updated.derivatives), 1)
        self.assertEqual(updated.derivatives[0]["kind"], "audio_transcript")


if __name__ == "__main__":
    unittest.main()
