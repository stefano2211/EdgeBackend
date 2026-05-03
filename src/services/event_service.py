"""Event service with pipeline management and SSE broadcasting."""

import asyncio
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import NotFoundError, ValidationError
from src.persistencia.models.event import Event
from src.persistencia.repositories.event_repository import EventRepository
from src.api.v1.schemas.event import ManualEventPayload, ApprovalPayload
from src.services.event_broadcast import get_event_broadcast
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

    # ── Pipeline Actions ──

    async def approve_event(self, event_id: int, payload: ApprovalPayload | None = None) -> Event:
        event = await self.get_event(event_id)
        if event.status != "awaiting_approval":
            raise ValidationError(f"Event is not awaiting approval (current: {event.status})")

        event.status = "executing"
        event.agent_plan = (event.agent_plan or "") + f"\nApproved. Notes: {payload.notes or 'none'}"
        await self.session.commit()
        await self._broadcast_event_update(event)

        # In Fase 6 this would trigger actual tool execution via System 2
        # For now, auto-complete after a brief simulated execution
        await self._simulate_execution(event)
        return event

    async def reject_event(self, event_id: int, payload: ApprovalPayload | None = None) -> Event:
        event = await self.get_event(event_id)
        if event.status != "awaiting_approval":
            raise ValidationError(f"Event is not awaiting approval (current: {event.status})")

        event.status = "failed"
        event.resolved_at = datetime.now(timezone.utc)
        event.agent_plan = (event.agent_plan or "") + f"\nRejected. Notes: {payload.notes or 'none'}"
        await self.session.commit()
        await self._broadcast_event_update(event)
        return event

    async def start_analysis(self, event_id: int) -> Event:
        """Transition from pending -> analyzing. Stub for System 2 integration."""
        event = await self.get_event(event_id)
        if event.status != "pending":
            raise ValidationError(f"Event is not pending (current: {event.status})")

        event.status = "analyzing"
        await self.session.commit()
        await self._broadcast_event_update(event)

        # Simulate async analysis (stub — in Fase 6 this calls the LLM orchestrator)
        asyncio.create_task(self._simulate_analysis(event_id))
        return event

    # ── SSE Broadcasting ──

    def connect_sse(self) -> asyncio.Queue:
        """Register a new SSE listener via the global broadcast manager."""
        return get_event_broadcast().connect()

    def disconnect_sse(self, queue: asyncio.Queue) -> None:
        """Remove an SSE listener via the global broadcast manager."""
        get_event_broadcast().disconnect(queue)

    async def _broadcast_event_update(self, event: Event) -> None:
        """Push an event update to all connected SSE clients."""
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

    # ── Simulation Stubs ──

    async def _simulate_analysis(self, event_id: int) -> None:
        """Simulate AI analysis and transition to awaiting_approval."""
        await asyncio.sleep(2.0)

        event = await self.repo.get_by_id(event_id)
        if not event:
            return

        event.status = "awaiting_approval"
        event.agent_analysis = f"Simulated analysis for: {event.title}"
        event.agent_reasoning = "This is a stub reasoning. In Fase 6, System 2 will provide real LLM-based analysis."
        event.agent_plan = "1. Review data\n2. Take corrective action\n3. Verify resolution"
        await self.session.commit()
        await self._broadcast_event_update(event)

    async def _simulate_execution(self, event: Event) -> None:
        """Simulate tool execution and transition to completed."""
        await asyncio.sleep(1.5)
        event.status = "completed"
        event.resolved_at = datetime.now(timezone.utc)
        event.actions_taken = ["action_1_stub", "action_2_stub"]
        await self.session.commit()
        await self._broadcast_event_update(event)
