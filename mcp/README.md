# RAGElven MCP

This folder contains a thin optional MCP server around stable internal
RAGElven tools.

Current tools are read-only or validation-only:

- `list_tools`
- `list_universes`
- `read_document`
- `search_corpus`
- `list_entities`
- `get_entity`
- `list_relations`
- `validate_assertion`
- `validate_generated_output`

The server is intentionally thin. It calls `src.mcp_tools`, which calls the
same retrieval, KG, and validation functions used by the app. Do not add write
tools for canon or memory until permissions and review rules are explicit.

Run manually after installing the optional MCP Python package:

```bash
python -m mcp.ragelven_server
```

## Tool Contracts

The canonical tool registry lives in `src/mcp_tools.py`.

Each public tool declares:

- category;
- arguments;
- read-only status;
- side-effect status;
- stability.

Use `list_tools` before calling other tools from an external agent.

## Current Boundary

Allowed:

- corpus search;
- processed document reading;
- KG entity lookup;
- KG relation lookup;
- assertion validation;
- generated-output validation.

Not allowed yet:

- writing canon;
- adding validated memory;
- generating lore through MCP;
- changing indexes;
- running paid model calls.
