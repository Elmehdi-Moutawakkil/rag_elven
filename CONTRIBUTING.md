# Contributing

Status: early project guidance.

RAGElven is not ready for broad public contribution yet. This file exists so
the future open-source release has clear defaults.

## Before A Change

- Read `README.md`.
- Read `docs/PIPELINE1_STATUS.md`.
- Read the relevant section of `TECHNICAL_SPEC_RAGELVEN.md`.
- Keep corpus, KG, memory, generation, and validation boundaries separate.

## Development Checks

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

make sanity
make test
python scripts/open_source_audit.py
```

## Contribution Rules

- Do not commit real API keys.
- Do not auto-promote generated lore to canon.
- Do not add write MCP tools without explicit review and rollback rules.
- Do not add private or unclear-license corpus files.
- Keep tests focused on changed behavior.
- Update docs when module contracts change.

## Data And Corpus

Before public release, every tracked corpus or index asset must have a clear
license and redistribution decision.

When in doubt, add a small example corpus instead of real/private data.
