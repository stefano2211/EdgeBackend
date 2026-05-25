"""Maquinaria MCP server — custom FastMCP implementation.

Exposes tools:
  - get_machinery_metrics
  - list_equipment_status

Authentication: none (apiEjemplo is open on localhost:7000).
Transport: stdio.
"""

from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

from .tools import register_tools

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def create_server() -> FastMCP:
    """Factory: build and configure the Maquinaria MCP server."""
    mcp = FastMCP("maquinaria", json_response=True)
    register_tools(mcp)
    return mcp


if __name__ == "__main__":
    server = create_server()
    logger.info("Maquinaria MCP server starting on stdio")
    server.run(transport="stdio")
