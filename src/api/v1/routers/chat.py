"""Chat router — stub (Fase 3)."""

from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/chat")
async def chat():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Chat endpoints will be implemented in Fase 3",
    )


@router.post("/chat/stream")
async def chat_stream():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Chat streaming will be implemented in Fase 3",
    )
