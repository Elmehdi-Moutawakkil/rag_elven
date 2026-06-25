"""Generic lore generation for any universe — with optional KG validation.

Pipeline:
1. search_faiss()     — retrieve relevant chunks from universe index
2. KG canon check     — load hard rules if a KG exists for this universe
3. Claude API         — generate story grounded in chunks + KG constraints
4. KG violation check — flag any canon violations in the output
"""

import re
import sqlite3
from pathlib import Path

from anthropic import Anthropic
from sentence_transformers import SentenceTransformer
import faiss

from src.knowledge_graph import KnowledgeGraph
from src.retrieval import search_faiss
from src.settings import ANTHROPIC_API_KEY_ENV, ANTHROPIC_LORE_MODEL, missing_key_message

PROJECT_ROOT = Path(__file__).parent.parent

# Map universe_id → KG path (add new universes here)
KG_PATHS = {
    "terran_empire": PROJECT_ROOT / "vector_db" / "terran_empire" / "knowledge_graph.sqlite",
}


def _load_kg_constraints(universe_id: str) -> tuple[str, list[dict]]:
    """Return (constraints_text, canon_facts) from the KG if it exists."""
    kg_path = KG_PATHS.get(universe_id)
    if not kg_path or not kg_path.exists():
        return "", []

    conn = sqlite3.connect(kg_path)
    conn.row_factory = sqlite3.Row

    # Key entities for the prompt
    entities = conn.execute(
        "SELECT name, entity_type, description FROM entities ORDER BY entity_type, name"
    ).fetchall()

    # Hard canon facts only
    facts = conn.execute(
        "SELECT description, violation_pattern, severity FROM canon_facts"
    ).fetchall()
    conn.close()

    entity_lines = [f"- [{r['entity_type'].upper()}] {r['name']}: {r['description']}" for r in entities]
    constraints = "KNOWN ENTITIES (respect these):\n" + "\n".join(entity_lines)
    return constraints, [dict(f) for f in facts]


def _check_violations(story: str, canon_facts: list[dict]) -> list[str]:
    """Return list of canon violation descriptions found in the story."""
    violations = []
    for fact in canon_facts:
        pattern = fact.get("violation_pattern")
        if pattern:
            try:
                if re.search(pattern, story):
                    violations.append(f"[{fact['severity']}] {fact['description']}")
            except re.error:
                pass
    return violations


def generate_lore_for_universe(
    user_request: str,
    universe_name: str,
    api_key: str,
    model: SentenceTransformer,
    index: faiss.Index,
    metadata: list[dict],
    k: int = 5,
    universe_id: str | None = None,
) -> dict:
    """Generate lore for any universe using FAISS context + Claude.

    Args:
        user_request  : the user's lore generation request
        universe_name : display name used in the generation prompt
        api_key       : Anthropic API key
        model         : sentence-transformers model (for FAISS query encoding)
        index         : FAISS index for the target universe
        metadata      : FAISS metadata parallel to the index
        k             : number of context chunks to retrieve
        universe_id   : optional vector_db/<universe_id>/knowledge_graph.sqlite namespace

    Returns:
        {
            "success"    : bool,
            "story"      : str,
            "chunks_used": int,
            "error"      : str (only if failed),
        }
    """
    try:
        if not api_key:
            return {
                "success": False,
                "error": missing_key_message(ANTHROPIC_API_KEY_ENV, "generation de lore"),
                "story": None,
                "chunks_used": 0,
                "kg_violations": [],
            }

        chunks = search_faiss(user_request, model, index, metadata, k=k)

        if not chunks:
            return {
                "success": False,
                "error": "No relevant context found in index. Try rephrasing your request.",
                "story": None,
                "chunks_used": 0,
            }

        context_text = "\n\n---\n\n".join(c["text"] for c in chunks[:4])

        # Load KG constraints if available for this universe
        kg_constraints, canon_facts = _load_kg_constraints(universe_id)

        kg_section = f"\n\n{kg_constraints}" if kg_constraints else ""

        prompt = f"""You are a creative writer and lore expert for the {universe_name} universe.

Using the following canon excerpts as your foundation, generate an original, coherent piece of lore
that fits seamlessly within the universe. Stay true to the tone, terminology, and established facts.

CANON CONTEXT:
{context_text}{kg_section}

USER REQUEST:
{user_request}

Write the lore now. Be creative but strictly respect the canon entities and facts above."""

        client = Anthropic(api_key=api_key)
        message = client.messages.create(
            model=ANTHROPIC_LORE_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        story = message.content[0].text
        regex_violations = _check_violations(story, canon_facts) if canon_facts else []
        kg_validation = _validate_with_universe_kg(story, universe_id)
        kg_violations = kg_validation.get("violations", []) if kg_validation else []

        return {
            "success": True,
            "story": story,
            "chunks_used": len(chunks),
            "kg_validation": kg_validation,
            "kg_violations": kg_violations or regex_violations,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "story": None,
            "chunks_used": 0,
            "kg_violations": [],
        }


def _validate_with_universe_kg(story: str, universe_id: str | None) -> dict | None:
    """Validate story against vector_db/<universe_id>/knowledge_graph.sqlite if present."""
    if not universe_id:
        return None

    db_path = Path(__file__).parent.parent / "vector_db" / universe_id / "knowledge_graph.sqlite"
    if not db_path.exists():
        return {
            "method": "knowledge_graph",
            "is_valid": None,
            "score": None,
            "violations": [],
            "warning": f"Knowledge graph not found: {db_path}",
        }

    try:
        with KnowledgeGraph(db_path=db_path) as kg:
            return kg.validate_story(story)
    except Exception as exc:
        return {
            "method": "knowledge_graph",
            "is_valid": None,
            "score": None,
            "violations": [],
            "warning": str(exc),
        }
