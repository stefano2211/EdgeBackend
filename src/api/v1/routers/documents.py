"""Documents router — stub (Fase 5)."""

from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload")
async def upload_document():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Document upload will be implemented in Fase 5",
    )
