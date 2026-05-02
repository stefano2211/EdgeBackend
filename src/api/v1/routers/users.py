"""User endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.auth import UserOut
from src.core.database import AsyncSessionLocal
from src.core.deps import get_current_user_id
from src.persistencia.repositories.user_repository import UserRepository

router = APIRouter(prefix="/users", tags=["users"])


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


@router.get("/me", response_model=UserOut)
async def get_me(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> UserOut:
    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
