"""Admin router — stub (Fase 7)."""

from fastapi import APIRouter, HTTPException, status

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
async def list_users():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Admin endpoints will be implemented in Fase 7",
    )


@router.patch("/users/{user_id}")
async def update_user(user_id: int):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Admin endpoints will be implemented in Fase 7",
    )


@router.delete("/users/{user_id}")
async def delete_user(user_id: int):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Admin endpoints will be implemented in Fase 7",
    )


@router.get("/analytics")
async def get_analytics():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Admin endpoints will be implemented in Fase 7",
    )


@router.get("/settings")
async def get_settings():
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Admin endpoints will be implemented in Fase 7",
    )
