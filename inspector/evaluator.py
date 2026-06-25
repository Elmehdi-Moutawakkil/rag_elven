"""
Evaluator — uses Claude as judge to score app responses.

For each test, Claude receives:
  - The question asked
  - The app's response
  - Key canonical facts that should be present (ground truth hints)
  - Red-flag phrases that would indicate hallucinations

Claude returns a structured verdict:
  CORRECT       — response is factually accurate and relevant
  PARTIAL       — partially correct, missing key facts
  HALLUCINATION — response contains demonstrably false information
  IRRELEVANT    — response does not address the question
  ERROR         — app returned an error or empty response

Web search is used when Claude needs to verify a claim it's unsure about.
"""

import json
import os
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*_args, **_kwargs):
        return False

load_dotenv(PROJECT_ROOT / ".env")

from src.settings import ANTHROPIC_API_KEY_ENV, ANTHROPIC_JUDGE_MODEL, env_value, missing_key_message


# ---------------------------------------------------------------------------
# Optional web search via DuckDuckGo (no API key required)
# ---------------------------------------------------------------------------

def web_search(query: str, max_results: int = 3) -> str:
    """Return a summary of top search results for query."""
    try:
        try:
            from ddgs import DDGS
        except ModuleNotFoundError:
            from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(f"- {r['title']}: {r['body'][:200]}")
        return "\n".join(results) if results else "No results found."
    except Exception as e:
        return f"[web search unavailable: {e}]"


# ---------------------------------------------------------------------------
# Claude judge
# ---------------------------------------------------------------------------

def evaluate_response(
    feature_id: str,
    question: str,
    app_response: str | None,
    facts: list[str],
    anti: list[str],
) -> dict:
    """
    Ask Claude to evaluate the app's response.

    Returns:
        {
            "verdict":     str,   # CORRECT | PARTIAL | HALLUCINATION | IRRELEVANT | ERROR
            "score":       float, # 0.0 to 1.0
            "judge_notes": str,
        }
    """
    import anthropic

    if not app_response or app_response.strip() == "":
        return {
            "verdict": "ERROR",
            "score": 0.0,
            "judge_notes": "App returned an empty response.",
        }

    api_key = env_value(ANTHROPIC_API_KEY_ENV)
    if not api_key:
        return {
            "verdict": "ERROR",
            "score": 0.0,
            "judge_notes": missing_key_message(ANTHROPIC_API_KEY_ENV, "Inspector judge"),
        }

    # For Q&A features, optionally search for extra context
    search_context = ""
    if feature_id in ("qa_elvish", "qa_terran"):
        search_query = f"{question} {' '.join(facts[:2])}"
        search_context = web_search(search_query)

    facts_str = "\n".join(f"  - {f}" for f in facts)
    anti_str  = "\n".join(f"  - {a}" for a in anti)

    prompt = f"""You are an expert fact-checker evaluating an AI app's response.

## Question asked to the app
{question}

## App's response
{app_response}

## Expected canonical facts (the response should mention at least some of these)
{facts_str}

## Hallucination red flags (presence of these suggests a hallucination)
{anti_str}

{f"## Additional web search context{chr(10)}{search_context}" if search_context else ""}

## Your task
Evaluate the app's response strictly on:
1. **Factual correctness** — does it contain accurate information?
2. **Completeness** — does it address the question?
3. **Hallucination** — does it state false facts, or things in the red-flag list?

Respond ONLY with valid JSON, no markdown, no explanation outside JSON:
{{
  "verdict": "<CORRECT|PARTIAL|HALLUCINATION|IRRELEVANT|ERROR>",
  "score": <float between 0.0 and 1.0>,
  "judge_notes": "<one concise sentence explaining your verdict>"
}}

Scoring guide:
  CORRECT      → score 0.85–1.0
  PARTIAL      → score 0.4–0.84
  HALLUCINATION → score 0.0–0.3
  IRRELEVANT   → score 0.1–0.3
  ERROR        → score 0.0
"""

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=ANTHROPIC_JUDGE_MODEL,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()

    # Strip possible markdown fences
    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)

    try:
        result = json.loads(raw)
        return {
            "verdict":     result.get("verdict", "ERROR"),
            "score":       float(result.get("score", 0.0)),
            "judge_notes": result.get("judge_notes", ""),
        }
    except json.JSONDecodeError:
        return {
            "verdict": "ERROR",
            "score": 0.0,
            "judge_notes": f"Judge returned unparseable response: {raw[:200]}",
        }
