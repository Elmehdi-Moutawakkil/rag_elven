# RAGElven

RAGElven is an open-source AI lore platform experiment.

The goal is to build a modular system where fictional universes can be stored,
searched, validated, extended, and generated from a versioned canon repository.
The long-term target is not just a chatbot: it is a lore-aware workspace with
Normal Mode for everyday use and Lab Mode for composing, testing, and replacing
individual modules.

## Current State

The app currently includes:

- RAG Q&A over local FAISS indexes and SQLite data;
- deterministic Quenya translation layers;
- lore generation;
- local Knowledge Graph validation;
- an experimental Lab Mode with composable layers;
- manifest-driven ingestion and text chunk indexes;
- hybrid retrieval over normalized chunks;
- validated-memory primitives;
- provider-neutral LLM interface;
- controlled agent runner and MCP-ready read tools;
- basic sanity and regression checks.

## Run Locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

make sanity
make test
make ingest-terran
make index-terran
make run
```

API keys are optional for local validation, but required for provider-backed
generation and Q&A:

```bash
cp .env.example .env
```

Never commit real API keys.

## Architecture

The active technical direction is documented in:

[`TECHNICAL_SPEC_RAGELVEN.md`](TECHNICAL_SPEC_RAGELVEN.md)

Archived documents from earlier MVP phases are stored in:

[`docs/archive/`](docs/archive/)
