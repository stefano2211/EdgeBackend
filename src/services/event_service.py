"""Event service with pipeline management and SSE broadcasting."""

import asyncio
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import AsyncSessionLocal
from src.core.exceptions import NotFoundError, ValidationError
from src.persistencia.models.event import Event
from src.persistencia.repositories.event_repository import EventRepository
from src.api.v1.schemas.event import ManualEventPayload, EventIngestPayload, ApprovalPayload
from src.services.event_broadcast import get_event_broadcast
from src.services.reactive_orchestrator import ReactiveOrchestrator
from src.services._helpers import commit_and_refresh


class EventService:
    """Manages the event lifecycle pipeline and broadcasts SSE updates."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = EventRepository(session)

    # ── CRUD ──

    async def list_events(
        self,
        severity: str | None = None,
        status: str | None = None,
        source_type: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[Event], int]:
        items = await self.repo.list_with_filters(severity, status, source_type, skip, limit)
        total = await self.repo.count_with_filters(severity, status, source_type)
        return items, total

    async def get_event(self, event_id: int) -> Event:
        event = await self.repo.get_by_id(event_id)
        if not event:
            raise NotFoundError(f"Event {event_id} not found")
        return event

    async def create_manual_event(
        self, payload: ManualEventPayload, triggered_by_user_id: int | None = None
    ) -> Event:
        event = Event(
            tenant_id="default",
            source_type="manual",
            severity=payload.severity.value,
            status="pending",
            title=payload.title,
            description=payload.description,
            raw_payload=payload.raw_payload,
            triggered_by_user_id=triggered_by_user_id,
        )
        await self.repo.create(event)
        await commit_and_refresh(self.session, event)
        await self._broadcast_event_update(event)
        return event

    async def ingest_event(self, payload: EventIngestPayload) -> Event:
        event = Event(
            tenant_id=payload.tenant_id,
            source_type=payload.source_type.value,
            severity=payload.severity.value,
            status="pending",
            title=payload.title,
            description=payload.description,
            raw_payload=payload.raw_payload,
            triggered_by_user_id=None,
        )
        await self.repo.create(event)
        await commit_and_refresh(self.session, event)
        await self._broadcast_event_update(event)
        return event

    # ── Pipeline Actions ──

    async def approve_event(self, event_id: int, payload: ApprovalPayload | None = None) -> Event:
        event = await self.get_event(event_id)
        if event.status != "awaiting_approval":
            raise ValidationError(f"Event is not awaiting approval (current: {event.status})")

        event.status = "executing"
        if payload and payload.notes:
            event.agent_plan = (event.agent_plan or "") + f"\nApproved. Notes: {payload.notes}"
        await self.session.commit()
        await self._refresh_and_broadcast(event)

        # Launch execution in background with isolated session
        asyncio.create_task(self._run_execution_background(event_id))
        return event

    async def reject_event(self, event_id: int, payload: ApprovalPayload | None = None) -> Event:
        event = await self.get_event(event_id)
        if event.status != "awaiting_approval":
            raise ValidationError(f"Event is not awaiting approval (current: {event.status})")

        event.status = "failed"
        event.resolved_at = datetime.now(timezone.utc)
        if payload and payload.notes:
            event.agent_plan = (event.agent_plan or "") + f"\nRejected. Notes: {payload.notes}"
        await self.session.commit()
        await self._broadcast_event_update(event)
        return event

    async def start_analysis(self, event_id: int) -> Event:
        """Transition from pending -> analyzing, then launch background analysis."""
        event = await self.get_event(event_id)
        if event.status != "pending":
            raise ValidationError(f"Event is not pending (current: {event.status})")

        event.status = "analyzing"
        await self.session.commit()
        await self._refresh_and_broadcast(event)

        # Launch analysis in background with isolated session
        asyncio.create_task(self._run_analysis_background(event_id))
        return event

    # ── Background tasks (isolated sessions) ──

    async def _run_analysis_background(self, event_id: int) -> None:
        """Run analysis with a fresh database session."""
        async with AsyncSessionLocal() as session:
            try:
                orchestrator = ReactiveOrchestrator(get_event_broadcast())
                event = await EventRepository(session).get_by_id(event_id)
                if event:
                    await orchestrator.analyze(event, session)
            except Exception:
                import logging
                logging.getLogger(__name__).exception(
                    "Background analysis failed for event %s", event_id
                )

    async def _run_execution_background(self, event_id: int) -> None:
        """Run execution with a fresh database session."""
        async with AsyncSessionLocal() as session:
            try:
                orchestrator = ReactiveOrchestrator(get_event_broadcast())
                event = await EventRepository(session).get_by_id(event_id)
                if event:
                    await orchestrator.execute(event, session)
            except Exception:
                import logging
                logging.getLogger(__name__).exception(
                    "Background execution failed for event %s", event_id
                )

    # ── SSE helpers ──

    async def _broadcast_event_update(self, event: Event) -> None:
        payload = {
            "type": "event_update",
            "event": {
                "id": event.id,
                "status": event.status,
                "severity": event.severity,
                "title": event.title,
                "updated_at": event.updated_at.isoformat() if event.updated_at else None,
            },
        }
        await get_event_broadcast().broadcast(payload)

    async def _refresh_and_broadcast(self, event: Event) -> None:
        """Refresh event from DB and broadcast update."""
        await self.session.refresh(event)
        await self._broadcast_event_update(event)
