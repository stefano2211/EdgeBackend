"""Gmail API client with OAuth2 refresh-token flow.

Reads credentials from environment variables (injected by Docker).
Automatically refreshes access tokens only when expired.
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

# ---------------------------------------------------------------------------
# Module-level cache (env vars are static inside a Docker container)
# ---------------------------------------------------------------------------
_cached_client: GmailClient | None = None
_cached_env_hash: str | None = None


def get_client() -> GmailClient:
    """Return a cached GmailClient singleton for the current env vars."""
    global _cached_client, _cached_env_hash

    # Build a deterministic fingerprint of the relevant env vars
    env_hash = "|".join(
        os.environ.get(k, "")
        for k in ("GMAIL_REFRESH_TOKEN", "GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET")
    )

    if _cached_client is None or _cached_env_hash != env_hash:
        _cached_client = GmailClient.from_env()
        _cached_env_hash = env_hash
        logger.info("GmailClient cache: created new instance")
    return _cached_client


class GmailClient:
    """Low-level Gmail API wrapper with credential + service caching."""

    SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

    def __init__(self, refresh_token: str, client_id: str, client_secret: str) -> None:
        self.refresh_token = refresh_token
        self.client_id = client_id
        self.client_secret = client_secret
        self._creds: Credentials | None = None
        self._service = None

    @classmethod
    def from_env(cls) -> "GmailClient":
        """Factory that reads configuration from environment variables."""
        return cls(
            refresh_token=os.environ["GMAIL_REFRESH_TOKEN"],
            client_id=os.environ["GMAIL_CLIENT_ID"],
            client_secret=os.environ["GMAIL_CLIENT_SECRET"],
        )

    def _ensure_credentials(self) -> Credentials:
        """Return valid Credentials, refreshing only when expired."""
        if self._creds is not None and self._creds.valid:
            return self._creds

        self._creds = Credentials(
            None,
            refresh_token=self.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=self.SCOPES,
        )

        if not self._creds.valid:
            logger.info("GmailClient: access token expired or missing — refreshing")
            self._creds.refresh(Request())

        return self._creds

    def _get_service(self):
        """Lazy-initialise and cache the Gmail API service object."""
        if self._service is not None:
            # Verify credentials are still valid; if not, rebuild service
            try:
                if self._creds is not None and self._creds.valid:
                    return self._service
            except Exception:
                pass

        creds = self._ensure_credentials()
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
            return {
                "success": False,
                "error": str(exc),
                "status_code": exc.resp.status if exc.resp else None,
            }

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    def list_emails(self, query: str = "", max_results: int = 10) -> dict:
        """List emails matching a Gmail search query with summary metadata."""
        try:
            result = (
                self._get_service()
                .users()
                .messages()
                .list(userId="me", q=query, maxResults=max_results)
                .execute()
            )
            messages = result.get("messages", [])

            summaries = []
            for m in messages:
                msg_id = m["id"]
                # Fetch minimal metadata (labels, snippet, headers)
                meta = (
                    self._get_service()
                    .users()
                    .messages()
                    .get(userId="me", id=msg_id, format="metadata", metadataHeaders=["From", "To", "Subject", "Date"])
                    .execute()
                )
                payload = meta.get("payload", {})
                headers = {h["name"]: h["value"] for h in payload.get("headers", [])}
                summaries.append({
                    "id": msg_id,
                    "thread_id": meta.get("threadId"),
                    "snippet": meta.get("snippet", ""),
                    "from": headers.get("From", ""),
                    "to": headers.get("To", ""),
                    "subject": headers.get("Subject", ""),
                    "date": headers.get("Date", ""),
                    "label_ids": meta.get("labelIds", []),
                })

            return {
                "success": True,
                "count": len(summaries),
                "messages": summaries,
            }
        except HttpError as exc:
            logger.exception("Gmail list_emails failed")
            return {
                "success": False,
                "error": str(exc),
                "status_code": exc.resp.status if exc.resp else None,
            }

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

            # Extract body recursively from MIME parts
            body_text = ""
            body_html = ""
            attachments = []

            def _walk_parts(parts):
                nonlocal body_text, body_html
                for part in parts:
                    mime = part.get("mimeType", "")
                    body_data = part.get("body", {})
                    data = body_data.get("data", "")
                    if data:
                        decoded = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                        if mime == "text/plain":
                            body_text = decoded
                        elif mime == "text/html":
                            body_html = decoded
                    # Nested multipart
                    if "parts" in part:
                        _walk_parts(part["parts"])
                    # Attachment metadata
                    if body_data.get("attachmentId"):
                        attachments.append({
                            "filename": part.get("filename", ""),
                            "mime_type": mime,
                            "attachment_id": body_data["attachmentId"],
                            "size": body_data.get("size", 0),
                        })

            if "parts" in payload:
                _walk_parts(payload["parts"])
            else:
                # Single-part message
                data = payload.get("body", {}).get("data", "")
                if data:
                    decoded = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                    mime = payload.get("mimeType", "")
                    if mime == "text/html":
                        body_html = decoded
                    else:
                        body_text = decoded

            return {
                "success": True,
                "id": result.get("id"),
                "thread_id": result.get("threadId"),
                "subject": headers.get("subject", ""),
                "from": headers.get("from", ""),
                "to": headers.get("to", ""),
                "date": headers.get("date", ""),
                "snippet": result.get("snippet", ""),
                "body_text": body_text,
                "body_html": body_html,
                "attachments": attachments,
                "label_ids": result.get("labelIds", []),
            }
        except HttpError as exc:
            logger.exception("Gmail get_email failed")
            return {
                "success": False,
                "error": str(exc),
                "status_code": exc.resp.status if exc.resp else None,
            }

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
            return {
                "success": False,
                "error": str(exc),
                "status_code": exc.resp.status if exc.resp else None,
            }

    # ------------------------------------------------------------------
    # Reply
    # ------------------------------------------------------------------

    def reply_to_email(self, email_id: str, body: str, html: bool = False) -> dict:
        """Reply to an existing email thread."""
        try:
            # Fetch original to get threadId and headers
            original = (
                self._get_service()
                .users()
                .messages()
                .get(userId="me", id=email_id, format="metadata", metadataHeaders=["Subject", "From", "To", "Message-ID", "References"])
                .execute()
            )
            payload = original.get("payload", {})
            headers = {h["name"]: h["value"] for h in payload.get("headers", [])}

            thread_id = original.get("threadId")
            subject = headers.get("Subject", "")
            if not subject.lower().startswith("re:"):
                subject = f"Re: {subject}"

            from_addr = headers.get("To", "")
            to_addr = headers.get("From", "")
            message_id = headers.get("Message-ID", "")
            references = headers.get("References", "")
            if references:
                references = f"{references} {message_id}"
            else:
                references = message_id

            message = EmailMessage()
            message["To"] = to_addr
            message["From"] = from_addr
            message["Subject"] = subject
            message["In-Reply-To"] = message_id
            message["References"] = references

            if html:
                message.add_alternative(body, subtype="html")
            else:
                message.set_content(body)

            encoded = base64.urlsafe_b64encode(message.as_bytes()).decode()
            payload = {"raw": encoded, "threadId": thread_id}

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
            logger.exception("Gmail reply_to_email failed")
            return {
                "success": False,
                "error": str(exc),
                "status_code": exc.resp.status if exc.resp else None,
            }

    # ------------------------------------------------------------------
    # Drafts
    # ------------------------------------------------------------------

    def create_draft(self, to: str, subject: str, body: str, html: bool = False, reply_to: str | None = None) -> dict:
        """Create a draft email."""
        try:
            message = EmailMessage()
            message["To"] = to
            message["Subject"] = subject
            if html:
                message.add_alternative(body, subtype="html")
            else:
                message.set_content(body)

            encoded = base64.urlsafe_b64encode(message.as_bytes()).decode()
            draft_payload = {
                "message": {
                    "raw": encoded,
                }
            }
            if reply_to:
                draft_payload["message"]["threadId"] = reply_to

            result = (
                self._get_service()
                .users()
                .drafts()
                .create(userId="me", body=draft_payload)
                .execute()
            )
            return {
                "success": True,
                "draft_id": result.get("id"),
                "message_id": result.get("message", {}).get("id"),
            }
        except HttpError as exc:
            logger.exception("Gmail create_draft failed")
            return {
                "success": False,
                "error": str(exc),
                "status_code": exc.resp.status if exc.resp else None,
            }

    def list_drafts(self, max_results: int = 10) -> dict:
        """List draft emails."""
        try:
            result = (
                self._get_service()
                .users()
                .drafts()
                .list(userId="me", maxResults=max_results)
                .execute()
            )
            drafts = result.get("drafts", [])
            return {
                "success": True,
                "count": len(drafts),
                "drafts": [{"id": d["id"], "message_id": d.get("message", {}).get("id")} for d in drafts],
            }
        except HttpError as exc:
            logger.exception("Gmail list_drafts failed")
            return {
                "success": False,
                "error": str(exc),
                "status_code": exc.resp.status if exc.resp else None,
            }

    def send_draft(self, draft_id: str) -> dict:
        """Send an existing draft."""
        try:
            result = (
                self._get_service()
                .users()
                .drafts()
                .send(userId="me", body={"id": draft_id})
                .execute()
            )
            return {
                "success": True,
                "message_id": result.get("id"),
                "thread_id": result.get("threadId"),
            }
        except HttpError as exc:
            logger.exception("Gmail send_draft failed")
            return {
                "success": False,
                "error": str(exc),
                "status_code": exc.resp.status if exc.resp else None,
            }

    # ------------------------------------------------------------------
    # Labels
    # ------------------------------------------------------------------

    def list_labels(self) -> dict:
        """List all Gmail labels."""
        try:
            result = self._get_service().users().labels().list(userId="me").execute()
            labels = result.get("labels", [])
            return {
                "success": True,
                "count": len(labels),
                "labels": [{"id": l["id"], "name": l["name"], "type": l.get("type", "user")} for l in labels],
            }
        except HttpError as exc:
            logger.exception("Gmail list_labels failed")
            return {
                "success": False,
                "error": str(exc),
                "status_code": exc.resp.status if exc.resp else None,
            }

    def modify_labels(self, email_id: str, add_labels: list[str] | None = None, remove_labels: list[str] | None = None) -> dict:
        """Add or remove labels from an email."""
        try:
            body = {}
            if add_labels:
                body["addLabelIds"] = add_labels
            if remove_labels:
                body["removeLabelIds"] = remove_labels

            result = (
                self._get_service()
                .users()
                .messages()
                .modify(userId="me", id=email_id, body=body)
                .execute()
            )
            return {
                "success": True,
                "message_id": email_id,
                "label_ids": result.get("labelIds", []),
            }
        except HttpError as exc:
            logger.exception("Gmail modify_labels failed")
            return {
                "success": False,
                "error": str(exc),
                "status_code": exc.resp.status if exc.resp else None,
            }
