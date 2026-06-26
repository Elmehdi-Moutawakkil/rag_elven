"""Optional MCP server for RAGElven tools.

Install the `mcp` Python package to run this server. The core tool handlers
live in `src.mcp_tools` and are tested without requiring MCP as a dependency.
"""

from __future__ import annotations

from src.mcp_tools import (
    get_entity_tool,
    list_entities_tool,
    list_relations_tool,
    list_universes,
    read_document,
    search_corpus_tool,
    validate_assertion_tool,
)


try:
    from mcp.server.fastmcp import FastMCP
except ModuleNotFoundError as exc:  # pragma: no cover - depends on optional package
    raise SystemExit(
        "The optional `mcp` package is not installed. "
        "Install it to run `python -m mcp.ragelven_server`."
    ) from exc


mcp = FastMCP("ragelven")


@mcp.tool()
def list_universes_tool() -> dict:
    return list_universes()


@mcp.tool()
def read_document_tool(universe_id: str = "terran_empire", document_id: str | None = None, source_path: str | None = None) -> dict:
    return read_document(universe_id=universe_id, document_id=document_id, source_path=source_path)


@mcp.tool()
def search_corpus_mcp(query: str, universe_id: str = "terran_empire", k: int = 5) -> dict:
    return search_corpus_tool(query=query, universe_id=universe_id, k=k)


@mcp.tool()
def list_entities_mcp(universe_id: str = "terran_empire", entity_type: str | None = None) -> dict:
    return list_entities_tool(universe_id=universe_id, entity_type=entity_type)


@mcp.tool()
def get_entity_mcp(name: str, universe_id: str = "terran_empire") -> dict:
    return get_entity_tool(name=name, universe_id=universe_id)


@mcp.tool()
def list_relations_mcp(entity_name: str, universe_id: str = "terran_empire", relation_type: str | None = None) -> dict:
    return list_relations_tool(entity_name=entity_name, universe_id=universe_id, relation_type=relation_type)


@mcp.tool()
def validate_assertion_mcp(assertion: str, universe_id: str = "terran_empire") -> dict:
    return validate_assertion_tool(assertion=assertion, universe_id=universe_id)


if __name__ == "__main__":  # pragma: no cover - manual MCP runtime
    mcp.run()
