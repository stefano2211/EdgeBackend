"""Chat router — non-streaming + SSE streaming."""

import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.v1.schemas.chat import ChatRequest, ChatResponse
from backend.core.deps import get_db, get_current_user
from backend.persistencia.models.user import User
from backend.services.chat_service import ChatService
router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ChatService(session)
    result = await service.process_non_stream(request, current_user.id)
    return ChatResponse(**result)


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ChatService(session)

    async def event_generator():
        try:
            async for event in service.process_stream(request, current_user.id):
                # Handle both dicts and Pydantic models
                if hasattr(event, "model_dump"):
                    event = event.model_dump()
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:
            logging.getLogger(__name__).exception("Chat stream error: %s", exc)
            yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )



