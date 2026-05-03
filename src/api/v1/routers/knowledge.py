"""Knowledge router — functional CRUD."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.knowledge import (
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    KnowledgeBaseOut,
    KnowledgeBaseDetailOut,
    KnowledgeDocumentOut,
)
from src.core.deps import get_db, get_current_user_id
from src.services.knowledge_service import KnowledgeService

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("", response_model=list[KnowledgeBaseOut])
async def list_knowledge_bases(
    context_mode: str | None = Query(None),
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = KnowledgeService(session)
    kbs = await service.list_knowledge_bases(user_id, context_mode)
    return kbs


@router.post("", response_model=KnowledgeBaseOut, status_code=201)
async def create_knowledge_base(
    data: KnowledgeBaseCreate,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = KnowledgeService(session)
    kb = await service.create_knowledge_base(user_id, data)
    return kb


@router.get("/{knowledge_id}", response_model=KnowledgeBaseDetailOut)
async def get_knowledge_base(
    knowledge_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = KnowledgeService(session)
    kb = await service.get_knowledge_base_with_documents(knowledge_id, user_id)
    # Build detail response with documents
    return KnowledgeBaseDetailOut(
        id=kb.id,
        user_id=kb.user_id,
        name=kb.name,
        description=kb.description,
        context_mode=kb.context_mode,
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
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = KnowledgeService(session)
    kb = await service.update_knowledge_base(knowledge_id, user_id, data)
    return kb


@router.delete("/{knowledge_id}", status_code=204)
async def delete_knowledge_base(
    knowledge_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = KnowledgeService(session)
    await service.delete_knowledge_base(knowledge_id, user_id)
    return None
