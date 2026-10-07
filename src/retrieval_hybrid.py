"""Hybrid retrieval over normalized corpus chunks."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
import math
import re
from pathlib import Path
from typing import Any

from src.indexing.chunks import read_chunks_jsonl
from src.indexing.build import default_text_index_dir


TOKEN_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]+")

# Function words add noise to small corpora and previously let generic prose
# outrank the passage that actually defined the requested entity.
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "do", "does", "for", "from",
    "how", "in", "is", "it", "of", "on", "or", "that", "the", "this", "to", "what",
    "when", "where", "which", "who", "why", "with",
    "au", "aux", "avec", "ce", "ces", "cette", "comment", "dans", "de", "des", "donc", "du",
    "elle", "en", "est", "et", "il", "la", "le", "les", "leur", "leurs", "l", "ou",
    "par", "pour", "qu", "que", "quel", "quelle", "qui", "son", "sur", "un", "une",
}
ENTITY_QUESTION_RE = re.compile(r"\b(?:who|qui|quelle?\s+personnage)\b", re.IGNORECASE)


@dataclass(frozen=True)
class RetrievalHit:
    """One ranked retrieval result with source provenance."""

    chunk_id: str
    document_id: str
    universe_id: str
    collection_id: str | None
    text: str
    start_offset: int | None
    end_offset: int | None
    source_path: str
    source_name: str
    score: float
    relevance_score: float
    lexical_score: float
    semantic_score: float
    match_terms: list[str] = field(default_factory=list)
    citation: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def tokenize(text: str) -> list[str]:
    """Return meaningful lowercase terms, excluding common EN/FR words."""
    normalized = text.replace("’", "'").replace("'", " ")
    return [token.lower() for token in TOKEN_RE.findall(normalized) if token.lower() not in STOPWORDS]


def _matches_filters(chunk: dict[str, Any], filters: dict[str, Any] | None) -> bool:
    if not filters:
        return True
    metadata = chunk.get("metadata", {})
    for key, expected in filters.items():
        actual = chunk.get(key, metadata.get(key))
        if isinstance(expected, (list, tuple, set)):
            if actual not in expected:
                return False
        elif actual != expected:
            return False
    return True


def score_chunks(query: str, chunks: list[dict[str, Any]]) -> list[RetrievalHit]:
    """Rank chunks with a deterministic lexical score."""
    query_terms = tokenize(query)
    if not query_terms:
        return []

    query_counts = Counter(query_terms)
    document_frequency: Counter[str] = Counter()
    chunk_tokens: dict[str, list[str]] = {}
    for chunk in chunks:
        tokens = tokenize(str(chunk.get("text", "")))
        chunk_tokens[str(chunk["chunk_id"])] = tokens
        document_frequency.update(set(tokens))

    total_chunks = max(1, len(chunks))
    query_lower = query.lower().strip()
    scored: list[tuple[float, dict[str, Any], list[str], str]] = []
    entity_question = bool(ENTITY_QUESTION_RE.search(query))

    for chunk in chunks:
        tokens = chunk_tokens[str(chunk["chunk_id"])]
        if not tokens:
            continue
        token_counts = Counter(tokens)
        score = 0.0
        matched_terms: list[str] = []
        for term, query_weight in query_counts.items():
            tf = token_counts.get(term, 0)
            if tf == 0:
                continue
            idf = math.log((total_chunks + 1) / (document_frequency[term] + 1)) + 1.0
            score += (1.0 + math.log(tf)) * idf * query_weight
            matched_terms.append(term)

        text = str(chunk.get("text", ""))
        phrase_bonus = 2.0 if query_lower and query_lower in text.lower() else 0.0
        raw_score = score + phrase_bonus
        metadata = dict(chunk.get("metadata", {}))
        source_name = str(chunk.get("source_name", ""))
        if entity_question and (
            metadata.get("content_kind") == "entity_profiles" or "key_figures" in source_name.lower()
        ):
            raw_score *= 1.75
        if raw_score <= 0:
            continue
        scored.append((raw_score, chunk, sorted(matched_terms), text))

    scored.sort(key=lambda item: (-item[0], str(item[1].get("source_path", "")), str(item[1].get("chunk_id", ""))))
    max_score = scored[0][0] if scored else 1.0
    hits: list[RetrievalHit] = []
    for rank, (raw_score, chunk, matched_terms, text) in enumerate(scored, start=1):
        relevance = round(min(1.0, raw_score / max_score), 6)
        metadata = dict(chunk.get("metadata", {}))
        citation = f"{chunk.get('source_path')}#{chunk.get('chunk_id')}"
        hits.append(
            RetrievalHit(
                chunk_id=str(chunk["chunk_id"]),
                document_id=str(chunk["document_id"]),
                universe_id=str(chunk["universe_id"]),
                collection_id=chunk.get("collection_id"),
                text=text,
                start_offset=chunk.get("start_offset"),
                end_offset=chunk.get("end_offset"),
                source_path=str(chunk.get("source_path", "")),
                source_name=str(chunk.get("source_name", "")),
                score=relevance,
                relevance_score=relevance,
                lexical_score=relevance,
                semantic_score=0.0,
                match_terms=matched_terms,
                citation=citation,
                metadata=metadata,
                diagnostics={"lexical_raw_score": round(raw_score, 6), "lexical_rank": rank},
            )
        )

    return hits


def search_chunks(
    query: str,
    chunks: list[dict[str, Any]],
    *,
    k: int = 5,
    filters: dict[str, Any] | None = None,
) -> list[RetrievalHit]:
    """Search an in-memory chunk list."""
    filtered_chunks = [chunk for chunk in chunks if _matches_filters(chunk, filters)]
    return score_chunks(query, filtered_chunks)[:k]


def search_corpus(
    query: str,
    *,
    universe_id: str = "terran_empire",
    k: int = 5,
    filters: dict[str, Any] | None = None,
    chunks_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Search a built corpus index and return JSON-compatible hits."""
    chunks_path = chunks_path or (default_text_index_dir(universe_id) / "chunks.jsonl")
    chunks = read_chunks_jsonl(chunks_path)
    hits = search_chunks(query, chunks, k=k, filters=filters)
    return [hit.to_dict() for hit in hits]
