"""Lore generation pipeline.

Pipeline:
1. extract_context()      → Parse user request (location, period, species, etc.)
2. retrieve_context()     → FAISS query for relevant chunks
3. build_constraints()    → Extract known facts that must be respected
4. generate_story()       → Call Claude API with context + constraints
5. validate_coherence()   → Basic validation (re-query FAISS for contradictions)
6. generate_lore()        → Main orchestrating function
"""

import json
from typing import Optional
from pathlib import Path

from anthropic import Anthropic
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

from src.prompt_templates import (
    format_generation_prompt,
    format_validation_prompt,
    format_extraction_prompt,
)
from src.retrieval import load_faiss, load_model, search_faiss


# ==============================================================================
# CONTEXT EXTRACTION
# ==============================================================================

def extract_context(user_request: str) -> dict:
    """Parse user request to extract key generation parameters.

    Examples:
        "Invente une tribu d'elfes en Beleriand"
        → {"location": "Beleriand", "species": "elves", "period": None}

        "Create a Sindarin tribe in Mirkwood during 2nd Age"
        → {"location": "Mirkwood", "language": "Sindarin", "period": "Second Age"}

    For MVP, use simple keyword extraction (can be enhanced later with LLM).
    """
    request_lower = user_request.lower()

    # Extract period (age)
    period = None
    if "1st age" in request_lower or "first age" in request_lower:
        period = "First Age"
    elif "2nd age" in request_lower or "second age" in request_lower:
        period = "Second Age"
    elif "3rd age" in request_lower or "third age" in request_lower:
        period = "Third Age"
    elif "4th age" in request_lower or "fourth age" in request_lower:
        period = "Fourth Age"

    # Extract location (simple keyword matching)
    locations = [
        "Beleriand", "Mirkwood", "Rivendell", "Lothlórien", "Gondor",
        "Rohan", "Doriath", "Nargothrond", "Lindon", "Valinor", "Endor"
    ]
    location = None
    for loc in locations:
        if loc.lower() in request_lower:
            location = loc
            break

    # Extract species/type
    species = "elves"  # default
    if "dwarf" in request_lower:
        species = "dwarves"
    elif "man" in request_lower or "human" in request_lower:
        species = "humans"
    elif "hobbit" in request_lower:
        species = "hobbits"

    # Extract language preference
    language = None
    if "quenya" in request_lower:
        language = "Quenya"
    elif "sindarin" in request_lower:
        language = "Sindarin"

    return {
        "location": location or "Middle-earth",
        "period": period,
        "species": species,
        "language": language,
        "raw_request": user_request,
    }


# ==============================================================================
# CONTEXT RETRIEVAL FROM FAISS
# ==============================================================================

def retrieve_context(
    location: str,
    period: Optional[str],
    model: SentenceTransformer,
    index: faiss.Index,
    metadata: list[dict],
    k: int = 5,
) -> list[dict]:
    """Retrieve relevant FAISS chunks for the given location/period.

    Build a query combining location + period + "tribe culture lore"
    to find the most relevant course material.
    """
    # Build search query
    query_parts = [location, "tribe", "culture", "history"]
    if period:
        query_parts.append(period)

    search_query = " ".join(query_parts)

    # Encode and search
    query_vector = model.encode([search_query], normalize_embeddings=True).astype("float32")
    distances, indices = index.search(query_vector, k=k)

    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if idx == -1:
            continue
        entry = metadata[idx]
        results.append({
            "text": entry.get("text", ""),
            "source": entry.get("source", ""),
            "page": entry.get("page"),
            "score": float(dist),
        })

    return results


def build_constraints_from_chunks(chunks: list[dict]) -> str:
    """Extract known facts from FAISS chunks to use as constraints.

    Simple approach: concatenate key facts from the top chunks.
    (In Phase 2, this becomes a Knowledge Graph query.)
    """
    if not chunks:
        return "No constraints found. Use standard Tolkien lore."

    constraints = []
    for chunk in chunks[:3]:  # top 3 chunks
        text = chunk.get("text", "")
        # Extract first 2 sentences as a constraint
        sentences = text.split(".")[:2]
        if sentences:
            constraint = ".".join(sentences) + "."
            constraints.append(constraint)

    return "\n".join(constraints) if constraints else "Use established Tolkien canon."


# ==============================================================================
# GENERATION
# ==============================================================================

def generate_story(
    context: dict,
    chunks: list[dict],
    api_key: str,
) -> str:
    """Call Claude API to generate the story.

    Args:
        context: extracted context from user request
        chunks: FAISS-retrieved relevant chunks
        api_key: Anthropic API key

    Returns:
        Generated story text
    """
    # Format constraints from chunks
    chunks_text = "\n\n".join([c["text"] for c in chunks[:3]])
    constraints = build_constraints_from_chunks(chunks)

    # Build the request for Claude
    request = f"""Generate a story about {context['species']}
in {context['location']}
{f"during the {context['period']}" if context['period'] else ""}
{f"speaking {context['language']}" if context['language'] else ""}.

Be creative but respect established Tolkien canon."""

    # Format full prompt
    prompt = format_generation_prompt(
        context=chunks_text,
        constraints=constraints,
        request=request,
    )

    # Call Claude
    client = Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        messages=[
            {"role": "user", "content": prompt}
        ],
    )

    return message.content[0].text


# ==============================================================================
# VALIDATION
# ==============================================================================

def validate_coherence(
    story: str,
    chunks: list[dict],
    api_key: str,
) -> dict:
    """Validate the generated story for canon compatibility.

    Simple approach: ask Claude to check for contradictions.
    (In Phase 2, this becomes a Knowledge Graph validation.)

    Returns:
        {
            "score": 0-100,
            "contradictions": [...],
            "strengths": [...],
            "is_valid": bool,
        }
    """
    # Format canon facts from chunks
    canon_facts = "\n\n".join([c["text"] for c in chunks[:3]])

    # Ask Claude to validate
    validation_prompt = format_validation_prompt(story=story, canon_facts=canon_facts)

    client = Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=512,
        messages=[
            {"role": "user", "content": validation_prompt}
        ],
    )

    validation_text = message.content[0].text

    # Parse validation response (simple heuristic for MVP)
    # In Phase 2, parse more carefully or use structured output
    score = 75  # default
    is_valid = True

    if "contradict" in validation_text.lower():
        score = 50
        is_valid = False
    elif "excellent" in validation_text.lower() or "perfect" in validation_text.lower():
        score = 95
    elif "good" in validation_text.lower() or "strong" in validation_text.lower():
        score = 85

    return {
        "score": score,
        "validation_text": validation_text,
        "is_valid": is_valid,
        "contradictions": [],  # would parse from validation_text in Phase 2
    }


# ==============================================================================
# MAIN ORCHESTRATOR
# ==============================================================================

def generate_lore(
    user_request: str,
    api_key: str,
    model: Optional[SentenceTransformer] = None,
    index: Optional[faiss.Index] = None,
    metadata: Optional[list[dict]] = None,
) -> dict:
    """Main function: orchestrate the full lore generation pipeline.

    Args:
        user_request: user's lore generation request
        api_key: Anthropic API key
        model: embedding model (loaded if not provided)
        index: FAISS index (loaded if not provided)
        metadata: FAISS metadata (loaded if not provided)

    Returns:
        {
            "success": bool,
            "story": str,
            "context": dict,
            "validation": dict,
            "error": str (if failed),
        }
    """
    try:
        # Load resources if not provided
        if model is None:
            model = load_model()
        if index is None or metadata is None:
            index, metadata = load_faiss()

        # Step 1: Extract context
        context = extract_context(user_request)

        # Step 2: Retrieve relevant chunks from FAISS
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

        # Step 3: Generate story
        story = generate_story(context, chunks, api_key)

        # Step 4: Validate coherence
        validation = validate_coherence(story, chunks, api_key)

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
            "error": f"Generation failed: {str(e)}",
            "story": None,
            "validation": None,
        }
