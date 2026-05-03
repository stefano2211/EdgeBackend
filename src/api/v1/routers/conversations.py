"""Conversations router — functional CRUD."""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.conversation import ConversationCreate, ConversationOut, MessageOut
from src.core.deps import get_db, get_current_user_id
from src.services.chat_service import ChatService

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationOut])
async def list_conversations(
    include_archived: bool = Query(False),
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = ChatService(session)
    convs = await service.list_conversations(user_id, include_archived)
    return convs


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    data: ConversationCreate,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = ChatService(session)
    conv = await service.get_or_create_conversation(None, user_id, data.title)
    return conv


@router.get("/{thread_id}/messages", response_model=list[MessageOut])
async def get_messages(
    thread_id: str,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = ChatService(session)
    messages = await service.get_messages(thread_id, user_id)
    return messages


@router.delete("/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    thread_id: str,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = ChatService(session)
    ok = await service.delete_conversation(thread_id, user_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return None


@router.patch("/{thread_id}/archive", response_model=ConversationOut)
async def archive_conversation(
    thread_id: str,
    archive: bool = Query(True),
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = ChatService(session)
    conv = await service.archive_conversation(thread_id, archive)
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conv
