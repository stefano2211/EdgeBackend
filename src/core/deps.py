"""FastAPI dependency injection utilities."""

from typing import AsyncGenerator, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import AsyncSessionLocal
from src.core.security import decode_access_token
from src.core.exceptions import AuthenticationError, PermissionDenied
from src.persistencia.repositories.user_repository import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_current_user_id(token: str = Depends(oauth2_scheme)) -> int:
    payload = decode_access_token(token)
    if not payload:
        raise AuthenticationError("Invalid or expired token")
    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError("Invalid token payload")
    return int(user_id)


async def require_admin(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Dependency that enforces the current user has admin role."""
    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    if not user or getattr(user, "role", None) != "admin":
        raise PermissionDenied("Admin access required")
