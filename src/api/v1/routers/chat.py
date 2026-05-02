"""Chat router — non-streaming + SSE streaming."""

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.chat import ChatRequest, ChatResponse
from src.core.database import AsyncSessionLocal
from src.core.deps import get_current_user_id
from src.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = ChatService(session)
    result = await service.process_non_stream(request, user_id)
    return ChatResponse(**result)


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = ChatService(session)

    async def event_generator():
        try:
            async for event in service.process_stream(request, user_id):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
