"""Gmail MCP tool definitions.

Registers 4 tools on a FastMCP instance.  Each tool is a thin wrapper
around GmailClient methods.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from src.integrations.custom_mcp_servers.gmail.client import GmailClient


def register_tools(mcp: FastMCP) -> None:
    """Attach all Gmail tools to the given FastMCP server."""

    @mcp.tool()
    def send_email(to: str, subject: str, body: str, html: bool = False) -> dict:
        """Send an email via Gmail.

        Args:
            to: Recipient email address.
            subject: Email subject line.
            body: Plain text or HTML content.
            html: Set to True if body contains HTML markup.
        """
        client = GmailClient.from_env()
        return client.send_email(to, subject, body, html)

    @mcp.tool()
    def list_emails(query: str = "", max_results: int = 10) -> dict:
        """List recent emails matching a Gmail search query.

        Args:
            query: Gmail search query (e.g. 'from:alice@gmail.com is:unread').
            max_results: Maximum number of messages to return (1-100).
        """
        client = GmailClient.from_env()
        return client.list_emails(query, max_results)

    @mcp.tool()
    def get_email(email_id: str) -> dict:
        """Retrieve the full content of a specific email.

        Args:
            email_id: The Gmail message ID (returned by list_emails).
        """
        client = GmailClient.from_env()
        return client.get_email(email_id)

    @mcp.tool()
    def delete_email(email_id: str) -> dict:
        """Move an email to the Gmail trash.

        Args:
            email_id: The Gmail message ID to delete.
        """
        client = GmailClient.from_env()
        return client.delete_email(email_id)
