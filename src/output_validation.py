"""Validation helpers for generated outputs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any

from src.kg_tools import validate_assertion
from src.memory_store import list_memory_items
from src.retrieval_hybrid import tokenize


SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class SourceCoverage:
    sentence: str
    supported: bool
    matched_terms: list[str] = field(default_factory=list)
    source_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def split_claims(text: str) -> list[str]:
    """Split generated text into checkable claims."""
    return [part.strip() for part in SENTENCE_RE.split(text.strip()) if len(part.strip()) >= 20]


def _content_terms(text: str) -> set[str]:
    stopwords = {
        "the", "and", "for", "with", "that", "this", "from", "into", "under",
        "une", "des", "les", "dans", "avec", "pour", "est", "sont", "qui",
    }
    return {term for term in tokenize(text) if len(term) > 3 and term not in stopwords}


def evaluate_source_coverage(text: str, retrieval_hits: list[dict[str, Any]]) -> list[SourceCoverage]:
    """Check whether each claim has lexical support in retrieved sources."""
    source_texts = [str(hit.get("text", "")) for hit in retrieval_hits]
    source_terms = [_content_terms(source_text) for source_text in source_texts]
    coverage: list[SourceCoverage] = []
    for sentence in split_claims(text):
        terms = _content_terms(sentence)
        best_matches: set[str] = set()
        source_count = 0
        for terms_in_source in source_terms:
            matches = terms & terms_in_source
            if len(matches) >= 2:
                source_count += 1
                best_matches.update(matches)
        coverage.append(
            SourceCoverage(
                sentence=sentence,
                supported=source_count > 0,
                matched_terms=sorted(best_matches),
                source_count=source_count,
            )
        )
    return coverage


def validate_generated_output(
    text: str,
    *,
    universe_id: str = "terran_empire",
    retrieval_hits: list[dict[str, Any]] | None = None,
    check_kg: bool = True,
    check_memory: bool = True,
) -> dict[str, Any]:
    """Validate generated text against sources, KG, and reusable memory."""
    retrieval_hits = retrieval_hits or []
    coverage = evaluate_source_coverage(text, retrieval_hits)
    unsupported = [item for item in coverage if not item.supported]
    kg_result = validate_assertion(text, universe_id=universe_id) if check_kg else {}
    reusable_memory = (
        list_memory_items(universe_id=universe_id, reusable_only=True)
        if check_memory
        else []
    )

    status = "validated"
    warnings: list[str] = []
    if kg_result.get("status") == "hard_contradiction":
        status = "hard_contradiction"
        warnings.append("Knowledge Graph hard contradiction detected")
    elif unsupported:
        status = "needs_human_review"
        warnings.append(f"{len(unsupported)} claim(s) lack retrieved source support")
    elif kg_result.get("status") == "attention":
        status = "attention"
        warnings.append("Knowledge Graph soft warning detected")

    return {
        "schema_version": 1,
        "universe_id": universe_id,
        "status": status,
        "warnings": warnings,
        "source_coverage": [item.to_dict() for item in coverage],
        "unsupported_claims": [item.to_dict() for item in unsupported],
        "kg": kg_result,
        "validated_memory_count": len(reusable_memory),
        "source_count": len(retrieval_hits),
    }
