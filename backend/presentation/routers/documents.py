"""Documents router — thin controller that delegates upload orchestration to DocumentService."""

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from backend.presentation.schemas.document import DocumentOut, DocumentListResponse
from backend.core.deps import get_db, get_current_user, get_storage
from backend.domain.models.user import User
from backend.domain.ports.storage import StoragePort
from backend.application.knowledge.document import DocumentService
from backend.application.knowledge.processor import DocumentProcessor

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentOut, status_code=201)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    knowledge_base_id: int = Form(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    storage: StoragePort = Depends(get_storage),
):
    """Upload a document into a KnowledgeBase (stored in MinIO/S3, processed asynchronously)."""
    service = DocumentService(session, storage=storage)
    try:
        doc = await service.upload_document(knowledge_base_id, current_user.id, file)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)
        )

    # Trigger background processing (parse → chunk → embed → Qdrant)
    background_tasks.add_task(
        DocumentProcessor(storage=storage).process_document,
        doc.id,
        knowledge_base_id,
    )

    return DocumentOut.model_validate(doc)


@router.get("/{doc_id}", response_model=DocumentOut)
async def get_document(
    doc_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Get a single document by ID."""
    from backend.infrastructure.persistence.document_repository import DocumentRepository
    repo = DocumentRepository(session)
    doc = await repo.get_by_id(doc_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return DocumentOut.model_validate(doc)


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    knowledge_base_id: int | None = Query(None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """List uploaded documents, optionally filtered by knowledge base."""
    service = DocumentService(session)
    docs = await service.list_documents(knowledge_base_id=knowledge_base_id)
    return DocumentListResponse(
        items=[DocumentOut.model_validate(d) for d in docs],
        total=len(docs),
    )


@router.delete("/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    doc_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
    storage: StoragePort = Depends(get_storage),
):
    """Delete a document (DB record + MinIO object + Qdrant vectors)."""
    service = DocumentService(session, storage=storage)
    await service.delete_document(doc_id)
    return None
