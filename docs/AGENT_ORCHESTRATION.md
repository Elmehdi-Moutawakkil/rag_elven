# Agent Orchestration

Status: Step 14 foundation.

## Current Scope

RAGElven has a controlled agent layer.

It is not a fully autonomous agent.

It can:

- inspect the user request;
- build an explicit plan;
- use a small tool registry;
- retrieve sources;
- optionally generate with an `LLMProvider`;
- validate the output;
- expose an auditable trace;
- block risky requests pending human confirmation.

## Tool Policy

Allowed runtime tools are declared in `src/agent/planner.py`.

Current tools:

- `retrieve`;
- `kg_validate`;
- `generate`;
- `validate_output`;
- `request_confirmation`;
- `expose_trace`.

Each tool declares:

- purpose;
- risk level;
- read-only status;
- confirmation requirement.

## Risk Policy

The agent blocks before execution when the request appears to involve:

- writes;
- deletion;
- canonization;
- memory validation;
- publishing;
- commit or push;
- irreversible archive actions.

Blocked runs return:

- `status = blocked_pending_confirmation`;
- `human_review_required = true`;
- trace event `request_confirmation`.

## Design Choice

Priority is traceability over autonomy.

The agent should remain boring and inspectable until the underlying tools,
logs, validation, and UI confirmation flows are stronger.

## Deferred

Not implemented yet:

- persistent `agent_runs` table;
- UI confirmation flow;
- durable budget/run telemetry;
- autonomous multi-step write tools;
- self-approval of generated lore or memory.
