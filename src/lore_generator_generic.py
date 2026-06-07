"""Generic lore generation for any universe — no KG, no Tolkien-specific logic.

Pipeline:
1. search_faiss() — retrieve relevant chunks from universe index
2. Claude API    — generate story grounded in those chunks
"""

from anthropic import Anthropic
from sentence_transformers import SentenceTransformer
import faiss

from src.retrieval import search_faiss


def generate_lore_for_universe(
    user_request: str,
    universe_name: str,
    api_key: str,
    model: SentenceTransformer,
    index: faiss.Index,
    metadata: list[dict],
    k: int = 5,
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

    Returns:
        {
            "success"    : bool,
            "story"      : str,
            "chunks_used": int,
            "error"      : str (only if failed),
        }
    """
    try:
        chunks = search_faiss(user_request, model, index, metadata, k=k)

        if not chunks:
            return {
                "success": False,
                "error": "No relevant context found in index. Try rephrasing your request.",
                "story": None,
                "chunks_used": 0,
            }

        context_text = "\n\n---\n\n".join(c["text"] for c in chunks[:4])

        prompt = f"""You are a creative writer and lore expert for the {universe_name} universe.

Using the following canon excerpts as your foundation, generate an original, coherent piece of lore
that fits seamlessly within the universe. Stay true to the tone, terminology, and established facts.

CANON CONTEXT:
{context_text}

USER REQUEST:
{user_request}

Write the lore now. Be creative but respect the canon established in the context above."""

        client = Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        return {
            "success": True,
            "story": message.content[0].text,
            "chunks_used": len(chunks),
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "story": None,
            "chunks_used": 0,
        }
