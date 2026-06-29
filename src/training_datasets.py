"""Fine-tuning dataset foundations.

This module prepares versioned dataset manifests from validated memory only.
It does not train, fine-tune, call model APIs, or create synthetic examples.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from src.memory_store import list_memory_items
from src.settings import PROJECT_ROOT


TrainingTask = Literal[
    "style_adaptation",
    "document_classification",
    "entity_extraction",
    "query_reformulation",
    "canonical_formatting",
    "lore_generation_style",
]

DATASET_SCHEMA_VERSION = 1
SUPPORTED_TASKS: tuple[TrainingTask, ...] = (
    "style_adaptation",
    "document_classification",
    "entity_extraction",
    "query_reformulation",
    "canonical_formatting",
    "lore_generation_style",
)


@dataclass(frozen=True)
class TrainingExample:
    schema_version: int
    example_id: str
    universe_id: str
    task: TrainingTask
    input: dict[str, Any]
    output: dict[str, Any]
    sources: list[str]
    validation: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def dataset_dir(universe_id: str, root: Path = PROJECT_ROOT) -> Path:
    return root / "datasets" / "fine_tuning" / universe_id


def stable_example_id(universe_id: str, task: str, memory_id: str) -> str:
    digest = hashlib.sha256(f"{universe_id}:{task}:{memory_id}".encode("utf-8")).hexdigest()
    return f"train_{digest[:16]}"


def training_strategy() -> dict[str, Any]:
    """Return the project training strategy without starting training."""
    return {
        "schema_version": DATASET_SCHEMA_VERSION,
        "status": "deferred_until_validated_data",
        "source_of_truth": "RAG retrieval, KG validation, and validated memory remain authoritative.",
        "trainable_tasks": [
            {
                "task": "style_adaptation",
                "useful_when": "Many validated examples share a stable target voice or report style.",
                "not_for": "Factual recall or source lookup.",
                "metrics": ["style rubric pass rate", "citation preservation", "human preference"],
            },
            {
                "task": "document_classification",
                "useful_when": "Corpus documents need repeated routing by type, canon status, or topic.",
                "not_for": "Canon validation.",
                "metrics": ["accuracy", "macro_f1", "confusion_matrix"],
            },
            {
                "task": "entity_extraction",
                "useful_when": "Validated KG extraction examples are available.",
                "not_for": "Final KG writes without review.",
                "metrics": ["precision", "recall", "f1", "source_span_accuracy"],
            },
            {
                "task": "query_reformulation",
                "useful_when": "Repeated retrieval failures have validated improved rewrites.",
                "not_for": "Answer generation.",
                "metrics": ["retrieval_hit_rate", "mrr", "source_recall"],
            },
            {
                "task": "canonical_formatting",
                "useful_when": "Outputs need a strict JSON or Markdown shape.",
                "not_for": "Truth checking.",
                "metrics": ["schema_validity", "field_completeness", "repair_rate"],
            },
            {
                "task": "lore_generation_style",
                "useful_when": "Enough human-validated lore drafts exist with stable style goals.",
                "not_for": "Knowledge exactness, KG consistency, or citation validation.",
                "metrics": ["source_support_rate", "kg_violation_rate", "human_review_score"],
            },
        ],
        "minimum_before_training": {
            "validated_examples_per_task": 50,
            "preferred_examples_per_task": 200,
            "baseline_required": True,
            "evaluation_set_required": True,
            "budget_required": True,
        },
        "risks": [
            "Premature training on draft or unsupported content.",
            "Model memorizes style but loses citation discipline.",
            "Fine-tuning used as a substitute for retrieval or KG validation.",
            "Dataset contamination from rejected or superseded memory.",
            "API or GPU costs without a baseline comparison.",
        ],
    }


def example_from_memory_item(
    item: dict[str, Any],
    *,
    task: TrainingTask = "lore_generation_style",
) -> TrainingExample:
    """Convert one validated memory item into a conservative training example."""
    memory_id = str(item["memory_id"])
    universe_id = str(item["universe_id"])
    return TrainingExample(
        schema_version=DATASET_SCHEMA_VERSION,
        example_id=stable_example_id(universe_id, task, memory_id),
        universe_id=universe_id,
        task=task,
        input={
            "summary": item.get("summary", ""),
            "sources": list(item.get("sources", [])),
            "instruction": "Produce only sourced, reviewable lore text in the validated project format.",
        },
        output={
            "content": item.get("content", ""),
        },
        sources=list(item.get("sources", [])),
        validation={
            "memory_status": item.get("status"),
            "kg_validation": item.get("kg_validation", {}),
            "validated_at": item.get("validated_at"),
            "reviewer": item.get("reviewer"),
            "content_hash": item.get("content_hash"),
        },
        metadata={
            "memory_id": memory_id,
            "memory_version": item.get("version", 1),
            "model": item.get("model"),
        },
    )


def build_training_dataset(
    *,
    universe_id: str,
    task: TrainingTask = "lore_generation_style",
    root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """Build examples from reusable validated memory without writing files."""
    if task not in SUPPORTED_TASKS:
        raise ValueError(f"Unsupported training task: {task}")
    memory_items = list_memory_items(universe_id=universe_id, reusable_only=True, root=root)
    examples = [example_from_memory_item(item, task=task).to_dict() for item in memory_items]
    return {
        "schema_version": DATASET_SCHEMA_VERSION,
        "universe_id": universe_id,
        "task": task,
        "status": "ready_for_baseline" if examples else "blocked_no_validated_examples",
        "created_at": utc_now(),
        "example_count": len(examples),
        "examples": examples,
        "strategy": training_strategy(),
    }


def write_training_dataset(
    *,
    universe_id: str,
    task: TrainingTask = "lore_generation_style",
    root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    """Write a versioned JSONL dataset and manifest from validated memory only."""
    dataset = build_training_dataset(universe_id=universe_id, task=task, root=root)
    output_dir = dataset_dir(universe_id, root)
    output_dir.mkdir(parents=True, exist_ok=True)
    examples_path = output_dir / f"{task}.jsonl"
    manifest_path = output_dir / f"{task}.manifest.json"

    lines = [json.dumps(example, ensure_ascii=False, sort_keys=True) for example in dataset["examples"]]
    examples_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    manifest = {key: value for key, value in dataset.items() if key != "examples"}
    manifest["examples_path"] = examples_path.relative_to(root).as_posix()
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest
