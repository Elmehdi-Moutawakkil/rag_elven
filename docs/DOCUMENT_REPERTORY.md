# RAGElven Document Repertory

Status: Phase 1 audit document.
Date: 2026-06-28.

This file inventories the documents and data sources currently present in the
project, with emphasis on what is actually used by retrieval.

## Active Retrieval Corpora

### Tolkien / Elvish Runtime Corpus

Current indexed source:

- `data/quenya_course/Quenya-Elvish-Language-Course-Tolkien.pdf`

Runtime artifacts:

- `vector_db/faiss.index`
- `vector_db/metadata.json`
- `vector_db/dictionary.sqlite`
- `vector_db/knowledge_graph.sqlite`

Observed state:

- `vector_db/metadata.json` contains 1490 chunks.
- All indexed FAISS metadata currently points to the Quenya course PDF.
- The source PDFs `data/quenya_dictionary/quen-eng.pdf` and
  `data/sindarin/sindarin-english.pdf` exist, but the active FAISS metadata does
  not show them as indexed text sources.
- Dictionary lookup uses SQLite, not direct PDF retrieval.

Action needed:

- Decide whether Tolkien/Elvish remains a first-class corpus or becomes a demo
  universe.
- Document how `dictionary.sqlite` was produced.
- Decide whether the dictionary PDFs should be ingested, archived, or treated
  as raw source references only.

### Terran Empire Runtime Corpus

Current source files:

- `data/universes/terran_empire/lore/history_and_origins.txt`
- `data/universes/terran_empire/lore/key_figures.txt`
- `data/universes/terran_empire/lore/mirror_universe_crossover_events.txt`
- `data/universes/terran_empire/lore/political_structure.txt`
- `data/universes/terran_empire/lore/technology_and_fleet.txt`
- `data/universes/terran_empire/lore/terok_nor_and_rebellion.txt`
- `data/universes/terran_empire/lore/the_alliance_and_fall.txt`

Corpus contract:

- `corpus/universes/terran_empire/manifest.json`
- `corpus/universes/terran_empire/SUMMARY.md`

Processed artifacts:

- `storage/processed/terran_empire/documents.jsonl`
- `storage/processed/terran_empire/ingestion_report.json`
- `indexes/terran_empire/text/chunks.jsonl`
- `indexes/terran_empire/text/manifest.json`
- `vector_db/terran_empire/faiss.index`
- `vector_db/terran_empire/metadata.json`
- `vector_db/terran_empire/knowledge_graph.sqlite`

Observed state:

- `storage/processed/terran_empire/documents.jsonl` contains 7 normalized
  documents.
- `indexes/terran_empire/text/chunks.jsonl` contains 90 normalized text chunks.
- `vector_db/terran_empire/metadata.json` contains 128 FAISS metadata chunks.
- Terran retrieval is now available through `src.retrieval_adapter.retrieve_evidence`.

Action needed:

- Make Terran the reference pilot corpus for the new architecture.
- Decide whether old `vector_db/terran_empire/metadata.json` should remain a
  runtime artifact or be rebuilt from `indexes/terran_empire/text/chunks.jsonl`.
- Add a small retrieval evaluation set for Terran.

## Present But Not Clearly Active

These files exist but should be reviewed before they are treated as canonical
inputs:

- `data/lore/first_age_wars.txt`
- `data/lore/languages_overview.txt`
- `data/lore/maiar_sauron.txt`
- `data/lore/valar_morgoth.txt`

Observed state:

- They are source-like Tolkien lore files.
- They do not appear in `vector_db/metadata.json`, which currently points only
  to the Quenya course PDF.

Action needed:

- Decide whether these files are still useful.
- If useful, migrate them into a proper Tolkien universe manifest.
- If obsolete, archive them under a clear historical folder.

## Project Planning Documents

Active:

- `TECHNICAL_SPEC_RAGELVEN.md`
- `README.md`

Needs decision:

- `PIPELINE1.md`

Archived:

- `docs/archive/AI_IMAGE_INTEGRATION_CONTEXT.md`
- `docs/archive/EXECUTION_PLAN.md`
- `docs/archive/ÉTAT_DES_LIEUX.md`
- `docs/archive/PHASE2_PLAN.md`
- `docs/archive/PRODUCT_SPEC.md`
- `docs/archive/README.md`
- `docs/archive/TECHNICAL_SPEC.md`

Observed state:

- `TECHNICAL_SPEC_RAGELVEN.md` is the active architecture contract.
- `PIPELINE1.md` is useful as a roadmap, but it is currently untracked and can
  conflict with the active spec if left ambiguous.

Action needed:

- Either version `PIPELINE1.md` as the active roadmap and align it with
  `TECHNICAL_SPEC_RAGELVEN.md`, or move it into `docs/archive/`.

## Operational Documentation

Current docs:

- `corpus/README.md`
- `indexes/README.md`
- `mcp/README.md`
- `memory/README.md`
- `prompts/README.md`
- `reports/README.md`
- `storage/README.md`
- `governance/policies.md`
- `reports/template_integration.md`
- `prompts/agent_profiles.json`

Action needed:

- Review these after the retrieval and roadmap cleanup.
- Keep docs short and tied to actual commands or contracts.

## Known Routing Issue

Terran-specific retrieval is fixed when callers pass:

- `universe_id="terran_empire"`

Working paths:

- Terran Q&A tab.
- Lab Mode with Terran selected.
- MCP/search tools using `terran_empire`.
- Agent planner using `terran_empire`.

Still at risk:

- Main Normal Mode currently hardcodes Tolkien resources and
  `universe_id="tolkien"`.
- A Star Trek question entered in the main input can still route through the
  Tolkien/Elvish pipeline unless universe detection is added.

Required fix:

- Add universe detection or a user-visible universe selector to Normal Mode.
- Disable Tolkien-only modules (`L03`, `L04`, `L05`, `L06`) when the selected
  universe is not Tolkien/Elvish.
