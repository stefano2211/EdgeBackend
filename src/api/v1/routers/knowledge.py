"""Knowledge router — stub (Fase 5)."""

from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.get("")
async def list_knowledge_bases():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Knowledge endpoints will be implemented in Fase 5",
    )


@router.post("")
async def create_knowledge_base():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Knowledge endpoints will be implemented in Fase 5",
    )


@router.get("/{knowledge_id}")
async def get_knowledge_base(knowledge_id: int):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Knowledge endpoints will be implemented in Fase 5",
    )


@router.patch("/{knowledge_id}")
async def update_knowledge_base(knowledge_id: int):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Knowledge endpoints will be implemented in Fase 5",
    )


@router.delete("/{knowledge_id}")
async def delete_knowledge_base(knowledge_id: int):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Knowledge endpoints will be implemented in Fase 5",
    )
