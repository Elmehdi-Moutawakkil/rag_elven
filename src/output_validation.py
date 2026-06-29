"""Validation helpers for generated outputs."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any

from src.kg_tools import validate_assertion
from src.memory_store import list_memory_items
from src.retrieval_hybrid import tokenize


SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
CITATION_RE = re.compile(r"\[(\d+)\]")


@dataclass(frozen=True)
class SourceCoverage:
    sentence: str
    supported: bool
    matched_terms: list[str] = field(default_factory=list)
    source_count: int = 0
    citation_ids: list[int] = field(default_factory=list)
    cited_source_count: int = 0
    missing_citation: bool = False
    claim_type: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ConstraintCheck:
    kind: str
    value: str
    passed: bool
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StyleCheck:
    name: str
    passed: bool
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def split_claims(text: str) -> list[str]:
    """Split generated text into checkable claims."""
    normalized = re.sub(r"([.!?])\s+((?:\[\d+\]\s*)+)", r" \2\1", text.strip())
    return [part.strip() for part in SENTENCE_RE.split(normalized) if len(part.strip()) >= 20]


def _content_terms(text: str) -> set[str]:
    stopwords = {
        "the", "and", "for", "with", "that", "this", "from", "into", "under",
        "une", "des", "les", "dans", "avec", "pour", "est", "sont", "qui",
    }
    return {term for term in tokenize(text) if len(term) > 3 and term not in stopwords}


def _citation_ids(text: str) -> list[int]:
    return [int(match.group(1)) for match in CITATION_RE.finditer(text)]


def _claim_type(*, supported: bool, cited_source_count: int, matched_terms: list[str]) -> str:
    if supported and cited_source_count > 0:
        return "canon_supported"
    if supported:
        return "uncited_supported"
    if matched_terms:
        return "extrapolation"
    return "invention_or_unsupported"


def evaluate_source_coverage(
    text: str,
    retrieval_hits: list[dict[str, Any]],
    *,
    require_citations: bool = True,
) -> list[SourceCoverage]:
    """Check whether each claim has lexical support in retrieved sources."""
    source_texts = [str(hit.get("text", "")) for hit in retrieval_hits]
    source_terms = [_content_terms(source_text) for source_text in source_texts]
    coverage: list[SourceCoverage] = []
    for sentence in split_claims(text):
        terms = _content_terms(sentence)
        best_matches: set[str] = set()
        source_count = 0
        cited_ids = _citation_ids(sentence)
        cited_source_count = 0
        for terms_in_source in source_terms:
            matches = terms & terms_in_source
            if len(matches) >= 2:
                source_count += 1
                best_matches.update(matches)
        for citation_id in cited_ids:
            if 1 <= citation_id <= len(retrieval_hits):
                cited_source_count += 1
        matched_terms = sorted(best_matches)
        supported = source_count > 0
        coverage.append(
            SourceCoverage(
                sentence=sentence,
                supported=supported,
                matched_terms=matched_terms,
                source_count=source_count,
                citation_ids=cited_ids,
                cited_source_count=cited_source_count,
                missing_citation=require_citations and supported and cited_source_count == 0,
                claim_type=_claim_type(
                    supported=supported,
                    cited_source_count=cited_source_count,
                    matched_terms=matched_terms,
                ),
            )
        )
    return coverage


def evaluate_constraints(text: str, constraints: dict[str, Any] | None = None) -> list[ConstraintCheck]:
    """Evaluate simple deterministic generation constraints."""
    constraints = constraints or {}
    lowered = text.lower()
    checks: list[ConstraintCheck] = []

    for value in constraints.get("must_include", []):
        passed = str(value).lower() in lowered
        checks.append(
            ConstraintCheck(
                kind="must_include",
                value=str(value),
                passed=passed,
                message="present" if passed else "missing required content",
            )
        )

    for value in constraints.get("must_not_include", []):
        passed = str(value).lower() not in lowered
        checks.append(
            ConstraintCheck(
                kind="must_not_include",
                value=str(value),
                passed=passed,
                message="absent" if passed else "forbidden content present",
            )
        )

    return checks


def evaluate_style(text: str, style_rules: dict[str, Any] | None = None) -> list[StyleCheck]:
    """Run lightweight style checks without calling an LLM."""
    style_rules = style_rules or {}
    checks: list[StyleCheck] = []
    if not style_rules:
        return checks

    max_words = style_rules.get("max_words")
    if max_words is not None:
        word_count = len(tokenize(text))
        passed = word_count <= int(max_words)
        checks.append(StyleCheck("max_words", passed, f"{word_count}/{max_words} words"))

    required_tone = style_rules.get("required_tone")
    if required_tone:
        value = str(required_tone).lower()
        lowered = text.lower()
        if value == "scholarly":
            markers = ("according", "source", "evidence", "records", "canon")
            passed = any(marker in lowered for marker in markers)
            checks.append(StyleCheck("required_tone", passed, "scholarly markers present" if passed else "scholarly markers missing"))

    return checks


def summarize_claim_types(coverage: list[SourceCoverage]) -> dict[str, int]:
    summary: dict[str, int] = {
        "canon_supported": 0,
        "uncited_supported": 0,
        "extrapolation": 0,
        "invention_or_unsupported": 0,
    }
    for item in coverage:
        summary[item.claim_type] = summary.get(item.claim_type, 0) + 1
    return summary


def validate_generated_output(
    text: str,
    *,
    universe_id: str = "terran_empire",
    retrieval_hits: list[dict[str, Any]] | None = None,
    constraints: dict[str, Any] | None = None,
    style_rules: dict[str, Any] | None = None,
    require_citations: bool = True,
    check_kg: bool = True,
    check_memory: bool = True,
) -> dict[str, Any]:
    """Validate generated text against sources, KG, and reusable memory."""
    retrieval_hits = retrieval_hits or []
    coverage = evaluate_source_coverage(text, retrieval_hits, require_citations=require_citations)
    unsupported = [item for item in coverage if not item.supported]
    uncited_supported = [item for item in coverage if item.missing_citation]
    constraint_checks = evaluate_constraints(text, constraints)
    failed_constraints = [item for item in constraint_checks if not item.passed]
    style_checks = evaluate_style(text, style_rules)
    failed_style = [item for item in style_checks if not item.passed]
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
    elif failed_constraints:
        status = "constraint_violation"
        warnings.append(f"{len(failed_constraints)} generation constraint(s) failed")
    elif unsupported:
        status = "needs_human_review"
        warnings.append(f"{len(unsupported)} claim(s) lack retrieved source support")
    elif uncited_supported:
        status = "needs_citation"
        warnings.append(f"{len(uncited_supported)} supported claim(s) lack explicit citation")
    elif kg_result.get("status") == "attention":
        status = "attention"
        warnings.append("Knowledge Graph soft warning detected")
    elif failed_style:
        status = "style_warning"
        warnings.append(f"{len(failed_style)} style check(s) failed")

    return {
        "schema_version": 1,
        "universe_id": universe_id,
        "status": status,
        "warnings": warnings,
        "source_coverage": [item.to_dict() for item in coverage],
        "unsupported_claims": [item.to_dict() for item in unsupported],
        "uncited_supported_claims": [item.to_dict() for item in uncited_supported],
        "claim_type_summary": summarize_claim_types(coverage),
        "constraints": [item.to_dict() for item in constraint_checks],
        "failed_constraints": [item.to_dict() for item in failed_constraints],
        "style": [item.to_dict() for item in style_checks],
        "failed_style": [item.to_dict() for item in failed_style],
        "kg": kg_result,
        "continuity": {
            "kg_status": kg_result.get("status") if kg_result else "not_checked",
            "validated_memory_count": len(reusable_memory),
        },
        "validated_memory_count": len(reusable_memory),
        "source_count": len(retrieval_hits),
        "human_review_required": status in {
            "hard_contradiction",
            "constraint_violation",
            "needs_human_review",
            "needs_citation",
            "attention",
            "style_warning",
        },
    }
