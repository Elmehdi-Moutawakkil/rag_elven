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


TOKEN_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9']+")


@dataclass(frozen=True)
class RetrievalHit:
    """One ranked retrieval result with source provenance."""

    chunk_id: str
    document_id: str
    universe_id: str
    collection_id: str | None
    text: str
    source_path: str
    source_name: str
    score: float
    lexical_score: float
    semantic_score: float
    match_terms: list[str] = field(default_factory=list)
    citation: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def tokenize(text: str) -> list[str]:
    """Lowercase tokenization shared by indexing and retrieval."""
    return [token.lower() for token in TOKEN_RE.findall(text)]


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
    hits: list[RetrievalHit] = []

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
        lexical_score = score + phrase_bonus
        semantic_score = 0.0
        combined_score = lexical_score + semantic_score
        if combined_score <= 0:
            continue

        citation = f"{chunk.get('source_path')}#{chunk.get('chunk_id')}"
        hits.append(
            RetrievalHit(
                chunk_id=str(chunk["chunk_id"]),
                document_id=str(chunk["document_id"]),
                universe_id=str(chunk["universe_id"]),
                collection_id=chunk.get("collection_id"),
                text=text,
                source_path=str(chunk.get("source_path", "")),
                source_name=str(chunk.get("source_name", "")),
                score=round(combined_score, 6),
                lexical_score=round(lexical_score, 6),
                semantic_score=semantic_score,
                match_terms=sorted(matched_terms),
                citation=citation,
                metadata=dict(chunk.get("metadata", {})),
            )
        )

    return sorted(hits, key=lambda hit: hit.score, reverse=True)


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
