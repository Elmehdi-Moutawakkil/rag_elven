# RAGElven Technical Specification

Status: active architecture contract.
Date: 2026-06-28.

Older planning files are archived in `docs/archive/`. They are historical
context, not active instructions.

## Objective

RAGElven is an open-source modular lore platform. Its goal is to let users
store fictional universes as versioned corpora, search them, generate new
material, validate generated content against canon, and experiment with
interchangeable AI modules.

The system must support two modes:

Normal Mode:
The application chooses the right pipeline automatically and gives the user a
clean answer, translation, generated lore item, or validated output.

Lab Mode:
The user manually composes modules, swaps providers, selects universes, inspects
intermediate results, and tests their own models or future modules.

## Current Repository Baseline

Existing app:
`app.py`

Current source modules:
`src/router.py`, `src/query_rewriter.py`, `src/retrieval.py`,
`src/embeddings.py`, `src/llm.py`, `src/translator.py`, `src/ir.py`,
`src/morphology.py`, `src/syntax.py`, `src/lore_generator.py`,
`src/lore_generator_p4.py`, `src/lore_generator_generic.py`,
`src/knowledge_graph.py`, `src/layer_registry.py`,
`src/module_registry.py`, `src/normal_mode.py`, `src/pipeline_executor.py`,
`src/ingestion/`, `src/indexing/`, `src/retrieval_hybrid.py`,
`src/kg_tools.py`, `src/memory_store.py`, `src/llm_provider.py`,
`src/output_validation.py`, `src/multimodal.py`, `src/agent/`,
`src/mcp_tools.py`, `src/settings.py`

Current data:
`corpus/universes/tolkien/`, `corpus/universes/terran_empire/`,
`data/quenya_course/`, `data/quenya_dictionary/`, `data/sindarin/`,
`data/universes/terran_empire/`

Current indexes and databases:
`vector_db/faiss.index`, `vector_db/metadata.json`,
`vector_db/dictionary.sqlite`, `vector_db/knowledge_graph.sqlite`,
`vector_db/terran_empire/faiss.index`,
`vector_db/terran_empire/metadata.json`,
`vector_db/terran_empire/knowledge_graph.sqlite`,
`storage/processed/terran_empire/documents.jsonl`,
`indexes/terran_empire/text/chunks.jsonl`

Current validation:
`scripts/sanity_check.py`, `tests/`, `Makefile`

## Cross-Cutting Design Rules

1. Do not treat generated content as canon unless it has been validated.
2. Keep canon, generated memory, raw assets, indexes, and runtime caches separate.
3. Every durable output needs provenance: source files, chunks, model, prompt or
   tool trace, validation result, and timestamp.
4. Lab Mode modules must be small, explicit, and independently testable.
5. MCP comes after stable internal tool contracts, not before.
6. Local and provider-backed models must share the same high-level interfaces.
7. Missing API keys must degrade gracefully where possible.
8. No real API key may be committed.

## Layer 1: Canonical Git Repository

Role:
Version the source-of-truth corpus for each universe.

Responsibilities:
Store canonical text, notes, source manifests, asset references, validated
memory, and reviewable changes. Make the corpus understandable to both humans
and tools.

Data in:
Manual notes, Markdown lore files, text files, PDFs, image/audio/video asset
references, imported source metadata, validated generated lore.

Data out:
Versioned corpus records ready for ingestion, review, indexing, and validation.

Formats:
Markdown for human-authored canon and notes.
JSON for manifests and metadata.
Binary assets referenced by manifest, not silently mixed with indexes.

Folders/files to create:
`corpus/README.md`
`corpus/universes/<universe_id>/manifest.json`
`corpus/universes/<universe_id>/SUMMARY.md`
`corpus/universes/<universe_id>/canon/`
`corpus/universes/<universe_id>/notes/`
`corpus/universes/<universe_id>/assets/`
`corpus/universes/<universe_id>/validated_memory/`

Tables:
None required at this layer. Git is the versioning database.

Manifest fields:
`universe_id`, `display_name`, `collections`, `themes`, `canon_policy`,
`default_kg_path`, `default_index_path`, `summary_path`.

Current modules concerned:
Future ingestion scripts will read this layer. Existing `data/` should remain
available until migration is complete.

Dependencies:
Git, file-system conventions, JSON validation.

Risks:
Moving too fast may break existing paths in `app.py`, `src/retrieval.py`, and
build scripts. Large binary assets can bloat Git if stored carelessly.

Implementation order:
Create folder structure and manifests first. Then migrate one universe as a
pilot. Add `SUMMARY.md` files before large-scale ingestion so the future agent
can read section summaries before loading chunks. Keep existing `data/` paths
working until all tests and app flows pass.

## Layer 2: Multimodal Storage

Role:
Store raw and processed multimodal assets without confusing them with canon or
indexes.

Responsibilities:
Keep original files, extracted text, thumbnails, image captions, audio
transcripts, video scene descriptions, hashes, and processing metadata.

Data in:
PDFs, text files, Markdown files, images, audio, video, generated assets,
external references.

Data out:
Stable asset records and processed sidecars for ingestion and retrieval.

Formats:
Original binary formats for raw assets.
`.txt` or `.md` sidecars for extracted text.
`.json` sidecars for metadata.
SQLite for larger asset catalogs if JSON becomes too large.

Folders/files to create:
`storage/raw/<universe_id>/`
`storage/processed/<universe_id>/`
`storage/manifests/<universe_id>.json`
`storage/cache/`

Tables:
Optional future table `assets`:
`asset_id`, `universe_id`, `modality`, `path`, `sha256`, `source_uri`,
`license`, `access_level`, `created_at`, `processed_at`, `status`.

Optional future table `asset_derivatives`:
`derivative_id`, `asset_id`, `kind`, `path`, `model`, `created_at`,
`metadata_json`.

Current modules concerned:
`src/multimodal.py` defines asset records, media derivatives, modality
detection, and processing plans. Future `src/storage/` can provide path and
manifest helpers if JSONL storage becomes too small.

Dependencies:
Current: Python standard library only for media metadata.
Future: `pypdf`, OCR, image, audio, and video processing libraries as needed.

Risks:
Asset licensing, oversized repo, duplicate files, unclear provenance, slow
processing.

Implementation order:
Start with manifests and raw/processed folders. Only then add processors for
image, audio, and video.

## Layer 3: Multimodal Ingestion

Role:
Convert raw corpus and assets into normalized records.

Responsibilities:
Extract text from PDFs, parse Markdown, normalize plain text, create stable
document IDs, attach provenance, transcribe audio, caption images, describe
video scenes, and write ingestion reports.

Data in:
Files from `corpus/` and `storage/raw/`.

Data out:
Normalized documents and asset records ready for chunking, embedding, KG
extraction, and validation.

Formats:
JSONL for normalized records.
JSON ingestion reports.
Text sidecars for extracted text.

Folders/files to create:
`src/ingestion/__init__.py`
`src/ingestion/documents.py`
`src/ingestion/loaders.py`
`src/ingestion/manifests.py`
`scripts/ingest_universe.py`
`storage/processed/<universe_id>/documents.jsonl`

Tables:
Optional future table `ingestion_runs`:
`run_id`, `universe_id`, `started_at`, `finished_at`, `input_count`,
`output_count`, `error_count`, `status`.

Current modules concerned:
`src/ingestion/documents.py` defines normalized document records.
`src/ingestion/loaders.py` ingests Markdown and plain text.
`src/ingestion/manifests.py` reads universe manifests.
`scripts/ingest_universe.py` writes processed JSONL records and reports.
`src/text_splitter.py` already handles PDF/text chunk preparation.
`scripts/build_universe_index.py` already builds universe indexes.

Dependencies:
Current: `pypdf`, `langchain_text_splitters`.
Future: OCR, speech-to-text, image captioning if multimodal ingestion expands.

Risks:
Bad extraction quality, duplicated chunks, broken page/source attribution,
expensive multimodal processing.

Implementation order:
First normalize text and Markdown. Then PDF extraction. Then images/audio/video.

Current status:
Text and Markdown ingestion are implemented for manifest-backed universes.
Image and audio can now be represented as normalized metadata-only documents
with planned derivatives for OCR, image description, image embedding, audio
transcription, and audio embedding. No OCR, transcription, description,
embedding, model call, or corpus mutation is performed by this layer.
PDF and video ingestion remain future extensions.

## Layer 4: Indexing And Retrieval

Role:
Retrieve the right evidence for a request.

Responsibilities:
Chunk normalized documents, create embeddings, build indexes, load indexes,
query by universe, modality, source, period, entity, and confidence. Return
chunks with traceable provenance. Support hybrid retrieval: vector search plus
lexical and structured filters.

Data in:
Normalized documents from ingestion, query text, routing metadata, selected
universe.

Data out:
Ranked retrieval results with text, score, source, page, chunk ID, modality,
and universe ID.

Formats:
FAISS index files for dense retrieval.
JSONL chunks and JSON metadata for index records.
SQLite for dictionaries and structured lookup.

Folders/files to create:
`indexes/<universe_id>/text/chunks.jsonl`
`indexes/<universe_id>/text/manifest.json`
`indexes/<universe_id>/text/faiss.index`
`indexes/<universe_id>/text/metadata.json`
Future: `indexes/<universe_id>/image/`, `indexes/<universe_id>/audio/`

Tables:
Current:
`vector_db/dictionary.sqlite`

Optional future table `chunks`:
`chunk_id`, `document_id`, `universe_id`, `modality`, `text`, `source_path`,
`page`, `start_offset`, `end_offset`, `embedding_model`, `index_path`.

Optional future catalog tables:
`collections`, `files`, `tags`, `sources`, `access_rights`.

Current modules concerned:
`src/indexing/chunks.py`
`src/indexing/build.py`
`src/retrieval_hybrid.py`
`scripts/build_retrieval_index.py`
`src/retrieval.py`
`src/embeddings.py`
`src/database.py`
`src/query_rewriter.py`
`scripts/build_universe_index.py`

Dependencies:
`sentence-transformers`, `faiss-cpu`, `numpy`, SQLite.

Risks:
Index metadata drift, stale indexes after corpus changes, weak retrieval on
small corpora, hidden coupling to old `vector_db/` paths.

Implementation order:
Keep current `vector_db/` working. Introduce universe manifest fields for index
paths. Move new indexes to `indexes/` only after adapters are tested.

Current status:
Manifest-driven text chunking and deterministic lexical retrieval are
implemented for `terran_empire`. `src.retrieval_adapter.retrieve_evidence`
is the unified retrieval facade for manifest-backed corpora. Existing FAISS
runtime remains available for the Tolkien/Elvish legacy corpus.

## Layer 5: Knowledge Graph

Role:
Represent canon as entities, aliases, relations, and contradiction rules.

Responsibilities:
Store named entities, relationships, canon facts, aliases, severities,
events, periods, timeline constraints, political hierarchies, continuity rules,
validation patterns, source provenance, and graph queries.

Data in:
Curated canon facts, extracted entities/relations, validated generated memory,
manual graph edits.

Data out:
Entity lookups, relation lookups, validation results, contradiction reports,
canon constraints for generation.

Formats:
SQLite for the current graph.
JSON export/import for reviewable graph diffs.

Folders/files to create:
`kg/<universe_id>/knowledge_graph.sqlite`
`kg/<universe_id>/export.json`
`src/kg/` when the current module is split.

Tables:
Current expected tables:
`entities`, `relations`, `canon_facts`.

Future tables:
`aliases`, `sources`, `validation_rules`, `entity_mentions`, `events`,
`timeline`, `periods`, `continuity_constraints`.

Current modules concerned:
`src/knowledge_graph.py`
`src/kg_tools.py`
`scripts/build_kg.py`
`scripts/build_kg_terran.py`
`src/lore_generator_p4.py`
`src/layer_registry.py` for L09.

Dependencies:
SQLite, regex validation, future NLP extraction if automated KG expansion is
added.

Risks:
False positives from regex rules, incomplete canon coverage, graph drift between
universes, over-trusting generated facts.

Implementation order:
Document the current SQLite schema. Add import/export. Then move from hardcoded
builders to universe-specific graph manifests.

Current status:
Sourced KG read tools expose entity lookup, relation lookup, source evidence,
assertion validation, and deterministic JSON export for review. The current
schema is documented in `docs/KNOWLEDGE_GRAPH.md`. Entities, relations, and
canon rules now carry `source_file`; precise source spans remain future work.

## Layer 6: Validated Memory

Role:
Store accepted AI outputs as reusable project memory without turning them into
original canon.

Responsibilities:
Track generated lore, reviewer decisions, validation status, KG violations,
retrieval context, model used, prompt template, and whether the output can be
used in future generations. Keep request history and the reason a memory item
was accepted, rejected, or left pending.

Data in:
Generated stories, answers, translations, images, audio, user approvals,
validation reports.

Data out:
Validated memory records for retrieval, KG candidate facts, changelog entries,
and future generation context.

Formats:
Current implementation uses JSONL for append-readable project memory records.
Future SQLite can be added when query volume requires it.

Folders/files:
`memory/<universe_id>/memory.jsonl`

Record fields:
`memory_id`, `universe_id`, `status`, `content`, `summary`, `sources`,
`kg_validation`, `model`, `created_at`, `updated_at`, `validated_at`,
`reviewer`, `version`, `content_hash`, `events`, `metadata`.

Current modules concerned:
`src/memory_store.py` provides JSONL memory records, review statuses, event
history, source/KG reuse gates, edit/rollback, and reusable-only reads for
validated memory.

Dependencies:
SQLite, JSON, human review flow.

Risks:
Memory pollution, canon/generated confusion, accepting hallucinated facts,
unclear reviewer accountability.

Implementation order:
Create status model first: `draft`, `pending`, `validated`, `rejected`,
`superseded`. Require manual approval before retrieval uses memory. Only later
add automatic candidate extraction.

Current status:
JSONL memory with controlled status transitions, review gates, versioning,
rollback, and reusable-only reads is implemented. It is not yet connected to
the Streamlit UI.

## Layer 7: AI Agent

Role:
Decide what to do for a user request.

Responsibilities:
Classify intent, select universe, select tools, retrieve context, inspect KG,
choose generation provider, request validation, return an auditable trace, and
fall back gracefully when providers or keys are missing.

Data in:
User request, selected mode, available universes, tool registry, model config,
environment state.

Data out:
Plan, executed tool trace, final response, intermediate outputs for Lab Mode.

Formats:
JSON-compatible trace objects.
Typed Python dataclasses or dictionaries for early implementation.

Folders/files to create:
`src/agent/__init__.py`
`src/agent/planner.py`
`src/agent/state.py`
`src/agent/traces.py`

Tables:
Optional future table `agent_runs`:
`run_id`, `user_input`, `mode`, `universe_id`, `started_at`, `finished_at`,
`status`, `trace_json`.

Current modules concerned:
`src/agent/planner.py`
`src/router.py`
`src/query_rewriter.py`
`src/normal_mode.py`
`src/pipeline_executor.py`
`src/layer_registry.py`
`src/module_registry.py`
`app.py`

Dependencies:
Current provider SDKs: Groq, Anthropic, OpenAI-compatible local endpoint.
Candidate local agent/model stack: Hermes or a similar small local model for
routing, planning, drafts, and simple tool orchestration.

Risks:
Opaque decisions, tool loops, hidden API costs, brittle prompts, hard-to-debug
state. The agent must not read the whole corpus blindly, write directly to
canon, ignore KG violations, or self-approve generated lore.

Implementation order:
First formalize the existing router and Lab Mode pipeline outputs as traces.
Then add a small planner. Avoid autonomous write actions until validation and
memory governance exist.

Current status:
A controlled agent runner can retrieve, optionally generate through an
`LLMProvider`, validate output, and return an inspectable trace. The runner now
declares a small tool registry, tags each tool with risk metadata, logs risk
assessment before execution, and blocks risky write/canonization/publishing
requests behind human confirmation. Normal Mode now resolves the effective
universe before execution. Clear Terran/Star Trek questions route to
`terran_empire`, and non-Tolkien pipelines exclude
Tolkien-only dictionary, translation, morphology, and syntax modules.

## Layer 8: Tools And MCP

Role:
Expose internal capabilities through stable tool contracts, then wrap them as
MCP servers later.

Responsibilities:
Provide controlled tools for search, KG lookup, validation, ingestion, memory
write, asset fetch, generation, and test execution.

Data in:
Tool call arguments as structured JSON.

Data out:
Tool results as structured JSON with status, data, warnings, and trace IDs.

Formats:
Python tool functions first.
JSON schemas for tool inputs and outputs.
MCP server definitions around stable Python handlers.

Folders/files to create:
`src/mcp_tools.py`
`mcp/ragelven_server.py`
`src/tools/__init__.py`
`src/tools/search.py`
`src/tools/kg.py`
`src/tools/validation.py`
`src/tools/memory.py`
`src/tools/inspector.py`
`mcp/` only after Python tools stabilize.

Tables:
Optional `tool_runs` table:
`tool_run_id`, `tool_name`, `args_json`, `result_json`, `started_at`,
`finished_at`, `status`.

Current modules concerned:
Existing layer functions in `src/layer_registry.py` are adapted into
`src/module_registry.py`, which is the current seed of the shared module
contract. `src/mcp_tools.py` exposes stable read-only/validation tool handlers.

Dependencies:
Core tool handlers have no MCP runtime dependency. The optional server uses the
Python MCP SDK when installed.

Candidate MCP servers:
Corpus/Git MCP for listing universes, collections, manifests, summaries, and
source files.
Storage MCP for asset metadata and attachments.
Retrieval MCP for chunk search and source lookup.
KG MCP for entity search, relation listing, assertion checks, and text
validation.
Lore Memory MCP for pending/validated/rejected memory workflows.
Inspector MCP for test runs, reports, scores, and regression checks.

Risks:
Building MCP too early, exposing unsafe write tools, unclear auth boundaries,
tool schemas changing too often.

Implementation order:
Create internal Python tools. Add tests. Freeze schemas. Then wrap selected
tools with MCP.

Current status:
First MCP-ready tools exist for universe listing, document reading, corpus
search, entity lookup, relation lookup, assertion validation, generated-output
validation, and tool contract discovery. The optional MCP server is
intentionally thin and read-only/validation-only.

## Layer 9: Generation And Fine-Tuning

Role:
Generate lore, translations, images, audio, and structured artifacts while
respecting evidence and validation constraints.

Responsibilities:
Manage provider-backed generation, local model fallback, prompt templates,
model configuration, output parsing, LoRA/fine-tuning experiments, and dataset
creation from validated memory.

Data in:
User request, retrieved context, KG constraints, memory records, model config,
prompt templates.

Data out:
Generated text, structured JSON, images, audio, validation candidates, training
examples.

Formats:
Text/Markdown, JSON, image/audio files, dataset JSONL for fine-tuning.

Folders/files to create:
`src/generation/`
`prompts/`
`datasets/fine_tuning/`
`outputs/generated/`

Tables:
Optional `generation_runs` table:
`run_id`, `universe_id`, `provider`, `model`, `prompt_template`,
`input_json`, `output_path`, `created_at`, `validation_status`.

Current modules concerned:
`src/lore_generator.py`
`src/lore_generator_p4.py`
`src/lore_generator_generic.py`
`src/llm_provider.py`
`src/prompt_templates.py`
`src/training_datasets.py`
`src/translator.py`
`src/settings.py`

Dependencies:
Anthropic, Groq, OpenAI API, OpenAI-compatible local endpoints such as LM
Studio or Ollama, future image/audio model dependencies.

Risks:
API cost, model drift, invalid model IDs, prompt fragility, generating more data
than can be validated, premature fine-tuning without clean data.

Implementation order:
Unify provider calls behind a generation interface. Use stronger models for
long generation and difficult validation, local/small models for routing,
drafts, reformulation, and simple tasks, and fast low-cost APIs for short
answers when appropriate. Improve trace capture. Collect validated examples.
Only then create fine-tuning datasets.

Current status:
A provider-neutral `LLMProvider` interface exists for Groq, Anthropic, OpenAI,
OpenAI-compatible local endpoints, Ollama aliases, and static offline tests.
Fine-tuning is explicitly deferred. `src/training_datasets.py` can export
versioned dataset manifests from validated reusable memory only; when no
validated examples exist, dataset status is `blocked_no_validated_examples`.
Generation can be wrapped with a trace object containing provider, model,
duration, usage, estimated cost when price data is known, and clean error text.

## Layer 10: Validation, Safety, And Governance

Role:
Keep the system trustworthy.

Responsibilities:
Run sanity checks, unit tests, KG validation, source citation checks, secret
scans, memory approval, error reporting, and governance rules for write actions.

Data in:
Generated outputs, retrieval traces, KG validation results, environment config,
test runs.

Data out:
Validation reports, warnings, blocked writes, test results, governance logs.

Formats:
Console output, JSON reports, Markdown reports, SQLite inspector DB.

Folders/files to create:
`reports/validation/`
`governance/policies.md`
`governance/checklists/`

Tables:
Current inspector uses SQLite runtime data.
Future `validation_runs` table:
`validation_id`, `target_type`, `target_id`, `validator`, `score`, `status`,
`violations_json`, `created_at`.

Validation statuses:
`validated`, `attention`, `rejected`, `needs_human_review`,
`hard_contradiction`, `soft_contradiction`, `missing_data`.

Current modules concerned:
`scripts/sanity_check.py`
`tests/`
`inspector/`
`src/knowledge_graph.py`
`src/output_validation.py`
`src/settings.py`
`.env.example`
`Makefile`

Dependencies:
pytest, unittest, SQLite, optional provider APIs for inspector judging.

Risks:
False confidence from shallow tests, provider-key failures, accidental secret
commits, accepting memory without human review.

Implementation order:
Keep `make sanity` and `make test` mandatory. Add validation reports before
automatic memory writes. Add stronger secret scanning before public releases.

Current status:
Generated-output validation combines retrieved source coverage, explicit source
citations, KG checks, validated-memory awareness, deterministic constraints,
and lightweight style checks. Reports distinguish canon-supported claims,
uncited supported claims, extrapolations, and unsupported inventions. Outputs
that need source citation, human review, KG attention, constraint fixes, or
style correction are marked explicitly instead of being silently accepted.

Governance policy:
Broad read access is acceptable. Write access must be limited by tool,
permission, and target. Canonization is never automatic. History should be
append-only where possible. Canon, generated content, pending memory, rejected
items, and fanon must remain separate.

## Target Directory Map

Current directories remain valid during migration:
`data/`, `vector_db/`, `src/`, `scripts/`, `tests/`, `inspector/`.

Target directories to add gradually:

```text
corpus/
  universes/<universe_id>/
    manifest.json
    SUMMARY.md
    canon/
    notes/
    assets/
    validated_memory/

storage/
  raw/<universe_id>/
  processed/<universe_id>/
  manifests/
  cache/

indexes/
  <universe_id>/
    text/
    image/
    audio/

kg/
  <universe_id>/

memory/
  <universe_id>/

prompts/
datasets/
outputs/
governance/
reports/
```

## Implementation Roadmap

Phase 3A: Specification and contracts.
Complete this document, define the universe manifest shape, and document the
current KG schema.

Phase 3B: Corpus structure.
Create `corpus/` and migrate one universe without breaking existing `data/`
paths.

Phase 3C: Tool contracts.
Extract stable Python tool functions from retrieval, KG validation, generation,
and memory candidates.

Phase 3D: Normal Mode and Lab Mode cleanup.
Make both modes use the same module/tool registry and trace objects.

Phase 3E: Validated memory.
Add memory statuses and manual approval. Do not auto-promote generated lore.

Phase 3F: Multimodal ingestion.
Add image/audio/video progressively. Current scope supports image/audio
metadata contracts and planned derivatives only. Model-backed OCR, image
captioning, audio transcription, and multimodal embeddings are deferred.

Phase 3G: MCP.
Wrap stable internal tools as MCP servers.

Phase 3H: Fine-tuning and LoRA.
Start only after enough validated examples exist.

## Reference Ideal Flow

1. User submits a request.
2. Router detects the universe, task type, and mode.
3. Agent reads the relevant manifest and `SUMMARY.md` files before loading
   detailed chunks.
4. Agent calls retrieval, KG, memory, and source tools as needed.
5. Generator receives relevant excerpts, KG constraints, timeline constraints,
   style rules, and the user request.
6. Model generates a draft.
7. Validator checks KG contradictions, source sufficiency, entity coherence,
   hard/soft rules, timeline, and style constraints.
8. If problems exist, the system returns warnings or asks for regeneration.
9. If acceptable, the system returns a final answer with sources.
10. If the user validates the output, it enters lore memory as `pending`.
11. After review, it may become `validated` memory and be available for future
    generation.

## Validation Commands

Run before committing architecture changes:

```bash
make sanity
make test
git diff --check
```
