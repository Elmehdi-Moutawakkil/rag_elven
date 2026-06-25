# RAGElven Technical Specification

Status: active architecture contract.

This document is the source of truth for the next architecture phase. Older
planning files are archived in `docs/archive/` and should not drive new work.

## Objective

Build a modular, open-source lore system where a user can maintain fictional
universes as versioned corpora, query them, generate new material, validate it
against canon, and experiment with interchangeable modules in Lab Mode.

## Operating Modes

Normal Mode:
The app chooses the right pipeline automatically and returns a polished answer,
translation, lore piece, or validated generation.

Lab Mode:
The user manually composes modules, changes providers, swaps indexes, tests
local models, and inspects intermediate outputs. This mode is essential for
open-source extension and experimentation.

## Architecture Layers

1. Canonical Git Repository

Role:
Version the canonical corpus and make lore changes reviewable.

Responsibilities:
Store universe folders, source notes, generated-but-validated lore, metadata,
and change history.

Inputs:
Markdown, text, PDF, images, audio, video, manual notes, validated generations.

Outputs:
Versioned corpus files and metadata ready for ingestion.

Suggested paths:
`corpus/universes/<universe_id>/canon/`
`corpus/universes/<universe_id>/notes/`
`corpus/universes/<universe_id>/validated_memory/`
`corpus/universes/<universe_id>/assets/`

2. Multimodal Storage

Role:
Keep raw and processed assets organized without mixing source files with indexes.

Responsibilities:
Store original files, extracted text, normalized metadata, thumbnails,
transcripts, captions, and asset hashes.

Formats:
Markdown, JSON, SQLite, image/audio/video files, extracted text sidecars.

Suggested paths:
`storage/raw/`
`storage/processed/`
`storage/manifests/`

3. Multimodal Ingestion

Role:
Transform raw files into normalized, traceable records.

Responsibilities:
Extract text from PDFs, parse Markdown, transcribe audio, caption images,
hash assets, detect duplicates, and create ingestion manifests.

Outputs:
Normalized documents with stable IDs, source pointers, modality, timestamps,
and provenance.

Likely modules:
`src/ingestion/`
`scripts/ingest_universe.py`

4. Indexing And Retrieval

Role:
Let the system find the right material quickly.

Responsibilities:
Chunk text, embed text/images/audio transcripts, build FAISS or other indexes,
query by universe, modality, source, time period, entity, and confidence.

Current state:
FAISS and SQLite already exist for text retrieval and dictionary lookup.

Likely modules:
`src/retrieval.py`
`src/embeddings.py`
future `src/indexing/`

5. Knowledge Graph

Role:
Represent canon as entities, relations, and constraints.

Responsibilities:
Store entities, aliases, relationships, canon facts, contradiction rules,
source provenance, and validation severity.

Current state:
SQLite Knowledge Graph exists for Tolkien and Terran Empire.

Likely modules:
`src/knowledge_graph.py`
future `src/kg/`

6. Validated Memory

Role:
Store accepted AI outputs as new controlled knowledge, without confusing them
with original canon.

Responsibilities:
Track generated lore, validation status, reviewer decision, source context,
KG impact, and whether the content can be reused in future generations.

Suggested states:
`draft`, `validated`, `rejected`, `superseded`.

7. AI Agent

Role:
Choose where to search, which tools to call, and when to ask for validation.

Responsibilities:
Route requests, select universe, inspect metadata, retrieve context, call tools,
ask generation models, request validation, and produce traceable outputs.

Current state:
Query rewriting and routing exist as early agent-like components.

Likely modules:
`src/router.py`
`src/query_rewriter.py`
future `src/agent/`

8. Tools And MCP

Role:
Expose internal capabilities through controlled tool interfaces, then MCP
servers when the local tool contracts are stable.

Responsibilities:
Provide tools for search, ingestion, KG lookup, validation, memory write,
asset fetch, and generation.

Implementation order:
First Python tool interfaces, then MCP wrappers. Do not start with MCP before
the internal tool contracts are stable.

9. Generation And Fine-Tuning

Role:
Generate lore, translations, images, audio, and structured data while respecting
retrieved context and validation constraints.

Responsibilities:
Support provider APIs, local models, LoRA/fine-tuning experiments, prompt
templates, model configuration, and output traces.

Current state:
Provider-backed text generation exists. Local LM Studio fallback exists for
translation polish.

10. Validation, Safety, And Governance

Role:
Prevent hallucinations, secret leaks, corrupted memory, and unreviewed canon
changes.

Responsibilities:
Validate against KG, cite sources, separate canon from generated memory, avoid
committing secrets, log failures, and require human approval for durable memory.

Current state:
`scripts/sanity_check.py`, regression tests, `.env` handling, and KG validation
are in place.

## Implementation Order

1. Keep the current app stable.
2. Define canonical corpus folders under Git.
3. Formalize module/tool interfaces for Normal Mode and Lab Mode.
4. Move ingestion/indexing toward explicit universe manifests.
5. Expand KG and validation contracts.
6. Add validated memory.
7. Build a real agent layer over the internal tools.
8. Add multimodal ingestion and retrieval.
9. Add MCP wrappers after internal tools are stable.
10. Explore fine-tuning/LoRA only after enough validated data exists.

## Current Validation Commands

```bash
make sanity
make test
```

Both commands should pass before architecture changes are committed.
