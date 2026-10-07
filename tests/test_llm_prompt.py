import unittest

from src.llm import build_prompt


class LLMPromptTests(unittest.TestCase):
    def test_prompt_uses_selected_universe(self):
        prompt = build_prompt(
            "Qui est Mirror Spock?",
            [{"source": "key_figures.txt", "text": "Mirror Spock later reformed the Empire."}],
            [],
            universe_name="Terran Empire — Star Trek Mirror Universe",
        )

        self.assertIn("Terran Empire", prompt)
        self.assertIn("Star Trek Mirror Universe", prompt)
        self.assertIn("Never apologize because the corpus is not Tolkien", prompt)
        self.assertNotIn("You are an expert on Elvish languages", prompt)
        self.assertNotIn("general knowledge of Tolkien", prompt)

    def test_prompt_numbers_passages_and_requires_inline_citations(self):
        prompt = build_prompt(
            "Who is the Intendant?",
            [
                {
                    "source_path": "data/key_figures.txt",
                    "text": "The Intendant is mirror Kira Nerys.",
                    "episode_refs": [
                        {
                            "series": "Star Trek: Deep Space Nine",
                            "title": "Crossover",
                            "season": 2,
                            "episode": 23,
                        }
                    ],
                },
                {
                    "source_path": "data/political_structure.txt",
                    "text": "An Intendant governs a territory.",
                    "episode_refs": [],
                },
            ],
            [],
            universe_name="Terran Empire",
        )

        self.assertIn("[1] Source: key_figures.txt", prompt)
        self.assertIn("Star Trek: Deep Space Nine — Crossover — S02E23", prompt)
        self.assertIn("[2] Source: political_structure.txt", prompt)
        self.assertIn("Référence d'épisode non renseignée", prompt)
        self.assertIn("citation [n] after every factual claim", prompt)
        self.assertIn("Never invent an episode reference", prompt)


if __name__ == "__main__":
    unittest.main()
