import json
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class UniverseManifestTests(unittest.TestCase):
    def test_terran_empire_manifest_references_existing_runtime_assets(self):
        manifest_path = PROJECT_ROOT / "corpus" / "universes" / "terran_empire" / "manifest.json"
        data = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(data["universe_id"], "terran_empire")
        self.assertTrue((PROJECT_ROOT / data["summary_path"]).exists())

        for source_file in data["source_files"]:
            self.assertTrue((PROJECT_ROOT / source_file).exists(), source_file)

        text_index = data["indexes"]["text"]
        self.assertTrue((PROJECT_ROOT / text_index["index_path"]).exists())
        self.assertTrue((PROJECT_ROOT / text_index["metadata_path"]).exists())
        self.assertTrue((PROJECT_ROOT / data["knowledge_graph"]["path"]).exists())


if __name__ == "__main__":
    unittest.main()
