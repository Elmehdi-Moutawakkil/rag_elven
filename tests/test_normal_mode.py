import unittest

from src.layer_registry import MODULE_REGISTRY
from src.query_rewriter import _SYSTEM_PROMPT
from src.router import _ROUTER_PROMPT, classify_request
from src.normal_mode import (
    NORMAL_PIPELINES,
    detect_universe_for_input,
    normalize_input_for_route,
    pipeline_for_route,
    resolve_normal_universe,
)


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

    def test_detect_universe_routes_star_trek_to_terran(self):
        self.assertEqual(detect_universe_for_input("Who is Mirror Spock?"), "terran_empire")
        self.assertEqual(detect_universe_for_input("What is the Agony Booth?"), "terran_empire")
        self.assertEqual(detect_universe_for_input("What does elda mean?"), "tolkien")

    def test_non_tolkien_qa_pipeline_excludes_elvish_dictionary(self):
        self.assertEqual(pipeline_for_route("qa", universe_id="terran_empire"), ["L01", "L02", "L13"])
        self.assertEqual(pipeline_for_route("qa", universe_id="tolkien"), ["L01", "L02", "L03", "L13"])

    def test_non_tolkien_lore_pipeline_keeps_universe_agnostic_constraints(self):
        self.assertEqual(pipeline_for_route("lore", universe_id="terran_empire"), ["L01", "L02", "L07", "L08", "L09"])

    def test_resolve_normal_universe_matches_ui_selection_rules(self):
        self.assertEqual(resolve_normal_universe("qa", "Who is Mirror Spock?", "Auto"), "terran_empire")
        self.assertEqual(resolve_normal_universe("qa", "Who is Mirror Spock?", "Tolkien / Elfique"), "tolkien")
        self.assertEqual(resolve_normal_universe("qa", "What does elda mean?", "Empire Terran"), "terran_empire")
        self.assertEqual(resolve_normal_universe("translate", "Translate: the warrior walks", "Empire Terran"), "tolkien")

    def test_star_trek_question_routes_to_qa_without_tolkien_generation_bias(self):
        result = classify_request("Who is Mirror Spock?", api_key="")

        self.assertEqual(result["route"], "qa")
        self.assertEqual(result["method"], "rules")

    def test_llm_prompts_are_universe_neutral_for_ambiguous_routing(self):
        self.assertIn("multi-universe", _ROUTER_PROMPT)
        self.assertNotIn("Tolkien Elvish language app", _ROUTER_PROMPT)
        self.assertNotIn("within Tolkien's universe", _ROUTER_PROMPT)

        self.assertIn("multi-universe RAG system", _SYSTEM_PROMPT)
        self.assertIn("Mirror Spock", _SYSTEM_PROMPT)
        self.assertIn("Use \"vocabulary\" only for explicit Quenya/Sindarin/Elvish", _SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
