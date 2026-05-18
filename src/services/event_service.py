"""Event service — manages the event lifecycle with domain detection and normalization.

SOLID:
  - SRP: Only orchestrates event lifecycle; analysis/execution delegated.
  - DIP: Depends on repository abstractions, not concrete DB sessions.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import AsyncSessionLocal
from src.core.exceptions import NotFoundError, ValidationError
from src.persistencia.models.event import Event
from src.persistencia.repositories.event_repository import EventRepository
from src.persistencia.repositories.domain_config_repository import DomainConfigRepository
from src.services.domain_detector import DomainDetector
from src.api.v1.schemas.event import (
    ManualEventPayload,
    EventIngestPayload,
    ApprovalPayload,
    EventFeedbackPayload,
    severity_text_to_number,
    severity_number_to_text,
)
from src.services.event_broadcast import get_event_broadcast
from src.services.reactive_orchestrator import ReactiveOrchestrator
from src.services._helpers import commit_and_refresh

logger = logging.getLogger(__name__)


async def _with_retry(coro_func, max_retries: int = 3, base_delay: float = 1.0):
    """Run an async coroutine with exponential backoff retries."""
    last_exc = None
    for attempt in range(1, max_retries + 1):
        try:
            return await coro_func()
        except Exception as exc:
            last_exc = exc
            if attempt == max_retries:
                break
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning("Retry %d/%d after %.1fs due to %s", attempt, max_retries, delay, exc)
            await asyncio.sleep(delay)
    raise last_exc


class EventService:
    """Manages event creation, normalization, domain detection, and pipeline orchestration."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = EventRepository(session)
        self.domain_repo = DomainConfigRepository(session)
        self.domain_detector = DomainDetector(self.domain_repo)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def list_events(
        self,
        severity_text: str | None = None,
        status: str | None = None,
        domain: str | None = None,
        event_type: str | None = None,
        source: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[Event], int]:
        items = await self.repo.list_with_filters(
            severity_text=severity_text,
            status=status,
            domain=domain,
            event_type=event_type,
            source=source,
            skip=skip,
            limit=limit,
        )
        total = await self.repo.count_with_filters(
            severity_text=severity_text,
            status=status,
            domain=domain,
            event_type=event_type,
            source=source,
        )
        return items, total

    async def get_event(self, event_id: int) -> Event:
        event = await self.repo.get_by_id(event_id)
        if not event:
            raise NotFoundError(f"Event {event_id} not found")
        return event

    # ------------------------------------------------------------------
    # Creation with normalization
    # ------------------------------------------------------------------

    async def create_manual_event(
        self, payload: ManualEventPayload, triggered_by_user_id: int
    ) -> Event:
        """Create a manually-triggered event with domain detection."""
        event = await self._build_event(
            event_type="manual",
            source="user",
            title=payload.title,
            description=payload.description,
            body=payload.data,
            severity_number=severity_text_to_number(payload.severity_text.value),
            severity_text=payload.severity_text.value,
            triggered_by_user_id=triggered_by_user_id,
        )
        await self._persist_and_start(event)
        return event

    async def ingest_event(
        self, payload: EventIngestPayload, triggered_by_user_id: int | None = None
    ) -> Event:
        """Ingest an external event (CloudEvents-compatible or generic JSON)."""
        event = await self._build_event(
            event_type=payload.type or "generic",
            source=payload.source or "unknown",
            title=payload.title or "Untitled Event",
            description=payload.description,
            body=payload.data,
            severity_number=payload.severity_number or 13,
            severity_text=payload.severity_text.value if payload.severity_text else "warning",
            timestamp=payload.time,
            subject=payload.subject,
            triggered_by_user_id=triggered_by_user_id,
        )
        await self._persist_and_start(event)
        return event

    # ------------------------------------------------------------------
    # Event builder
    # ------------------------------------------------------------------

    async def _build_event(
        self,
        event_type: str,
        source: str,
        title: str,
        description: str | None,
        body: dict | None,
        severity_number: int,
        severity_text: str,
        timestamp: datetime | None = None,
        subject: str | None = None,
        triggered_by_user_id: int | None = None,
    ) -> Event:
        """Construct an Event with domain detection and dedup key generation."""
        # Domain detection
        domain_result = await self.domain_detector.detect(
            payload=body or {},
            user_id=triggered_by_user_id,
            source=source,
        )

        # Dedup key: hash of source + type + title + domain (configurable)
        dedup_key = self._generate_dedup_key(source, event_type, title, domain_result["domain"])

        return Event(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            source=source,
            timestamp=timestamp or datetime.now(timezone.utc).replace(tzinfo=None),
            subject=subject,
            severity_number=severity_number,
            severity_text=severity_text,
            title=title,
            description=description,
            body=body,
            domain=domain_result.get("domain"),
            subdomain=domain_result.get("subdomain"),
            dedup_key=dedup_key,
            resource={"ingested_at": datetime.now(timezone.utc).isoformat()},
            status="pending",
            triggered_by_user_id=triggered_by_user_id,
        )

    @staticmethod
    def _generate_dedup_key(source: str, event_type: str, title: str, domain: str | None) -> str:
        """Generate a deterministic dedup key from event attributes."""
        import hashlib

        raw = f"{source}:{event_type}:{title}:{domain or 'generic'}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    async def _persist_and_start(self, event: Event) -> None:
        """Persist event, broadcast creation, and start analysis pipeline."""
        await self.repo.create(event)
        await commit_and_refresh(self.session, event)
        await self._broadcast_event_update(event)

        # Start analysis in background with isolated session
        asyncio.create_task(self._run_analysis_background(event.id))

    # ------------------------------------------------------------------
    # Pipeline Actions
    # ------------------------------------------------------------------

    async def approve_event(self, event_id: int, payload: ApprovalPayload | None = None) -> Event:
        event = await self.get_event(event_id)
        if event.status != "awaiting_approval":
            raise ValidationError(f"Event is not awaiting approval (current: {event.status})")

        event.status = "executing"
        if payload and payload.notes:
            event.agent_plan = (event.agent_plan or "") + f"\nApproved. Notes: {payload.notes}"
        await self.session.commit()
        await self._refresh_and_broadcast(event)

        asyncio.create_task(self._run_execution_background(event_id))
        return event

    async def reject_event(self, event_id: int, payload: ApprovalPayload | None = None) -> Event:
        event = await self.get_event(event_id)
        if event.status != "awaiting_approval":
            raise ValidationError(f"Event is not awaiting approval (current: {event.status})")

        event.status = "failed"
        event.resolved_at = datetime.now(timezone.utc).replace(tzinfo=None)
        if payload and payload.notes:
            event.agent_plan = (event.agent_plan or "") + f"\nRejected. Notes: {payload.notes}"
        await self.session.commit()
        await self._broadcast_event_update(event)
        return event

    async def submit_feedback(self, event_id: int, payload: EventFeedbackPayload) -> None:
        """Record user feedback for an event."""
        event = await self.get_event(event_id)
        from src.persistencia.models.user_feedback import UserFeedback

        feedback = UserFeedback(
            event_id=event.id,
            user_id=event.triggered_by_user_id,
            feedback_type=payload.feedback_type,
            comment=payload.comment,
        )
        self.session.add(feedback)
        await self.session.commit()

        logger.info("Feedback recorded for event=%s: %s", event_id, payload.feedback_type)

    # ------------------------------------------------------------------
    # Background tasks (isolated sessions)
    # ------------------------------------------------------------------

    async def _run_analysis_background(self, event_id: int) -> None:
        async def _analysis():
            async with AsyncSessionLocal() as session:
                orchestrator = ReactiveOrchestrator(get_event_broadcast())
                event = await EventRepository(session).get_by_id(event_id)
                if event:
                    await orchestrator.analyze(event, session)

        try:
            await _with_retry(_analysis, max_retries=3, base_delay=1.0)
        except Exception:
            logger.exception("Background analysis failed for event %s after retries", event_id)

    async def _run_execution_background(self, event_id: int) -> None:
        async def _execution():
            async with AsyncSessionLocal() as session:
                orchestrator = ReactiveOrchestrator(get_event_broadcast())
                event = await EventRepository(session).get_by_id(event_id)
                if event:
                    await orchestrator.execute(event, session)

        try:
            await _with_retry(_execution, max_retries=3, base_delay=1.0)
        except Exception:
            logger.exception("Background execution failed for event %s after retries", event_id)

    # ------------------------------------------------------------------
    # SSE helpers
    # ------------------------------------------------------------------

    async def _broadcast_event_update(self, event: Event) -> None:
        payload = {
            "type": "event_update",
            "event": {
                "id": event.id,
                "event_id": event.event_id,
                "status": event.status,
                "severity_text": event.severity_text,
                "severity_number": event.severity_number,
                "title": event.title,
                "domain": event.domain,
                "updated_at": event.updated_at.isoformat() if event.updated_at else None,
            },
        }
        await get_event_broadcast().broadcast(payload)

    async def _refresh_and_broadcast(self, event: Event) -> None:
        await self.session.refresh(event)
        await self._broadcast_event_update(event)
