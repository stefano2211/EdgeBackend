"""Documents router — upload endpoint with MinIO/S3 storage and background processing."""

import os
import uuid as uuid_mod

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.document import DocumentOut, DocumentListResponse
from src.core.config import settings
from src.core.deps import get_db, get_current_user, get_storage
from src.persistencia.models.user import User
from src.persistencia.storage.storage_port import StoragePort
from src.services.document_service import DocumentService
from src.services.document_processor import DocumentProcessor

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

    # Validate file size
    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Max size: {settings.MAX_UPLOAD_SIZE} bytes",
        )

    # Build S3 key: kb/{knowledge_base_id}/{uuid}.{ext}
    ext = os.path.splitext(file.filename or "")[1]
    file_id = str(uuid_mod.uuid4())
    s3_key = f"kb/{knowledge_base_id}/{file_id}{ext}"

    # Upload to MinIO/S3
    content_type = file.content_type or "application/octet-stream"
    await storage.upload(s3_key, content, content_type=content_type)

    # Create document record with S3 key as file_id
    service = DocumentService(session, storage=storage)
    doc = await service.create_document(
        knowledge_base_id,
        current_user.id,
        file.filename or "unknown",
        s3_key=s3_key,
        content_type=content_type,
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
    from src.persistencia.repositories.document_repository import DocumentRepository
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
