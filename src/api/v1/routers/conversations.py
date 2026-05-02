"""Conversations router — stub (Fase 3)."""

from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("")
async def list_conversations():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Conversations endpoints will be implemented in Fase 3",
    )


@router.post("")
async def create_conversation():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Conversations endpoints will be implemented in Fase 3",
    )


@router.get("/{thread_id}/messages")
async def get_messages(thread_id: str):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Conversations endpoints will be implemented in Fase 3",
    )


@router.delete("/{thread_id}")
async def delete_conversation(thread_id: str):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Conversations endpoints will be implemented in Fase 3",
    )


@router.patch("/{thread_id}/archive")
async def archive_conversation(thread_id: str):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Conversations endpoints will be implemented in Fase 3",
    )
