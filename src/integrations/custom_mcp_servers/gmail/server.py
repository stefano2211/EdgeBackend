"""Gmail MCP server — custom FastMCP implementation.

Exposes 4 tools:
  - send_email
  - list_emails
  - get_email
  - delete_email

Authentication: OAuth2 refresh token (env vars injected by Docker).
Transport: streamable-http (SSE-compatible) on port 8080.
"""

from __future__ import annotations

import logging
import os

from mcp.server.fastmcp import FastMCP

from src.integrations.custom_mcp_servers.gmail.client import GmailClient
from src.integrations.custom_mcp_servers.gmail.tools import register_tools

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def create_server() -> FastMCP:
    """Factory: build and configure the Gmail MCP server."""
    mcp = FastMCP("gmail", json_response=True)
    register_tools(mcp)
    return mcp


if __name__ == "__main__":
    # Validate env before starting
    required = ["GMAIL_REFRESH_TOKEN", "GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        logger.error("Missing required environment variables: %s", missing)
        raise SystemExit(1)

    server = create_server()
    logger.info("Gmail MCP server starting on port 8080")
    server.run(transport="streamable-http")
