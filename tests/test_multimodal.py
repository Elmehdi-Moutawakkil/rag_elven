import tempfile
import unittest
from pathlib import Path

from src.multimodal import build_asset_record, detect_modality


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


if __name__ == "__main__":
    unittest.main()
