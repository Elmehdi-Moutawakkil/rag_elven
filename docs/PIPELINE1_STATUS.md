# PIPELINE1 Status

Date: 2026-06-28.

Source roadmap: `PIPELINE1.md`.

## Current Position

Active position: Step 10 next.

Reason:

- Steps 1 to 7 have usable project artifacts.
- Step 8 retrieval exists, is wired, and has a Terran evaluation set.
- Step 9 KG exists, has schema documentation, source-file provenance, exports, and regression tests.
- Steps 10 to 16 exist as prototypes or backend slices, not finished product layers.
- Steps 17 and 18 are not mature enough to call done.

## Step Status

| Step | Topic | Status | Evidence | Next action |
|---:|---|---|---|---|
| 1 | Audit | Done | `docs/DOCUMENT_REPERTORY.md`, tests, sanity check | Keep updated during changes |
| 2 | Cleanup/security | Partial | corpus cleanup, `.env` ignored, settings centralized | Add secret scan before release |
| 3 | Module stabilization | Mostly done | `tests/`, `src/module_registry.py`, `src/layer_registry.py` | Add module status matrix if needed |
| 4 | Target architecture | Done | `TECHNICAL_SPEC_RAGELVEN.md` | Keep spec current |
| 5 | Modular core | Done enough | `src/module_registry.py`, `src/pipeline_executor.py` | Harden error contracts |
| 6 | Normal/Lab modes | Partial | `src/normal_mode.py`, shared registry | Improve UI trace consistency |
| 7 | Document ingestion | Done for text/Markdown | `src/ingestion/`, `storage/processed/terran_empire/` | Add PDF ingestion later |
| 8 | Indexing/retrieval | Done for current scope | `src/retrieval_adapter.py`, `indexes/terran_empire/`, `evals/retrieval/terran_empire.jsonl` | Add larger evals later |
| 9 | Knowledge Graph | Done for current scope | `src/knowledge_graph.py`, `src/kg_tools.py`, `docs/KNOWLEDGE_GRAPH.md`, `kg/*/export.json` | Add source spans later |
| 10 | Validated memory | Partial | `src/memory_store.py`, tests | Connect to UI and agent flow |
| 11 | AI generation | Partial | `src/llm_provider.py`, lore generators | Improve cost/log traces |
| 12 | Output validation | Partial | `src/output_validation.py`, tests | Add source-coverage thresholds |
| 13 | Multimodal | Scaffold only | `src/multimodal.py`, docs | Do not expand before text is solid |
| 14 | AI agents | Prototype | `src/agent/planner.py`, `.codex/agents.json` | Keep controlled, tool-limited |
| 15 | Template integration | Partial | `reports/template_integration.md`, `.codex/` | Import only useful workflow pieces |
| 16 | MCP | Prototype | `mcp/ragelven_server.py`, `src/mcp_tools.py` | Keep read-only until contracts harden |
| 17 | Fine-tuning/LoRA | Not started | No dataset baseline | Wait for validated memory |
| 18 | Open source/governance | Partial | README, `.env.example`, governance docs | Add CI, license check, contribution docs |

## Immediate Roadmap

1. Harden Step 10 memory integration.
2. Delay multimodal, broad agents, MCP expansion, and fine-tuning until retrieval/KG/memory are stronger.
