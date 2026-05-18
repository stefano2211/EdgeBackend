"""Events router — CRUD, SSE streaming, approval pipeline, and feedback."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.event import (
    EventListResponse,
    EventOut,
    ManualEventPayload,
    EventIngestPayload,
    ApprovalPayload,
    EventFeedbackPayload,
)
from src.core.deps import get_db, get_current_user, get_current_user_flexible, verify_api_key
from src.persistencia.models.user import User
from src.services.event_service import EventService
from src.services.event_broadcast import get_event_broadcast

router = APIRouter(prefix="/events", tags=["events"])

logger = logging.getLogger(__name__)


@router.get("", response_model=EventListResponse)
async def list_events(
    severity_text: str | None = Query(None),
    status: str | None = Query(None),
    domain: str | None = Query(None),
    event_type: str | None = Query(None),
    source: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> EventListResponse:
    """List events with filtering."""
    service = EventService(session)
    items, total = await service.list_events(
        severity_text=severity_text,
        status=status,
        domain=domain,
        event_type=event_type,
        source=source,
        skip=offset,
        limit=limit,
    )
    return EventListResponse(
        total=total,
        items=[EventOut.model_validate(i) for i in items],
    )


# ── SSE stream (MUST be before /{event_id} to avoid path param capture) ──

@router.get("/stream")
async def event_stream(current_user: User = Depends(get_current_user_flexible)) -> StreamingResponse:
    """Server-Sent Events stream for real-time event updates."""
    broadcast = get_event_broadcast()
    queue = broadcast.connect()

    async def generator():
        try:
            while True:
                data = await queue.get()
                if isinstance(data, str) and data.startswith("data:"):
                    yield data
                else:
                    import json
                    yield f"data: {json.dumps(data)}\n\n"
        except Exception as exc:
            logger.exception("Event SSE stream error: %s", exc)
        finally:
            broadcast.disconnect(queue)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


# ── CRUD (path-param routes AFTER static routes) ──

@router.get("/{event_id}", response_model=EventOut)
async def get_event(
    event_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> EventOut:
    """Get a single event by ID."""
    service = EventService(session)
    event = await service.get_event(event_id)
    return EventOut.model_validate(event)


@router.post("/ingest", response_model=EventOut, status_code=status.HTTP_202_ACCEPTED)
async def ingest_external_event(
    payload: EventIngestPayload,
    api_key: str = Depends(verify_api_key),
    session: AsyncSession = Depends(get_db),
) -> EventOut:
    """Ingest an event from external sensor/webhook (X-API-Key required).

    Supports CloudEvents (ce-* headers or application/cloudevents+json)
    as well as generic JSON payloads.
    """
    service = EventService(session)
    event = await service.ingest_event(payload)
    return EventOut.model_validate(event)


@router.post("/manual", response_model=EventOut, status_code=status.HTTP_202_ACCEPTED)
async def create_manual_event(
    payload: ManualEventPayload,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> EventOut:
    """Create a manual event (auto-starts analysis)."""
    service = EventService(session)
    event = await service.create_manual_event(payload, triggered_by_user_id=current_user.id)
    return EventOut.model_validate(event)


@router.post("/{event_id}/approve", response_model=EventOut)
async def approve_event(
    event_id: int,
    payload: ApprovalPayload | None = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> EventOut:
    """Approve an event for execution."""
    service = EventService(session)
    event = await service.approve_event(event_id, payload)
    return EventOut.model_validate(event)


@router.post("/{event_id}/reject", response_model=EventOut)
async def reject_event(
    event_id: int,
    payload: ApprovalPayload | None = None,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> EventOut:
    """Reject an event."""
    service = EventService(session)
    event = await service.reject_event(event_id, payload)
    return EventOut.model_validate(event)


@router.post("/{event_id}/feedback", status_code=status.HTTP_204_NO_CONTENT)
async def submit_event_feedback(
    event_id: int,
    payload: EventFeedbackPayload,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Submit feedback for an event (false positive, incorrect diagnosis, etc.)."""
    service = EventService(session)
    await service.submit_feedback(event_id, payload)
