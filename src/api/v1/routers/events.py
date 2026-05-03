"""Events router — CRUD + SSE streaming + approval pipeline."""

import logging

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.event import (
    EventListResponse,
    EventOut,
    ManualEventPayload,
    ApprovalPayload,
)
from src.core.deps import get_db, get_current_user_id
from src.services.event_service import EventService
from src.services.event_broadcast import get_event_broadcast

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=EventListResponse)
async def list_events(
    severity: str | None = Query(None),
    status: str | None = Query(None),
    source_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = EventService(session)
    items, total = await service.list_events(
        severity=severity,
        status=status,
        source_type=source_type,
        skip=offset,
        limit=limit,
    )
    return EventListResponse(
        total=total,
        items=[EventOut.model_validate(i) for i in items],
    )


@router.get("/{event_id}", response_model=EventOut)
async def get_event(
    event_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = EventService(session)
    event = await service.get_event(event_id)
    return EventOut.model_validate(event)


@router.post("/manual", response_model=EventOut, status_code=201)
async def create_manual_event(
    payload: ManualEventPayload,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = EventService(session)
    event = await service.create_manual_event(payload, triggered_by_user_id=user_id)
    # Auto-start analysis in background
    await service.start_analysis(event.id)
    return EventOut.model_validate(event)


@router.post("/{event_id}/approve", response_model=EventOut)
async def approve_event(
    event_id: int,
    payload: ApprovalPayload | None = None,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = EventService(session)
    event = await service.approve_event(event_id, payload)
    return EventOut.model_validate(event)


@router.post("/{event_id}/reject", response_model=EventOut)
async def reject_event(
    event_id: int,
    payload: ApprovalPayload | None = None,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = EventService(session)
    event = await service.reject_event(event_id, payload)
    return EventOut.model_validate(event)


@router.get("/stream")
async def event_stream(user_id: int = Depends(get_current_user_id)):
    broadcast = get_event_broadcast()
    queue = broadcast.connect()

    async def generator():
        try:
            while True:
                data = await queue.get()
                yield data
        except Exception as exc:
            logging.getLogger(__name__).exception("Event SSE stream error: %s", exc)
        finally:
            broadcast.disconnect(queue)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
