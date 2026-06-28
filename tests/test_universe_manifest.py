import json
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class UniverseManifestTests(unittest.TestCase):
    def test_universe_manifests_reference_existing_runtime_assets(self):
        manifest_paths = sorted((PROJECT_ROOT / "corpus" / "universes").glob("*/manifest.json"))

        self.assertGreaterEqual(len(manifest_paths), 2)
        for manifest_path in manifest_paths:
            with self.subTest(manifest=manifest_path):
                self._assert_manifest_paths_exist(manifest_path)

    def _assert_manifest_paths_exist(self, manifest_path: Path):
        data = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertTrue((PROJECT_ROOT / data["summary_path"]).exists())

        for source_file in data["source_files"]:
            self.assertTrue((PROJECT_ROOT / source_file).exists(), source_file)

        for index_config in data.get("indexes", {}).values():
            if "index_path" in index_config:
                self.assertTrue((PROJECT_ROOT / index_config["index_path"]).exists())
            if "metadata_path" in index_config:
                self.assertTrue((PROJECT_ROOT / index_config["metadata_path"]).exists())
            if "path" in index_config:
                self.assertTrue((PROJECT_ROOT / index_config["path"]).exists())

        if "knowledge_graph" in data:
            self.assertTrue((PROJECT_ROOT / data["knowledge_graph"]["path"]).exists())


if __name__ == "__main__":
    unittest.main()
