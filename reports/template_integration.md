# AI Template Integration Report

Status: Step 15 selective integration.

Source template: `/Volumes/ssd1/ai-project-template`.

Decision: do not import `.aip` as infrastructure. RAGElven is an application
with its own RAG, KG, memory, validation, multimodal, and future MCP layers.
The template is useful as a workflow reference, not as runtime architecture.

## Integrate Now

| Template idea | RAGElven adaptation | Reason |
|---|---|---|
| Contract-first tasks | Keep layer inputs, outputs, status, errors, tests, and docs explicit | Fits the current modular pipeline |
| Quality gate habit | Keep `scripts/sanity_check.py`, full pytest, and `git diff --check` before commits | Useful without adding dependencies |
| Review personas | Keep app-level profiles in `prompts/agent_profiles.json` | Useful only when tied to real tools |
| Verification prompt | Add RAGElven-specific verification templates in `prompts/workflow_templates.json` | Improves review quality without importing `.aip` |
| Cross-review stance | Adapt skeptical review prompts for retrieval, KG, memory, validation, and docs | Catches hallucination and provenance gaps |
| Progressive disclosure | Keep `README.md`, `TECHNICAL_SPEC_RAGELVEN.md`, and `docs/PIPELINE1_STATUS.md` as the active map | Avoids context bloat |
| MCP-after-contracts | MCP tools wrap stable Python functions only | Prevents tool sprawl |

## Adapt Later

| Template idea | Later adaptation | Condition |
|---|---|---|
| Task tracking | Lightweight issue/task docs or GitHub issues | Only when contributors appear |
| Event bus | Runtime audit/event log for agent runs | Only after `agent_runs` exists |
| Memory database | Keep ideas for indexing and health checks | Must preserve lore statuses and canon gates |
| Multi-agent coordination | Reviewer/implementer split for complex PRs | Only after logs and UI confirmation exist |
| Session-per-task | Useful for large refactors | Not needed for current solo pipeline |
| ADR catalog | Add only for major architecture decisions | Avoid docs noise |

## Ignore

| Template idea | Reason |
|---|---|
| Full `.aip` bootstrap | Too heavy for an app repo |
| Shell-first metadata DB | Would duplicate RAGElven's own stores |
| Generated Claude/Codex mirrors | Risk of config drift |
| Template state machine | Not aligned with RAGElven runtime |
| n8n webhook notifications | Operational overhead now |
| Decorative agents | Agents must map to real tools and validation |
| Broad script framework | Too much maintenance surface |

## Applied Transfers

- `prompts/agent_profiles.json` keeps only tool-scoped profiles:
  retrieval archivist, canon validator, lore drafter, governance reviewer.
- `prompts/workflow_templates.json` adds adapted review and verification
  templates.
- `.codex/` keeps specialist configuration, but does not import `.aip`.
- `docs/PIPELINE1_STATUS.md` tracks the selective integration decision.

## Boundary Rules

- RAGElven identity remains primary.
- User/persona identity stays outside the runtime app.
- Generated lore remains draft until validated.
- Template content is an inspiration source, not executable dependency.
- No new abstraction is accepted unless it improves retrieval, validation,
  memory, governance, or documentation.
