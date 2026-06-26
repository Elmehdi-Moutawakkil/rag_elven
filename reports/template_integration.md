# AI Template Integration Report

Status: selective integration for RAGElven.

The template should not be copied wholesale into RAGElven. Its `.aip`
infrastructure is a development workflow framework, while RAGElven is an
application for lore retrieval, validation, memory, generation, and future MCP
tools.

## Integrate Now

- Contract-first task style: every new layer should expose inputs, outputs,
  status, errors, and tests.
- Quality gate habit: `make sanity`, `make test`, and `git diff --check` remain
  the local baseline.
- Review personas: adapt only the useful roles as app-level agent profiles:
  retrieval, validation, generation, security, and architecture.
- Progressive disclosure: keep `README.md` and `TECHNICAL_SPEC_RAGELVEN.md` as
  the active map; avoid many competing planning documents.
- MCP-after-contracts principle: MCP tools wrap stable Python functions; they
  do not replace internal modules.

## Adapt Later

- Event bus and task tracking: useful for a future contributor workflow, but too
  heavy for the runtime app right now.
- Memory database ideas: useful inspiration, but RAGElven memory must stay
  lore-domain specific with canon/review statuses.
- Multi-agent coordination: useful for open-source maintainers later, not
  needed in the app runtime yet.
- Skills library: useful as prompt/workflow examples, but should not be imported
  as runtime code.

## Ignore

- Full `.aip` bootstrap system.
- Shell-first task database.
- Generated Claude/Codex config mirrors.
- Template-specific project state machine.
- Decorative agent personalities that do not map to real tools or validation.

## RAGElven-Specific Transfer

The useful transfer is a small set of operational profiles, stored in
`prompts/agent_profiles.json`. They describe how an agent should behave when
calling RAGElven tools, without importing the template infrastructure.
