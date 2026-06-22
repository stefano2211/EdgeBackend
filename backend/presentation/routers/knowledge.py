"""Knowledge router — functional CRUD."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.presentation.schemas.knowledge import (
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    KnowledgeBaseOut,
    KnowledgeBaseDetailOut,
    KnowledgeDocumentOut,
)
from backend.core.deps import get_db, get_current_user
from backend.domain.models.user import User
from backend.application.knowledge.service import KnowledgeService

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("", response_model=list[KnowledgeBaseOut])
async def list_knowledge_bases(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = KnowledgeService(session)
    kbs = await service.list_knowledge_bases(current_user.id)
    return kbs


@router.post("", response_model=KnowledgeBaseOut, status_code=201)
async def create_knowledge_base(
    data: KnowledgeBaseCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = KnowledgeService(session)
    kb = await service.create_knowledge_base(current_user.id, data)
    return kb


@router.get("/{knowledge_id}", response_model=KnowledgeBaseDetailOut)
async def get_knowledge_base(
    knowledge_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = KnowledgeService(session)
    kb = await service.get_knowledge_base_with_documents(knowledge_id, current_user.id)
    # Build detail response with documents
    return KnowledgeBaseDetailOut(
        id=kb.id,
        user_id=kb.user_id,
        name=kb.name,
        description=kb.description,
        is_enabled_chat=kb.is_enabled_chat,
        is_enabled_reactive=kb.is_enabled_reactive,
        created_at=kb.created_at,
        updated_at=kb.updated_at,
        documents=[
            KnowledgeDocumentOut(
                id=d.id,
                file_id=d.file_id,
                filename=d.filename,
                status=d.status,
                created_at=d.created_at,
            )
            for d in kb.documents
        ],
    )


@router.patch("/{knowledge_id}", response_model=KnowledgeBaseOut)
async def update_knowledge_base(
    knowledge_id: int,
    data: KnowledgeBaseUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = KnowledgeService(session)
    kb = await service.update_knowledge_base(knowledge_id, current_user.id, data)
    return kb


@router.delete("/{knowledge_id}", status_code=204)
async def delete_knowledge_base(
    knowledge_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = KnowledgeService(session)
    await service.delete_knowledge_base(knowledge_id, current_user.id)
    return None


@router.patch("/{knowledge_id}/toggle-chat", response_model=KnowledgeBaseOut)
async def toggle_chat(
    knowledge_id: int,
    enabled: bool,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = KnowledgeService(session)
    kb = await service.toggle_chat(knowledge_id, current_user.id, enabled)
    return kb


@router.patch("/{knowledge_id}/toggle-reactive", response_model=KnowledgeBaseOut)
async def toggle_reactive(
    knowledge_id: int,
    enabled: bool,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = KnowledgeService(session)
    kb = await service.toggle_reactive(knowledge_id, current_user.id, enabled)
    return kb
