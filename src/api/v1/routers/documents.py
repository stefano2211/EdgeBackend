"""Documents router — upload endpoint with background processing."""

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.document import DocumentOut
from src.core.config import settings
from src.core.database import AsyncSessionLocal
from src.core.deps import get_current_user_id
from src.services.knowledge_service import KnowledgeService
from src.services.document_processor import DocumentProcessor

router = APIRouter(prefix="/documents", tags=["documents"])


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


@router.post("/upload", response_model=DocumentOut, status_code=201)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    knowledge_base_id: int = Form(...),
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    # Validate file size
    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Max size: {settings.MAX_UPLOAD_SIZE} bytes",
        )

    # Save file to disk
    import os, uuid as uuid_mod
    ext = os.path.splitext(file.filename or "")[1]
    file_id = str(uuid_mod.uuid4())
    upload_path = os.path.join(settings.UPLOAD_DIR, f"{file_id}{ext}")
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    with open(upload_path, "wb") as f:
        f.write(content)

    # Create document record
    service = KnowledgeService(session)
    doc = await service.create_document(knowledge_base_id, user_id, file.filename or "unknown")

    # Update file_id to match our generated UUID
    doc.file_id = file_id
    await session.commit()
    await session.refresh(doc)

    # Trigger background processing (parse → chunk → embed → Qdrant)
    background_tasks.add_task(
        DocumentProcessor().process_document,
        doc.id,
        knowledge_base_id,
    )

    return DocumentOut.model_validate(doc)
