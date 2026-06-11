"""
Direct calls to app Python modules — bypasses Streamlit entirely.

All functions return {"success": bool, "response": str, "error": str | None}.
Must be called with PROJECT_ROOT as cwd (handled by run_tests.py).
"""

import os
import sys
import time
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Change working directory so relative paths (vector_db/, data/) work
os.chdir(PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")


# ---------------------------------------------------------------------------
# Lazy resource cache — loaded once, reused across tests
# ---------------------------------------------------------------------------

_cache: dict = {}


def _get_embedding_model():
    if "model" not in _cache:
        from src.retrieval import load_model
        print("[bridge] Loading sentence-transformer model...")
        _cache["model"] = load_model()
    return _cache["model"]


def _get_elvish_index():
    if "elvish_index" not in _cache:
        from src.retrieval import load_faiss
        print("[bridge] Loading Elvish FAISS index...")
        idx, meta = load_faiss("vector_db/faiss.index", "vector_db/metadata.json")
        _cache["elvish_index"] = (idx, meta)
    return _cache["elvish_index"]


def _get_terran_index():
    if "terran_index" not in _cache:
        from src.retrieval import load_faiss
        print("[bridge] Loading Terran Empire FAISS index...")
        idx, meta = load_faiss(
            "vector_db/terran_empire/faiss.index",
            "vector_db/terran_empire/metadata.json",
        )
        _cache["terran_index"] = (idx, meta)
    return _cache["terran_index"]


# ---------------------------------------------------------------------------
# Feature bridges
# ---------------------------------------------------------------------------

def call_qa_elvish(question: str) -> dict:
    """Q&A Tolkien — FAISS + SQLite + Groq LLM."""
    t0 = time.time()
    try:
        from src.retrieval import retrieve
        from src.llm import answer

        model = _get_embedding_model()
        index, metadata = _get_elvish_index()

        results = retrieve(question, model, index, metadata, k=3)
        response = answer(
            question,
            results["faiss"],
            results.get("dictionary", []),
            api_key=os.getenv("GROQ_API_KEY"),
        )
        return {
            "success": True,
            "response": response,
            "duration_ms": int((time.time() - t0) * 1000),
            "error": None,
        }
    except Exception as e:
        return {"success": False, "response": None, "duration_ms": int((time.time() - t0) * 1000), "error": str(e)}


def call_translate_quenya(sentence: str) -> dict:
    """English → Quenya translation pipeline."""
    t0 = time.time()
    try:
        from src.translator import translate

        # translate() reads GROQ_API_KEY from env directly (no api_key param)
        result = translate(sentence)
        response = (
            f"Quenya: {result.quenya_sentence}\n"
            f"Confidence: {result.confidence_floor.name}\n"
            f"Explanation: {result.explanation}"
        )
        return {
            "success": True,
            "response": response,
            "duration_ms": int((time.time() - t0) * 1000),
            "error": None,
        }
    except Exception as e:
        return {"success": False, "response": None, "duration_ms": int((time.time() - t0) * 1000), "error": str(e)}


def call_lore_tolkien(request: str) -> dict:
    """Tolkien lore generation — FAISS + Claude."""
    t0 = time.time()
    try:
        from src.lore_generator import generate_lore

        model = _get_embedding_model()
        index, metadata = _get_elvish_index()

        result = generate_lore(
            user_request=request,
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            model=model,
            index=index,
            metadata=metadata,
        )
        if result.get("success"):
            return {
                "success": True,
                "response": result["story"],
                "duration_ms": int((time.time() - t0) * 1000),
                "error": None,
            }
        else:
            return {
                "success": False,
                "response": None,
                "duration_ms": int((time.time() - t0) * 1000),
                "error": result.get("error", "Unknown error"),
            }
    except Exception as e:
        return {"success": False, "response": None, "duration_ms": int((time.time() - t0) * 1000), "error": str(e)}


def call_qa_terran(question: str) -> dict:
    """Q&A Mirror Universe — FAISS + Groq LLM."""
    t0 = time.time()
    try:
        from src.retrieval import search_faiss
        from groq import Groq

        model = _get_embedding_model()
        index, metadata = _get_terran_index()

        chunks = search_faiss(question, model, index, metadata, k=3)
        context = "\n\n".join(c["text"] for c in chunks[:3])

        prompt = f"""You are an expert on the Star Trek Mirror Universe (Terran Empire).
Answer the question using ONLY the context provided below.
If the context does not contain enough information, say so clearly.
IMPORTANT: Answer in the same language as the question.

--- CONTEXT ---
{context}
--- END CONTEXT ---

Question: {question}
Answer:"""

        client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        resp = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=512,
            temperature=0.2,
        )
        response = resp.choices[0].message.content
        return {
            "success": True,
            "response": response,
            "duration_ms": int((time.time() - t0) * 1000),
            "error": None,
        }
    except Exception as e:
        return {"success": False, "response": None, "duration_ms": int((time.time() - t0) * 1000), "error": str(e)}


def call_lore_terran(request: str) -> dict:
    """Mirror Universe lore generation — FAISS + Claude."""
    t0 = time.time()
    try:
        from src.lore_generator_generic import generate_lore_for_universe

        model = _get_embedding_model()
        index, metadata = _get_terran_index()

        result = generate_lore_for_universe(
            user_request=request,
            universe_name="Terran Empire (Star Trek Mirror Universe)",
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            model=model,
            index=index,
            metadata=metadata,
            universe_id="terran_empire",
        )
        if result.get("success"):
            return {
                "success": True,
                "response": result["story"],
                "duration_ms": int((time.time() - t0) * 1000),
                "error": None,
            }
        else:
            return {
                "success": False,
                "response": None,
                "duration_ms": int((time.time() - t0) * 1000),
                "error": result.get("error", "Unknown error"),
            }
    except Exception as e:
        return {"success": False, "response": None, "duration_ms": int((time.time() - t0) * 1000), "error": str(e)}


# ---------------------------------------------------------------------------
# Dispatch table — add new features here
# ---------------------------------------------------------------------------

BRIDGE_MAP = {
    "qa_elvish":       call_qa_elvish,
    "translate_quenya": call_translate_quenya,
    "lore_tolkien":    call_lore_tolkien,
    "qa_terran":       call_qa_terran,
    "lore_terran":     call_lore_terran,
}


def call_feature(feature_id: str, question: str) -> dict:
    fn = BRIDGE_MAP.get(feature_id)
    if fn is None:
        return {"success": False, "response": None, "duration_ms": 0, "error": f"Unknown feature_id: {feature_id}"}
    return fn(question)
