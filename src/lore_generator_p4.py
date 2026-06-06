"""Lore generation pipeline — Phase 4 (Knowledge Graph validation).

Identical to Phase 3 (lore_generator.py) except that validate_coherence()
is replaced by validate_with_kg() — a DETERMINISTIC check against the
SQLite Knowledge Graph instead of a second Claude API call.

Pipeline:
1. extract_context()      → same as Phase 3
2. retrieve_context()     → same as Phase 3 (FAISS)
3. build_constraints()    → same as Phase 3
4. generate_story()       → same as Phase 3 (Claude)
5. validate_with_kg()     → NEW: deterministic KG query (no LLM call)
6. generate_lore_p4()     → main orchestrator
"""

import json
from typing import Optional
from pathlib import Path

from anthropic import Anthropic
from sentence_transformers import SentenceTransformer
import faiss

from src.prompt_templates import (
    format_generation_prompt,
)
from src.retrieval import load_faiss, load_model, search_faiss
from src.knowledge_graph import KnowledgeGraph, KG_DB_PATH

# ==============================================================================
# RE-USE Phase 3 helpers unchanged
# ==============================================================================

from src.lore_generator import (
    extract_context,
    retrieve_context,
    build_constraints_from_chunks,
    generate_story,
)


# ==============================================================================
# PHASE 4 — DETERMINISTIC VALIDATION VIA KG
# ==============================================================================

def validate_with_kg(story: str) -> dict:
    """Validate the generated story against the Knowledge Graph.

    No LLM is called here.  The check is fully deterministic:
      1. Find canon entities mentioned in the story.
      2. Detect role assertions and compare against KG.
      3. Check against hard-coded canon fact patterns.

    Returns:
        {
            "score": int (0–100),
            "violations": [{"text", "canon", "severity"}],
            "entities_found": [str],
            "is_valid": bool,
            "method": "knowledge_graph",
        }

    Raises a clear error if the KG database has not been built yet.
    """
    if not KG_DB_PATH.exists():
        return {
            "score": 0,
            "violations": [],
            "entities_found": [],
            "is_valid": False,
            "method": "knowledge_graph",
            "error": (
                "Knowledge Graph database not found. "
                "Run `python scripts/build_kg.py` to build it."
            ),
        }

    with KnowledgeGraph() as kg:
        return kg.validate_story(story)


# ==============================================================================
# MAIN ORCHESTRATOR
# ==============================================================================

def generate_lore_p4(
    user_request: str,
    api_key: str,
    model: Optional[SentenceTransformer] = None,
    index: Optional[faiss.Index] = None,
    metadata: Optional[list[dict]] = None,
) -> dict:
    """Main function: orchestrate the Phase 4 lore generation pipeline.

    Identical to generate_lore() (Phase 3) except validation is via KG
    instead of a second Claude call.

    Returns:
        {
            "success": bool,
            "story": str,
            "context": dict,
            "validation": dict,
            "chunks_used": int,
            "error": str (if failed),
        }
    """
    try:
        # Load resources if not provided
        if model is None:
            model = load_model()
        if index is None or metadata is None:
            index, metadata = load_faiss()

        # Step 1: Extract context (same as Phase 3)
        context = extract_context(user_request)

        # Step 2: Retrieve relevant FAISS chunks (same as Phase 3)
        chunks = retrieve_context(
            location=context["location"],
            period=context["period"],
            model=model,
            index=index,
            metadata=metadata,
            k=5,
        )

        if not chunks:
            return {
                "success": False,
                "error": "No relevant context found in FAISS. Try a different location or period.",
                "story": None,
                "validation": None,
            }

        # Step 3: Generate story (Claude — same as Phase 3)
        story = generate_story(context, chunks, api_key)

        # Step 4: Validate via KG (DETERMINISTIC — no second Claude call)
        validation = validate_with_kg(story)

        return {
            "success": True,
            "story": story,
            "context": context,
            "validation": validation,
            "chunks_used": len(chunks),
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Phase 4 generation failed: {str(e)}",
            "story": None,
            "validation": None,
        }
