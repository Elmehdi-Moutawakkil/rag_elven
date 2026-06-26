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


if __name__ == "__main__":
    unittest.main()
