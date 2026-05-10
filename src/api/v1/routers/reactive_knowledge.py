"""Reactive Knowledge router — functional CRUD for reactive knowledge bases."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.reactive_knowledge import (
    ReactiveKnowledgeBaseCreate,
    ReactiveKnowledgeBaseUpdate,
    ReactiveKnowledgeBaseOut,
    ReactiveKnowledgeBaseDetailOut,
    ReactiveKnowledgeDocumentOut,
)
from src.core.deps import get_db, get_current_user
from src.persistencia.models.user import User
from src.services.reactive_knowledge_service import ReactiveKnowledgeService

router = APIRouter(prefix="/reactive/knowledge", tags=["reactive-knowledge"])


@router.get("", response_model=list[ReactiveKnowledgeBaseOut])
async def list_reactive_knowledge_bases(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ReactiveKnowledgeService(session)
    kbs = await service.list_knowledge_bases(current_user.id)
    return kbs


@router.post("", response_model=ReactiveKnowledgeBaseOut, status_code=201)
async def create_reactive_knowledge_base(
    data: ReactiveKnowledgeBaseCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ReactiveKnowledgeService(session)
    kb = await service.create_knowledge_base(current_user.id, data)
    return kb


@router.get("/{knowledge_id}", response_model=ReactiveKnowledgeBaseDetailOut)
async def get_reactive_knowledge_base(
    knowledge_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ReactiveKnowledgeService(session)
    kb = await service.get_knowledge_base_with_documents(knowledge_id, current_user.id)
    return ReactiveKnowledgeBaseDetailOut(
        id=kb.id,
        user_id=kb.user_id,
        name=kb.name,
        description=kb.description,
        is_enabled=kb.is_enabled,
        created_at=kb.created_at,
        updated_at=kb.updated_at,
        documents=[
            ReactiveKnowledgeDocumentOut(
                id=d.id,
                file_id=d.file_id,
                filename=d.filename,
                status=d.status,
                created_at=d.created_at,
            )
            for d in kb.documents
        ],
    )


@router.patch("/{knowledge_id}", response_model=ReactiveKnowledgeBaseOut)
async def update_reactive_knowledge_base(
    knowledge_id: int,
    data: ReactiveKnowledgeBaseUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ReactiveKnowledgeService(session)
    kb = await service.update_knowledge_base(knowledge_id, current_user.id, data)
    return kb


@router.delete("/{knowledge_id}", status_code=204)
async def delete_reactive_knowledge_base(
    knowledge_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ReactiveKnowledgeService(session)
    await service.delete_knowledge_base(knowledge_id, current_user.id)
    return None
