"""Prompt templates pour la génération de lore compatible avec un univers cible.

Les templates incluent:
- Context: chunks FAISS pertinents du cours
- Constraints: faits connus qui doivent être respectés
- Few-shot examples: exemples de lore bien-formé
- Instructions: ce que le LLM doit faire/éviter
"""

# ==============================================================================
# TEMPLATE PRINCIPAL : Génération de lore avec contraintes
# ==============================================================================

LORE_GENERATION_TEMPLATE = """You are a lore expert and creative writer for the {universe_name} universe. Your task is to generate a NEW story that is:
1. Internally consistent (tribe has coherent culture, geography matches, timeline works)
2. Compatible with established canon from the selected corpus (respects known facts, doesn't contradict)
3. Creative but plausible (invents believable details within the selected universe)

CONTEXT FROM COURSE (established facts):
{context}

CONSTRAINTS (you MUST respect these):
{constraints}

GENERATION REQUEST:
{request}

EXAMPLE OF GOOD LORE GENERATION:
- "A local faction emerges in a known region, follows established politics, and adds small cultural details supported by the corpus."
- "A new event is framed as a minor episode around known entities without changing major canon outcomes."

EXAMPLE OF BAD LORE GENERATION:
- "The tribe forged the Silmarils" (contradicts canon)
- "They ruled all of Middle-earth" (implausible)
- "They existed in 4th Age but disappeared in 1st Age" (timeline breaks)

YOUR TASK:
1. Generate the story (2-3 paragraphs)
2. List 3 key facts that make it canon-compatible
3. Explain any invented cultural/linguistic details

Write in a scholarly tone, as if documenting historical lore."""

# ==============================================================================
# TEMPLATE DE VALIDATION : Vérifier la cohérence post-génération
# ==============================================================================

COHERENCE_VALIDATION_TEMPLATE = """You are a canon expert for the {universe_name} universe. Review this generated lore and assess compatibility.

GENERATED STORY:
{story}

KNOWN CANON FACTS (from course):
{canon_facts}

VALIDATION CRITERIA:
1. Does it contradict any known facts? (Thingol is king of Doriath, Silmarils exist, etc.)
2. Is the geography plausible? (locations exist, distances make sense)
3. Is the timeline consistent? (doesn't skip ages, respects known chronology)
4. Are cultural details believable? (elvish societies have consistent patterns)

PROVIDE:
- Compatibility score (0-100)
- List of potential contradictions (if any)
- List of strengths in the generation
- Suggestions for improvement (if needed)

Be critical but fair. Minor liberties with details are OK (inventing a sub-tribe of a known tribe is fine). Major contradictions are NOT OK."""

# ==============================================================================
# TEMPLATE D'EXTRACTION : Extraire les faits de la génération
# ==============================================================================

FACT_EXTRACTION_TEMPLATE = """Extract key facts from this generated lore for validation.

GENERATED TEXT:
{story}

EXTRACT AND STRUCTURE:
Return a list of claims in this format:
- CLAIM: "The Thorgrim tribe inhabited Mirkwood"
- TYPE: geography|leadership|timeline|culture|language
- CONFIDENCE: high|medium|low

Do NOT filter or judge — just extract all factual claims."""

# ==============================================================================
# HELPERS
# ==============================================================================

def format_generation_prompt(
    context: str,
    constraints: str,
    request: str,
    universe_name: str = "Tolkien's Middle-earth and Elvish languages",
) -> str:
    """Format the main generation prompt with context, constraints, and user request."""
    return LORE_GENERATION_TEMPLATE.format(
        universe_name=universe_name,
        context=context,
        constraints=constraints,
        request=request,
    )


def format_validation_prompt(
    story: str,
    canon_facts: str,
    universe_name: str = "Tolkien's Middle-earth and Elvish languages",
) -> str:
    """Format the validation prompt."""
    return COHERENCE_VALIDATION_TEMPLATE.format(
        universe_name=universe_name,
        story=story,
        canon_facts=canon_facts,
    )


def format_extraction_prompt(story: str) -> str:
    """Format the fact extraction prompt."""
    return FACT_EXTRACTION_TEMPLATE.format(story=story)
