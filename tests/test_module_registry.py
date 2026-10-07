import unittest

from src.layer_registry import LAYER_META, LAYER_ORDER, MODULE_REGISTRY
from src.pipeline_executor import execute_pipeline


class ModuleRegistryTests(unittest.TestCase):
    def test_all_layers_have_module_definitions(self):
        self.assertEqual(set(LAYER_ORDER), set(MODULE_REGISTRY))

        for module_id in LAYER_ORDER:
            module = MODULE_REGISTRY[module_id]
            self.assertEqual(module.id, module_id)
            self.assertTrue(module.name)
            self.assertTrue(module.description)
            self.assertIsInstance(module.input_types, list)
            self.assertTrue(module.output_type)
            self.assertIsInstance(module.dependencies, list)
            self.assertIn(module.status, {"stable", "experimental", "future", "disabled"})
            self.assertIn(module.cost, {"free", "groq", "claude", "gpu", "local", "unknown"})
            self.assertIn(module.confidence, {"high", "medium", "low", "unknown"})

    def test_future_modules_are_declared_but_not_available(self):
        for module_id in ("L10", "L11", "L12"):
            module = MODULE_REGISTRY[module_id]
            self.assertEqual(module.status, "future")
            self.assertFalse(module.available)
            self.assertIsNone(module.run)

    def test_l08_metadata_describes_configurable_lore_provider(self):
        meta = LAYER_META["L08"]

        self.assertNotIn("Anthropic", meta.description)
        self.assertNotIn("Claude", meta.description)
        self.assertEqual(meta.cost, "unknown")
        self.assertNotIn("ANTHROPIC_API_KEY", meta.dependencies)
        self.assertIn("fournisseur de lore sélectionné", meta.description.lower())

    def test_l01_metadata_describes_configurable_query_provider(self):
        meta = LAYER_META["L01"]

        self.assertEqual(meta.cost, "unknown")
        self.assertNotIn("GROQ_API_KEY", meta.dependencies)
        self.assertIn("fournisseur q&a configuré", meta.description.lower())

    def test_pipeline_reports_unavailable_future_module(self):
        result = execute_pipeline(["L10"], "show me an image")

        self.assertEqual(result["final_type"], "error")
        self.assertIn("Module indisponible", result["error"])

    def test_l02_uses_unified_retrieval_adapter_for_universe_chunks(self):
        result = execute_pipeline(
            ["L02"],
            "Mirror Spock reforms",
            resources={"universe_id": "terran_empire"},
        )

        self.assertIsNone(result["error"])
        self.assertEqual(result["final_type"], "json_chunks")
        self.assertTrue(result["final_output"])
        self.assertIn("source_path", result["final_output"][0])

    def test_l02_rejects_legacy_faiss_contract_without_registered_handle(self):
        class FakeModel:
            def encode(self, values, normalize_embeddings=True):
                import numpy as np

                return np.array([[1.0, 0.0]], dtype="float32")

        class FakeIndex:
            def search(self, vector, k):
                import numpy as np

                return np.array([[0.25]], dtype="float32"), np.array([[0]], dtype="int64")

        result = execute_pipeline(
            ["L02"],
            "legacy query",
            resources={
                "model": FakeModel(),
                "index": FakeIndex(),
                "meta": [{"text": "legacy FAISS passage", "source": "legacy.txt", "page": 1}],
            },
        )

        self.assertIn("UNIVERSE_REQUIRED", result["error"])


if __name__ == "__main__":
    unittest.main()
