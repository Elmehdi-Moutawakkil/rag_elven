# RAGElven

RAGElven is a local-first experimental AI lore workspace.

It explores how fictional universes can be ingested, searched, validated,
extended, and generated from versioned sources. The project is not just a
chatbot prototype: it is a modular RAG/KG/lore system with a normal user path
and a lab path for testing individual pipeline layers.

## Status

Current maturity: research prototype with working foundations.

Not ready for public open-source release yet.

Main blockers before publication:

- choose a license;
- review corpus and index redistribution rights;
- separate public sample data from private or unclear-license data;
- add GitHub Actions once the repository token has `workflow` scope;
- finalize public contribution and security processes.

See [`docs/OPEN_SOURCE_READINESS.md`](docs/OPEN_SOURCE_READINESS.md).

## What Works Now

- RAG Q&A over local FAISS indexes and SQLite data.
- Deterministic Quenya translation layers.
- Lore generation over retrieved sources.
- Manifest-driven text/Markdown ingestion.
- Hybrid retrieval over normalized chunks.
- Local Knowledge Graph with source provenance and regression tests.
- Output validation against sources, KG continuity, constraints, and memory.
- Validated memory primitives with draft, validated, rejected, history, and
  rollback semantics.
- Provider-neutral LLM interface with current DeepSeek, OpenAI, Anthropic,
  Groq, Ollama, and LM Studio adapters. DeepSeek is the default Q&A and lore
  provider.
- Multimodal document metadata foundations for image/audio support.
- Controlled agent runner with inspectable plans and risky-action blocking.
- Thin MCP tool wrappers over stable read/validation modules.
- Fine-tuning/LoRA strategy and dataset export foundations, without training.
- Sanity checks and regression tests.

## What Is Still Experimental

- Normal Mode and Lab Mode need better UI trace consistency.
- Retrieval evaluation needs more examples and stricter source-span checks.
- Validated memory is not fully exposed in the user interface.
- Multimodal support is metadata-first; OCR, image captioning, audio
  transcription, and embeddings are planned later.
- MCP write tools remain disabled until permissions, validation, and rollback
  are mature.
- Fine-tuning is intentionally deferred until enough validated examples exist.

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

Set `DEEPSEEK_API_KEY` for the default Q&A and lore paths. `QA_PROVIDER` can
explicitly select `deepseek`, `groq`, `openai`, or `anthropic`; no automatic
fallback occurs. Each selection uses its corresponding API key variable.

Never commit real API keys.

## Key Documentation

- Architecture: [`TECHNICAL_SPEC_RAGELVEN.md`](TECHNICAL_SPEC_RAGELVEN.md)
- Pipeline status: [`docs/PIPELINE1_STATUS.md`](docs/PIPELINE1_STATUS.md)
- Knowledge Graph: [`docs/KNOWLEDGE_GRAPH.md`](docs/KNOWLEDGE_GRAPH.md)
- Multimodal plan: [`docs/MULTIMODAL.md`](docs/MULTIMODAL.md)
- Agent orchestration: [`docs/AGENT_ORCHESTRATION.md`](docs/AGENT_ORCHESTRATION.md)
- MCP tools: [`mcp/README.md`](mcp/README.md)
- Fine-tuning strategy: [`docs/FINE_TUNING_STRATEGY.md`](docs/FINE_TUNING_STRATEGY.md)
- Open-source readiness: [`docs/OPEN_SOURCE_READINESS.md`](docs/OPEN_SOURCE_READINESS.md)
- Archived planning docs: [`docs/archive/`](docs/archive/)
