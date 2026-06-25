"""Inspector configuration — add a universe or feature here to make it testable."""

from pathlib import Path
from src.settings import ANTHROPIC_JUDGE_MODEL, GROQ_MODEL as DEFAULT_GROQ_MODEL

PROJECT_ROOT = Path(__file__).parent.parent
INSPECTOR_DB = PROJECT_ROOT / "inspector" / "inspector.db"

# ---------------------------------------------------------------------------
# Feature registry — one entry per testable capability
# ---------------------------------------------------------------------------
# To add a new universe: add entries below following the same pattern.
# To disable a feature: set "enabled": False.

FEATURES = [
    {
        "id": "qa_elvish",
        "universe": "Elfique (Tolkien)",
        "feature": "Q&A",
        "description": "Factual questions about Tolkien lore and Elvish languages",
        "enabled": True,
    },
    {
        "id": "translate_quenya",
        "universe": "Elfique (Tolkien)",
        "feature": "Traduction Quenya",
        "description": "English → Quenya sentence translation pipeline",
        "enabled": True,
    },
    {
        "id": "lore_tolkien",
        "universe": "Elfique (Tolkien)",
        "feature": "Génération Lore",
        "description": "Creative Tolkien lore generation via Claude + FAISS",
        "enabled": True,
    },
    {
        "id": "qa_terran",
        "universe": "Empire Terran (Star Trek)",
        "feature": "Q&A",
        "description": "Factual questions about the Mirror Universe",
        "enabled": True,
    },
    {
        "id": "lore_terran",
        "universe": "Empire Terran (Star Trek)",
        "feature": "Génération Lore",
        "description": "Creative Mirror Universe lore generation via Claude + FAISS",
        "enabled": True,
    },
    # --- Future universes ---
    # {
    #     "id": "qa_dune",
    #     "universe": "Dune",
    #     "feature": "Q&A",
    #     "description": "Factual questions about the Dune universe",
    #     "enabled": False,
    # },
]

# Number of tests per feature per run (set to 6 → 30 tests/run with 5 features)
TESTS_PER_FEATURE = 6

# Groq model under test
GROQ_MODEL = DEFAULT_GROQ_MODEL

# Anthropic model used by the inspector as judge
JUDGE_MODEL = ANTHROPIC_JUDGE_MODEL

# Minimum acceptable correctness rate (below this → flagged in report)
CORRECTNESS_THRESHOLD = 0.70

# Minimum acceptable hallucination rate (above this → flagged in report)
HALLUCINATION_THRESHOLD = 0.25
