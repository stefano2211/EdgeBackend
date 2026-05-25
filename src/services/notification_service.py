"""Notification Service — generic event notifications via direct Gmail API.

Replaces VL-Agent browser automation for email delivery with direct GmailClient
instantiation using stored OAuth2 credentials or environment fallback. This is
orders of magnitude faster and more reliable than browser-based email composition.

Architecture:
  1. Resolve recipient (user preference → global default)
  2. Resolve Gmail credentials (user IntegrationInstance → env fallback)
  3. Format generic notification (no sector assumptions)
  4. Send via Gmail API in thread pool
  5. Retry with exponential backoff
  6. Audit log to NotificationLog
"""

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.config import settings
from src.core.logging import logging
from src.integrations.credentials import CredentialManager
from src.integrations.custom_mcp_servers.gmail.client import GmailClient
from src.integrations.models import IntegrationInstance, IntegrationCatalog
from src.integrations.repositories.integration_repository import IntegrationInstanceRepository
from src.persistencia.models.event import Event
from src.persistencia.models.notification_log import NotificationLog
from src.persistencia.models.user import User

logger = logging.getLogger(__name__)


class NotificationService:
    """Sends event notifications via configured channels."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def notify_analysis_complete(self, event: Event) -> dict:
        """Notify that analysis is complete and awaiting approval."""
        subject = f"[Aura AI] Event Analysis Complete — {event.title}"
        body = self._format_analysis_email(event)
        return await self._send_with_retry(
            event=event,
            subject=subject,
            body=body,
            trigger="analysis_complete",
        )

    async def notify_execution_complete(self, event: Event) -> dict:
        """Notify that execution completed successfully."""
        subject = f"[Aura AI] Event Resolved — {event.title}"
        body = self._format_resolution_email(event)
        return await self._send_with_retry(
            event=event,
            subject=subject,
            body=body,
            trigger="execution_complete",
        )

    async def notify_execution_failed(self, event: Event, error: Exception) -> dict:
        """Notify that pipeline execution failed."""
        subject = f"[Aura AI] Event Failed — {event.title}"
        body = self._format_failure_email(event, error)
        return await self._send_with_retry(
            event=event,
            subject=subject,
            body=body,
            trigger="execution_failed",
        )

    # ------------------------------------------------------------------
    # Core delivery with retry + audit
    # ------------------------------------------------------------------

    async def _send_with_retry(
        self,
        event: Event,
        subject: str,
        body: str,
        trigger: str,
        max_retries: int = 3,
    ) -> dict:
        """Send email with exponential-backoff retry and audit logging."""
        recipient = await self._resolve_recipient(event)
        user_id = event.triggered_by_user_id
        last_result: dict[str, Any] = {"success": False, "error": "No attempts made"}

        # Resolve Gmail client once (may query DB for user credentials)
        try:
            client = await self._resolve_gmail_client(user_id)
        except Exception as exc:
            logger.error("Failed to resolve Gmail client for event=%s: %s", event.id, exc)
            await self._persist_log(
                event_id=event.id,
                user_id=user_id,
                channel="email",
                recipient=recipient,
                status="failed",
                error_message=str(exc),
            )
            return {"success": False, "error": str(exc)}

        for attempt in range(1, max_retries + 1):
            try:
                # GmailClient.send_email is a blocking HTTP call — run in thread pool
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    None,
                    lambda: client.send_email(to=recipient, subject=subject, body=body),
                )

                status = "success" if result.get("success") else "failed"
                error_msg = result.get("error") if not result.get("success") else None

                await self._persist_log(
                    event_id=event.id,
                    user_id=user_id,
                    channel="email",
                    recipient=recipient,
                    status=status,
                    error_message=error_msg,
                )

                if result.get("success"):
                    logger.info(
                        "Notification sent [%s] event=%s attempt=%s/%s",
                        trigger,
                        event.id,
                        attempt,
                        max_retries,
                    )
                    return result

                last_result = result
                logger.warning(
                    "Notification attempt %s/%s failed for event=%s: %s",
                    attempt,
                    max_retries,
                    event.id,
                    result.get("error"),
                )

            except Exception as exc:
                last_result = {"success": False, "error": str(exc)}
                logger.warning(
                    "Notification attempt %s/%s failed for event=%s: %s",
                    attempt,
                    max_retries,
                    event.id,
                    exc,
                    exc_info=attempt == max_retries,
                )

            if attempt < max_retries:
                delay = 2 ** (attempt - 1)  # 1s, 2s, 4s
                await asyncio.sleep(delay)

        # All retries exhausted
        await self._persist_log(
            event_id=event.id,
            user_id=user_id,
            channel="email",
            recipient=recipient,
            status="failed",
            error_message=str(last_result.get("error")),
        )
        return last_result

    # ------------------------------------------------------------------
    # Recipient resolution
    # ------------------------------------------------------------------

    async def _resolve_recipient(self, event: Event) -> str:
        """Determine notification recipient.

        Priority:
        1. User's notification_email preference
        2. Global REACTIVE_NOTIFICATION_EMAIL fallback
        """
        if event.triggered_by_user_id:
            user = await self._session.get(User, event.triggered_by_user_id)
            if user and user.notification_email:
                return user.notification_email
        return settings.REACTIVE_NOTIFICATION_EMAIL

    # ------------------------------------------------------------------
    # Gmail client resolution
    # ------------------------------------------------------------------

    async def _resolve_gmail_client(self, user_id: int | None) -> GmailClient:
        """Return a GmailClient.

        Priority:
        1. User's configured Gmail IntegrationInstance (OAuth2 credentials from DB)
        2. Environment variables (GMAIL_REFRESH_TOKEN, GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET)
        """
        if user_id:
            client = await self._try_user_gmail_client(user_id)
            if client:
                return client

        # Environment fallback (primary mechanism for MVP)
        try:
            return GmailClient.from_env()
        except KeyError as exc:
            raise RuntimeError(
                "No Gmail credentials available. "
                "Please set GMAIL_REFRESH_TOKEN, GMAIL_CLIENT_ID, and GMAIL_CLIENT_SECRET "
                "in your environment, or configure a Gmail integration."
            ) from exc

    async def _try_user_gmail_client(self, user_id: int) -> GmailClient | None:
        """Try to build a GmailClient from the user's IntegrationInstance credentials."""
        stmt = (
            select(IntegrationInstance)
            .join(IntegrationCatalog)
            .where(
                IntegrationInstance.user_id == user_id,
                IntegrationInstance.is_enabled.is_(True),
                IntegrationCatalog.slug.in_(["gmail", "google", "google-mail"]),
            )
            .options(selectinload(IntegrationInstance.credentials))
            .options(selectinload(IntegrationInstance.catalog))
        )
        result = await self._session.execute(stmt)
        instance = result.scalar_one_or_none()

        if not instance:
            return None

        repo = IntegrationInstanceRepository(self._session)
        cm = CredentialManager(repo)
        creds = await cm.get_credentials(instance)

        refresh_token = (
            creds.get("refresh_token")
            or creds.get("oauth_refresh_token")
        )
        client_id = (
            creds.get("client_id")
            or creds.get("oauth_client_id")
        )
        client_secret = (
            creds.get("client_secret")
            or creds.get("oauth_client_secret")
        )

        if refresh_token and client_id and client_secret:
            return GmailClient(
                refresh_token=refresh_token,
                client_id=client_id,
                client_secret=client_secret,
            )

        return None

    # ------------------------------------------------------------------
    # Templates (generic — zero sector assumptions)
    # ------------------------------------------------------------------

    def _format_analysis_email(self, event: Event) -> str:
        return f"""Aura AI Event Notification
==============================

Event: {event.title}
Status: Analysis Complete — Awaiting Approval
Severity: {event.severity_text}
Domain: {getattr(event, 'domain', 'generic')}

Analysis Summary:
{self._truncate(getattr(event, 'agent_analysis', 'No analysis available.'), 800)}

Proposed Plan:
{self._truncate(getattr(event, 'agent_plan', 'No plan generated.'), 500)}

Action Required:
Please review and approve or reject at:
http://localhost:5173/events

---
Aura AI Operations Center
"""

    def _format_resolution_email(self, event: Event) -> str:
        return f"""Aura AI Event Notification
==============================

Event: {event.title}
Status: Resolved
Severity: {event.severity_text}
Domain: {getattr(event, 'domain', 'generic')}

Analysis Summary:
{self._truncate(getattr(event, 'agent_analysis', 'No analysis available.'), 800)}

Actions Taken:
{self._truncate(getattr(event, 'agent_plan', 'No plan available.'), 500)}

Result: Event has been successfully resolved.

---
Aura AI Operations Center
"""

    def _format_failure_email(self, event: Event, error: Exception) -> str:
        return f"""Aura AI Event Notification
==============================

Event: {event.title}
Status: FAILED
Severity: {event.severity_text}
Domain: {getattr(event, 'domain', 'generic')}

Error:
{self._truncate(str(error), 800)}

Please investigate at:
http://localhost:5173/events

---
Aura AI Operations Center
"""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _truncate(text: str | None, max_len: int) -> str:
        if not text:
            return "N/A"
        return text if len(text) <= max_len else text[: max_len - 3] + "..."

    async def _persist_log(
        self,
        event_id: int,
        user_id: int | None,
        channel: str,
        recipient: str,
        status: str,
        error_message: str | None,
    ) -> None:
        """Persist notification attempt to audit log."""
        log = NotificationLog(
            event_id=event_id,
            user_id=user_id,
            channel=channel,
            recipient=recipient,
            status=status,
            error_message=error_message,
        )
        self._session.add(log)
        try:
            await self._session.commit()
        except Exception as exc:
            logger.warning("Failed to persist notification log: %s", exc)
            await self._session.rollback()
