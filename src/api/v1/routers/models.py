"""Models router — stub (Fase 6)."""

from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/models", tags=["models"])


@router.get("")
async def list_models():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Model endpoints will be implemented in Fase 6",
    )


@router.post("")
async def create_model():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Model endpoints will be implemented in Fase 6",
    )


@router.get("/{model_id}")
async def get_model(model_id: int):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Model endpoints will be implemented in Fase 6",
    )


@router.patch("/{model_id}")
async def update_model(model_id: int):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Model endpoints will be implemented in Fase 6",
    )


@router.delete("/{model_id}")
async def delete_model(model_id: int):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Model endpoints will be implemented in Fase 6",
    )
