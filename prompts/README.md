# Prompts

Shared prompt templates will live here once generation is consolidated.

The current prompt code still lives in `src/prompt_templates.py` and generator
modules.
# Prompt Assets

This folder contains RAGElven-specific prompt and agent profile contracts.

These files are not copied runtime infrastructure from the AI template.
They are adapted lightweight contracts.

Current files:

- `agent_profiles.json`: tool-scoped assistant profiles.
- `workflow_templates.json`: review, verification, and context-refresh prompts.

Rules:

- profiles must map to real RAGElven tools;
- generated lore is never canon by default;
- templates guide review behavior, not autonomous writes;
- keep prompts small enough to load selectively.
