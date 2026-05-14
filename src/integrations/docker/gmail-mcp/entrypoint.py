"""Gmail MCP server entrypoint for Docker container."""

from __future__ import annotations

import logging
import os
import sys

# Ensure /app is on path
sys.path.insert(0, "/app")

from gmail.server import create_server

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def main() -> None:
    required = ["GMAIL_REFRESH_TOKEN", "GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        logger.error("Missing required environment variables: %s", missing)
        sys.exit(1)

    server = create_server()
    logger.info("Gmail MCP server starting on 0.0.0.0:8080")
    server.run(transport="streamable-http")


if __name__ == "__main__":
    main()
