import unittest

from src.layer_registry import LAYER_ORDER, MODULE_REGISTRY
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

    def test_pipeline_reports_unavailable_future_module(self):
        result = execute_pipeline(["L10"], "show me an image")

        self.assertEqual(result["final_type"], "error")
        self.assertIn("Module indisponible", result["error"])


if __name__ == "__main__":
    unittest.main()
