# RAGElven MCP

This folder contains a thin optional MCP server around stable internal
RAGElven tools.

Current tools are read-only or validation-only:

- `list_universes`
- `read_document`
- `search_corpus`
- `list_entities`
- `get_entity`
- `list_relations`
- `validate_assertion`

The server is intentionally thin. It calls `src.mcp_tools`, which calls the
same retrieval, KG, and validation functions used by the app. Do not add write
tools for canon or memory until permissions and review rules are explicit.

Run manually after installing the optional MCP Python package:

```bash
python -m mcp.ragelven_server
```
