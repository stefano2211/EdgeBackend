"""Gmail API client with OAuth2 refresh-token flow.

Reads credentials from environment variables (injected by Docker).
Automatically refreshes access tokens on every request.
"""

from __future__ import annotations

import base64
import logging
import os
from email.message import EmailMessage

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)


class GmailClient:
    """Low-level Gmail API wrapper."""

    SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

    def __init__(self, refresh_token: str, client_id: str, client_secret: str) -> None:
        self.refresh_token = refresh_token
        self.client_id = client_id
        self.client_secret = client_secret
        self._service = None

    @classmethod
    def from_env(cls) -> "GmailClient":
        """Factory that reads configuration from environment variables."""
        return cls(
            refresh_token=os.environ["GMAIL_REFRESH_TOKEN"],
            client_id=os.environ["GMAIL_CLIENT_ID"],
            client_secret=os.environ["GMAIL_CLIENT_SECRET"],
        )

    def _get_service(self):
        """Lazy-initialise and cache the Gmail API service object."""
        if self._service is not None:
            return self._service

        creds = Credentials(
            None,
            refresh_token=self.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=self.SCOPES,
        )
        creds.refresh(Request())
        self._service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        return self._service

    # ------------------------------------------------------------------
    # Send
    # ------------------------------------------------------------------

    def send_email(self, to: str, subject: str, body: str, html: bool = False) -> dict:
        """Send an email. Returns dict with threadId and messageId."""
        try:
            message = EmailMessage()
            message["To"] = to
            message["Subject"] = subject
            if html:
                message.add_alternative(body, subtype="html")
            else:
                message.set_content(body)

            encoded = base64.urlsafe_b64encode(message.as_bytes()).decode()
            payload = {"raw": encoded}

            result = (
                self._get_service()
                .users()
                .messages()
                .send(userId="me", body=payload)
                .execute()
            )
            return {
                "success": True,
                "message_id": result.get("id"),
                "thread_id": result.get("threadId"),
            }
        except HttpError as exc:
            logger.exception("Gmail send_email failed")
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    def list_emails(self, query: str = "", max_results: int = 10) -> dict:
        """List emails matching a Gmail search query."""
        try:
            result = (
                self._get_service()
                .users()
                .messages()
                .list(userId="me", q=query, maxResults=max_results)
                .execute()
            )
            messages = result.get("messages", [])
            return {
                "success": True,
                "count": len(messages),
                "messages": [
                    {"id": m["id"], "thread_id": m.get("threadId")} for m in messages
                ],
            }
        except HttpError as exc:
            logger.exception("Gmail list_emails failed")
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Get
    # ------------------------------------------------------------------

    def get_email(self, email_id: str) -> dict:
        """Fetch full email content by message ID."""
        try:
            result = (
                self._get_service()
                .users()
                .messages()
                .get(userId="me", id=email_id, format="full")
                .execute()
            )

            payload = result.get("payload", {})
            headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}

            # Extract body (prefer text/plain, fallback to text/html)
            body_text = ""
            parts = payload.get("parts", [payload])
            for part in parts:
                mime = part.get("mimeType", "")
                data = part.get("body", {}).get("data", "")
                if data and mime == "text/plain":
                    body_text = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                    break
                elif data and mime == "text/html" and not body_text:
                    body_text = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

            return {
                "success": True,
                "id": result.get("id"),
                "thread_id": result.get("threadId"),
                "subject": headers.get("subject", ""),
                "from": headers.get("from", ""),
                "to": headers.get("to", ""),
                "date": headers.get("date", ""),
                "snippet": result.get("snippet", ""),
                "body": body_text,
            }
        except HttpError as exc:
            logger.exception("Gmail get_email failed")
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete_email(self, email_id: str) -> dict:
        """Move email to trash (soft delete)."""
        try:
            self._get_service().users().messages().trash(userId="me", id=email_id).execute()
            return {"success": True, "message_id": email_id, "action": "trashed"}
        except HttpError as exc:
            logger.exception("Gmail delete_email failed")
            return {"success": False, "error": str(exc)}
