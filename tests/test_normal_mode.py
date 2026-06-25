import unittest

from src.layer_registry import MODULE_REGISTRY
from src.normal_mode import NORMAL_PIPELINES, normalize_input_for_route, pipeline_for_route


class NormalModeTests(unittest.TestCase):
    def test_official_pipelines_reference_known_available_modules(self):
        for route, modules in NORMAL_PIPELINES.items():
            self.assertEqual(pipeline_for_route(route), modules)
            self.assertTrue(modules)
            for module_id in modules:
                self.assertIn(module_id, MODULE_REGISTRY)
                self.assertTrue(MODULE_REGISTRY[module_id].available)

    def test_translate_input_prefix_is_removed(self):
        self.assertEqual(
            normalize_input_for_route("translate", "Translate: the warrior walks."),
            "the warrior walks.",
        )
        self.assertEqual(
            normalize_input_for_route("qa", "Translate: elda"),
            "Translate: elda",
        )

    def test_unknown_route_raises_clear_error(self):
        with self.assertRaisesRegex(ValueError, "Unknown Normal Mode route"):
            pipeline_for_route("missing")


if __name__ == "__main__":
    unittest.main()
