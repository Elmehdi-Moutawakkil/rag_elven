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

from sentence_transformers import SentenceTransformer
import faiss

from src.knowledge_graph import KnowledgeGraph
from src.retrieval_adapter import RetrievalStatus, retrieve_evidence_result
from src.llm_provider import generate_lore_text, safe_provider_error
from src.settings import ANTHROPIC_API_KEY_ENV, GROQ_API_KEY_ENV, missing_key_message
from src.universe_registry import SemanticIndexHandle, get_universe_registry

PROJECT_ROOT = Path(__file__).parent.parent

def _load_kg_constraints(universe_id: str | None) -> tuple[str, list[dict]]:
    """Return (constraints_text, canon_facts) from the KG if it exists."""
    config = get_universe_registry().get(universe_id)
    kg_path = config.knowledge_graph_path if config else None
    if kg_path is None or not kg_path.exists():
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
    api_key: str | None,
    model: SentenceTransformer | None = None,
    semantic_handle: SemanticIndexHandle | None = None,
    k: int = 5,
    universe_id: str | None = None,
    provider: str = "anthropic",
) -> dict:
    """Generate lore for any universe using FAISS context + Claude.

    Args:
        user_request  : the user's lore generation request
        universe_name : display name used in the generation prompt
        api_key       : API key for the selected lore provider
        model         : sentence-transformers model (for FAISS query encoding)
        semantic_handle: manifest-bound FAISS resources for the selected universe
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
        retrieval = retrieve_evidence_result(
            user_request,
            universe_id=universe_id,
            model=model,
            semantic_handle=semantic_handle,
        )
        provider_name = provider.strip().lower()
        if provider_name not in {"anthropic", "groq"}:
            return {
                "success": False,
                "error": "PROVIDER_UNSUPPORTED: fournisseur de lore non pris en charge.",
                "story": None,
                "chunks_used": 0,
                "kg_violations": [],
                "retrieval": retrieval.to_dict(),
            }
        if retrieval.status != RetrievalStatus.SUCCESS:
            return {
                "success": False,
                "error": f"{retrieval.status}: {retrieval.error or 'No evidence available'}",
                "story": None,
                "chunks_used": 0,
                "kg_violations": [],
                "retrieval": retrieval.to_dict(),
            }
        if not api_key:
            return {
                "success": False,
                "error": missing_key_message(
                    ANTHROPIC_API_KEY_ENV if provider_name == "anthropic" else GROQ_API_KEY_ENV,
                    "generation de lore",
                ),
                "story": None,
                "chunks_used": 0,
                "kg_violations": [],
            }

        chunks = retrieval.hits[:k]

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

        try:
            story = generate_lore_text(prompt, provider_name, api_key)
        except Exception as exc:
            raise safe_provider_error(provider_name, exc) from None
        regex_violations = _check_violations(story, canon_facts) if canon_facts else []
        kg_validation = _validate_with_universe_kg(story, universe_id)
        kg_violations = kg_validation.get("violations", []) if kg_validation else []

        return {
            "success": True,
            "story": story,
            "chunks_used": len(chunks),
            "retrieval": retrieval.to_dict(),
            "kg_validation": kg_validation,
            "kg_violations": kg_violations or regex_violations,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(safe_provider_error(provider, e)),
            "story": None,
            "chunks_used": 0,
            "kg_violations": [],
        }


def _validate_with_universe_kg(story: str, universe_id: str | None) -> dict | None:
    """Validate story against vector_db/<universe_id>/knowledge_graph.sqlite if present."""
    if not universe_id:
        return None

    config = get_universe_registry().get(universe_id)
    db_path = config.knowledge_graph_path if config else None
    if db_path is None or not db_path.exists():
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
