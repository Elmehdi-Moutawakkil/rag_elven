# Fine-Tuning And LoRA Strategy

Status: Step 17 foundation only.

## Decision

Do not train now.

RAGElven does not yet have enough validated examples to justify LoRA or
fine-tuning. RAG, KG validation, source citations, and validated memory remain
the source of truth.

## Useful Training Targets

| Task | Useful when | Metrics |
|---|---|---|
| Style adaptation | Many validated outputs share a stable voice | style rubric, citation preservation, human preference |
| Document classification | Documents need repeated routing by type/topic | accuracy, macro F1 |
| Entity extraction | KG examples have source spans | precision, recall, F1, span accuracy |
| Query reformulation | Retrieval failures have validated rewrites | hit rate, MRR, source recall |
| Canonical formatting | Outputs need strict JSON/Markdown | schema validity, field completeness |
| Lore generation style | Many human-validated drafts exist | source support, KG violation rate, human score |

## Not Training Targets

Do not use fine-tuning as the authority for:

- factual knowledge;
- source lookup;
- canon validation;
- global continuity;
- memory approval;
- KG consistency.

## Dataset Rules

Training examples may come only from reusable validated memory.

Required gates:

- memory status is `validated`;
- sources are present;
- KG has no hard contradiction;
- reviewer and validation history are retained;
- rejected, draft, pending, or superseded memory is excluded.

## Current Dataset Export

Foundation code:

- `src/training_datasets.py`

Default output path:

- `datasets/fine_tuning/<universe_id>/<task>.jsonl`
- `datasets/fine_tuning/<universe_id>/<task>.manifest.json`

If no validated memory exists, the manifest status is:

- `blocked_no_validated_examples`

This is expected for now.

## Minimum Before Training

- 50 validated examples per task minimum;
- 200 preferred examples per task;
- baseline without fine-tuning;
- held-out evaluation set;
- budget estimate;
- rollback plan;
- comparison report before/after.

## Risks

- training on draft or unsupported content;
- model learns style but loses citation discipline;
- using fine-tuning instead of retrieval;
- contaminating datasets with rejected memory;
- paying API/GPU costs before metrics exist.
