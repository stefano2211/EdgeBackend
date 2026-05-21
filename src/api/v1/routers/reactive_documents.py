"""Reactive Documents router — thin controller that delegates upload orchestration to ReactiveDocumentService."""

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.reactive_document import ReactiveDocumentOut
from src.core.deps import get_db, get_current_user, get_storage
from src.persistencia.models.user import User
from src.persistencia.storage.storage_port import StoragePort
from src.services.reactive_document_service import ReactiveDocumentService
from src.services.reactive_document_processor import ReactiveDocumentProcessor

router = APIRouter(prefix="/reactive/documents", tags=["reactive-documents"])


@router.post("/upload", response_model=ReactiveDocumentOut, status_code=201)
async def upload_reactive_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    knowledge_base_id: int = Form(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    storage: StoragePort = Depends(get_storage),
):
    """Upload a document into a Reactive KnowledgeBase (stored in MinIO/S3, processed asynchronously)."""
    service = ReactiveDocumentService(session, storage=storage)
    try:
        doc = await service.upload_document(knowledge_base_id, current_user.id, file)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)
        )

    background_tasks.add_task(
        ReactiveDocumentProcessor(storage=storage).process_document,
        doc.id,
        knowledge_base_id,
    )

    return ReactiveDocumentOut.model_validate(doc)


@router.get("/{doc_id}", response_model=ReactiveDocumentOut)
async def get_reactive_document(
    doc_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    from src.persistencia.repositories.reactive_document_repository import ReactiveDocumentRepository
    repo = ReactiveDocumentRepository(session)
    doc = await repo.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return ReactiveDocumentOut.model_validate(doc)


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_reactive_document(
    doc_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    storage: StoragePort = Depends(get_storage),
):
    """Delete a reactive document (DB record + MinIO object + Qdrant vectors)."""
    service = ReactiveDocumentService(session, storage=storage)
    await service.delete_document(doc_id)
    return None
