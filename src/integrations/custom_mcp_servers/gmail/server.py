"""Gmail MCP server — custom FastMCP implementation.

Exposes tools:
  - send_email
  - list_emails
  - get_email
  - delete_email
  - reply_to_email
  - create_draft
  - list_drafts
  - send_draft
  - list_labels
  - modify_labels

Authentication: OAuth2 refresh token (env vars injected by Docker).
Transport: SSE on port 8080.
"""

from __future__ import annotations

import logging
import os

from mcp.server.fastmcp import FastMCP

from .client import GmailClient
from .tools import register_tools

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
    logger.info("Gmail MCP server starting on 0.0.0.0:8080")
    server.run(transport="sse", host="0.0.0.0", port=8080)
