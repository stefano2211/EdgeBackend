"""Gmail MCP tool definitions.

Registers Gmail tools on a FastMCP instance.  Each tool is a thin wrapper
around GmailClient methods, using the module-level singleton so credentials
and the API service object are cached across calls.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from src.integrations.custom_mcp_servers.gmail.client import get_client


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
        return get_client().send_email(to, subject, body, html)

    @mcp.tool()
    def list_emails(query: str = "", max_results: int = 10) -> dict:
        """List recent emails matching a Gmail search query.

        Args:
            query: Gmail search query (e.g. 'from:alice@gmail.com is:unread').
            max_results: Maximum number of messages to return (1-100).
        """
        return get_client().list_emails(query, max_results)

    @mcp.tool()
    def get_email(email_id: str) -> dict:
        """Retrieve the full content of a specific email.

        Args:
            email_id: The Gmail message ID (returned by list_emails).
        """
        return get_client().get_email(email_id)

    @mcp.tool()
    def delete_email(email_id: str) -> dict:
        """Move an email to the Gmail trash.

        Args:
            email_id: The Gmail message ID to delete.
        """
        return get_client().delete_email(email_id)

    @mcp.tool()
    def reply_to_email(email_id: str, body: str, html: bool = False) -> dict:
        """Reply to an existing email thread.

        Args:
            email_id: The Gmail message ID to reply to.
            body: Reply content (plain text or HTML).
            html: Set to True if body contains HTML markup.
        """
        return get_client().reply_to_email(email_id, body, html)

    @mcp.tool()
    def create_draft(to: str, subject: str, body: str, html: bool = False, reply_to: str | None = None) -> dict:
        """Create a draft email (does not send).

        Args:
            to: Recipient email address.
            subject: Email subject line.
            body: Plain text or HTML content.
            html: Set to True if body contains HTML markup.
            reply_to: Optional message ID to reply to.
        """
        return get_client().create_draft(to, subject, body, html, reply_to)

    @mcp.tool()
    def list_drafts(max_results: int = 10) -> dict:
        """List draft emails.

        Args:
            max_results: Maximum number of drafts to return.
        """
        return get_client().list_drafts(max_results)

    @mcp.tool()
    def send_draft(draft_id: str) -> dict:
        """Send an existing draft.

        Args:
            draft_id: The draft ID to send.
        """
        return get_client().send_draft(draft_id)

    @mcp.tool()
    def list_labels() -> dict:
        """List all Gmail labels (system and user-created)."""
        return get_client().list_labels()

    @mcp.tool()
    def modify_labels(email_id: str, add_labels: list[str] | None = None, remove_labels: list[str] | None = None) -> dict:
        """Add or remove labels from an email.

        Args:
            email_id: The Gmail message ID.
            add_labels: List of label IDs to add (e.g. ['STARRED', 'IMPORTANT']).
            remove_labels: List of label IDs to remove (e.g. ['INBOX', 'UNREAD']).
        """
        return get_client().modify_labels(email_id, add_labels, remove_labels)
