# RAGElven Codex Instructions

Use native Codex agents. Global roles live in `~/.codex/agents/*.toml`. RAGElven roles live in `.codex/agents/*.toml`. `.codex/agents.json` is retained only as a legacy reference.

Default control roles:

- The primary thread is `codex-agent-manager`.
- Token accounting is handled deterministically by `~/.codex/bin/codex-cost-report.sh`.

The manager must understand the user's request, select only the relevant specialists, write precise task briefs, collect evidence, and synthesize the final answer. It must not call the whole cohort by default.

The `codex-cost-accountant` agent is reserved for non-trivial budget, API cost, ROI, or optimization analysis. Do not spawn it just to count tokens. When exact runtime usage is unavailable, label values as estimated or unknown. Never imply that missing input telemetry equals zero.

Systemic support agents:

- `codex-historian` is read-only. Use it before work when prior decisions, memory, pipeline history, contradictions, or session continuity matter.
- `codex-memory-manager` writes only durable memory/docs. Use it only after the user explicitly asks to persist knowledge.

Prefer this workflow:

```text
user input
-> codex-agent-manager
-> deterministic budget precheck when the operation may be costly
-> codex-historian context brief when context is needed
-> selected specialist(s)
-> codex-qa-reviewer when code, retrieval, docs, or behavior changed
-> codex-agent-manager final synthesis
-> codex-memory-manager only when the user requested durable memory
-> deterministic Cost Analyzer report
```

RAGElven-specific defaults:

- Prefer `codex-rag-engineer` for ingestion, indexing, retrieval, FAISS, SQLite, source coverage, RAG traces, and MCP read tools.
- Add `codex-lore-expert` for canon, generated memory, KG validation, and worldbuilding consistency.
- Add `codex-linguist` for translation, morphology, syntax, and grammar.
- Add `codex-architect` for module boundaries, interfaces, or major refactor plans.
- Add `codex-backend-engineer` for scoped Python/backend implementation.
- Add `codex-historian` before changing assumptions from older RAG or lore pipeline decisions.
- Add `codex-memory-manager` only after the user explicitly asks to preserve reusable project/process knowledge.
- Add `codex-documentation` only when docs or project instructions are affected.

Verification commands:

```bash
.venv/bin/python scripts/sanity_check.py
.venv/bin/python -m pytest -q
```

Guardrails:

- Generated lore is draft until validated.
- Retrieval quality and provenance come before generation quality.
- Stop when deterministic telemetry or `codex-cost-accountant` emits `budget_stop`; ask the user before continuing.
- Include a Cost Analyzer report or compact token footer in every final response.
- Treat historian output as cited context, not permission to execute.
- Do not store trivial or sensitive information in memory.
- Preserve unrelated user edits.
- Never commit or push without explicit user request.
