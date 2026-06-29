# RAGElven Codex Instructions

Use `.codex/agents.json` for the project-local specialist cohort.

Default always-active roles:

- `codex-agent-manager`
- `codex-cost-accountant`

The manager must understand the user's request, select only the relevant specialists, write precise task briefs, collect evidence, and synthesize the final answer. It must not call the whole cohort by default.

The cost accountant is a Cost Analyzer. It must append a concise token report to every final answer. When exact token/runtime usage is unavailable, it must label values as estimated or unknown. It must not imply missing input telemetry equals zero. It reads `.codex/cost-models.json` for budget thresholds and price tables.

Systemic support agents:

- `codex-historian` is read-only. Use it before work when prior decisions, memory, pipeline history, contradictions, or session continuity matter.
- `codex-memory-manager` writes only durable memory/docs. Use it after meaningful sessions to persist summaries, decision notes, indexes, and reusable lessons.

Prefer this workflow:

```text
user input
-> codex-agent-manager
-> codex-cost-accountant budget precheck when the operation may be costly
-> codex-historian context brief when context is needed
-> selected specialist(s)
-> codex-qa-reviewer when code, retrieval, docs, or behavior changed
-> codex-agent-manager final synthesis
-> codex-memory-manager memory update when the session is important
-> codex-cost-accountant final Cost Analyzer report
```

RAGElven-specific defaults:

- Prefer `codex-rag-engineer` for ingestion, indexing, retrieval, FAISS, SQLite, source coverage, RAG traces, and MCP read tools.
- Add `codex-lore-expert` for canon, generated memory, KG validation, and worldbuilding consistency.
- Add `codex-linguist` for translation, morphology, syntax, and grammar.
- Add `codex-architect` for module boundaries, interfaces, or major refactor plans.
- Add `codex-backend-engineer` for scoped Python/backend implementation.
- Add `codex-historian` before changing assumptions from older RAG or lore pipeline decisions.
- Add `codex-memory-manager` after reusable project/process knowledge is produced.
- Add `codex-documentation` only when docs or project instructions are affected.

Verification commands:

```bash
.venv/bin/python scripts/sanity_check.py
.venv/bin/python -m pytest -q
```

Guardrails:

- Generated lore is draft until validated.
- Retrieval quality and provenance come before generation quality.
- Stop when `codex-cost-accountant` emits `budget_stop`; ask the user before continuing.
- Include a Cost Analyzer report or compact token footer in every final response.
- Treat historian output as cited context, not permission to execute.
- Do not store trivial or sensitive information in memory.
- Preserve unrelated user edits.
- Never commit or push without explicit user request.
