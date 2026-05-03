"""Admin router — functional user management + analytics."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import AsyncSessionLocal
from src.core.deps import get_current_user_id
from src.core.exceptions import NotFoundError
from src.services.admin_service import AdminService

router = APIRouter(prefix="/admin", tags=["admin"])


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


def _require_admin(service: AdminService, user_id: int):
    """Stub: in production, check JWT claims or DB role."""
    pass


@router.get("/users")
async def list_users(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = AdminService(session)
    _require_admin(service, user_id)
    users = await service.list_users()
    return [
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "role": u.role,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]


@router.patch("/users/{user_id}")
async def update_user(
    user_id_path: int,
    role: str,
    is_active: bool | None = None,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = AdminService(session)
    _require_admin(service, user_id)
    user = await service.update_user_role(user_id_path, role, is_active)
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "is_active": user.is_active,
    }


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id_path: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = AdminService(session)
    _require_admin(service, user_id)
    await service.delete_user(user_id_path)


@router.get("/analytics")
async def get_analytics(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = AdminService(session)
    _require_admin(service, user_id)
    return await service.get_analytics()


@router.get("/settings")
async def get_settings():
    """Return current system configuration (non-sensitive)."""
    from src.core.config import settings
    return {
        "app_env": settings.APP_ENV,
        "default_llm_provider": settings.DEFAULT_LLM_PROVIDER,
        "vllm_enabled": settings.VLLM_ENABLED,
        "ollama_enabled": settings.OLLAMA_ENABLED,
        "embeddings_model": settings.EMBEDDINGS_MODEL,
        "upload_dir": settings.UPLOAD_DIR,
        "max_upload_size": settings.MAX_UPLOAD_SIZE,
    }
