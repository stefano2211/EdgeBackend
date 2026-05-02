"""Events router — stub (Fase 4)."""

from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/events", tags=["events"])


@router.get("")
async def list_events():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Events endpoints will be implemented in Fase 4",
    )


@router.post("/manual")
async def create_manual_event():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Events endpoints will be implemented in Fase 4",
    )


@router.post("/{event_id}/approve")
async def approve_event(event_id: int):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Events endpoints will be implemented in Fase 4",
    )


@router.post("/{event_id}/reject")
async def reject_event(event_id: int):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Events endpoints will be implemented in Fase 4",
    )


@router.get("/stream")
async def event_stream():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Event streaming will be implemented in Fase 4",
    )
