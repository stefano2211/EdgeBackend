"""Event service — manages the event lifecycle with domain detection and normalization.

SOLID:
  - SRP: Only orchestrates event lifecycle; analysis/execution delegated.
  - DIP: Depends on repository abstractions, not concrete DB sessions.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import AsyncSessionLocal
from backend.core.exceptions import NotFoundError, ValidationError
from backend.persistencia.models.event import Event
from backend.persistencia.repositories.event_repository import EventRepository
from backend.persistencia.repositories.domain_config_repository import DomainConfigRepository
from backend.services.domain_detector import DomainDetector
from backend.api.v1.schemas.event import (
    EventIngestPayload,
    ApprovalPayload,
    EventFeedbackPayload,
    severity_text_to_number,
    severity_number_to_text,
)
from backend.services.event_broadcast import get_event_broadcast
from backend.services.reactive_orchestrator import ReactiveOrchestrator
from backend.services._helpers import commit_and_refresh

logger = logging.getLogger(__name__)


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

    async def ingest_event(
        self,
        payload: EventIngestPayload,
        triggered_by_user_id: int | None = None,
        domain: str | None = None,
    ) -> Event:
        """Ingest an external event (CloudEvents-compatible or generic JSON).

        Args:
            payload: Normalized event payload.
            triggered_by_user_id: User who owns the webhook/source.
            domain: Optional pre-resolved domain (e.g. from webhook cache).
                    When provided, skips automatic domain detection.
        """
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
            domain=domain,
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
        domain: str | None = None,
    ) -> Event:
        """Construct an Event with domain detection and dedup key generation.

        If *domain* is provided (e.g. cached on the webhook), detection is skipped.
        Otherwise falls back to automatic rule-based + LLM detection.
        """
        if domain:
            # Use pre-resolved domain — skip expensive detection
            detected_domain = domain
            subdomain = None
            logger.debug(
                "Event builder using pre-resolved domain='%s' for source='%s'",
                domain,
                source,
            )
        else:
            # Domain detection (rules + LLM fallback)
            domain_result = await self.domain_detector.detect(
                payload=body or {},
                user_id=triggered_by_user_id,
                source=source,
            )
            detected_domain = domain_result.get("domain")
            subdomain = domain_result.get("subdomain")

        # Dedup key: hash of source + type + title + domain (configurable)
        dedup_key = self._generate_dedup_key(source, event_type, title, detected_domain)

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
            domain=detected_domain,
            subdomain=subdomain,
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
        # Synchronous dedup check before expensive analysis.
        # Use ``with_for_update()`` to narrow the race-condition window
        # when two identical webhooks arrive concurrently.
        from datetime import timedelta

        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=5)
        stmt = (
            select(Event)
            .where(Event.dedup_key == event.dedup_key)
            .where(Event.created_at >= cutoff)
            .where(Event.suppression_reason.is_(None))
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            event.status = "suppressed"
            event.suppression_reason = "duplicate"
            await self.repo.create(event)
            await commit_and_refresh(self.session, event)
            await self._broadcast_event_update(event)
            logger.info(
                "Event deduplicated immediately | dedup_key=%s existing_event=%s",
                event.dedup_key,
                existing.id,
            )
            return

        await self.repo.create(event)
        await commit_and_refresh(self.session, event)
        await self._broadcast_event_update(event)

        # Enqueue durable background job instead of fire-and-forget task
        from backend.services.event_job_tracker import get_job_tracker
        await get_job_tracker().enqueue(
            event.id, "analysis", lambda: self._build_analysis_coro(event.id)
        )

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

        # Enqueue durable background job for execution
        from backend.services.event_job_tracker import get_job_tracker
        await get_job_tracker().enqueue(
            event_id, "execution", lambda: self._build_execution_coro(event_id)
        )
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
        from backend.persistencia.models.user_feedback import UserFeedback

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
    # Background job factories (passed to EventJobTracker)
    # ------------------------------------------------------------------

    def _build_analysis_coro(self, event_id: int):
        return _build_analysis_coro(event_id)

    def _build_execution_coro(self, event_id: int):
        return _build_execution_coro(event_id)

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


# ═══════════════════════════════════════════════════════════════════════
#  Module-level coroutine factories (usable by EventJobTracker recovery)
# ═══════════════════════════════════════════════════════════════════════

async def _build_analysis_coro(event_id: int) -> None:
    async with AsyncSessionLocal() as session:
        orchestrator = ReactiveOrchestrator(get_event_broadcast())
        event = await EventRepository(session).get_by_id(event_id)
        if event and event.status not in ("suppressed", "failed"):
            await orchestrator.analyze(event, session)
        else:
            logger.warning(
                "Analysis skipped for event %s (status=%s)",
                event_id,
                event.status if event else "deleted",
            )


async def _build_execution_coro(event_id: int) -> None:
    async with AsyncSessionLocal() as session:
        orchestrator = ReactiveOrchestrator(get_event_broadcast())
        event = await EventRepository(session).get_by_id(event_id)
        if event and event.status == "executing":
            await orchestrator.execute(event, session)
        else:
            logger.warning(
                "Execution skipped for event %s (status=%s)",
                event_id,
                event.status if event else "deleted",
            )
