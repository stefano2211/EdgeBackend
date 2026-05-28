"""FastAPI dependency injection utilities."""

from typing import AsyncGenerator, Optional

from fastapi import Depends, HTTPException, status, Header, Query, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import AsyncSessionLocal
from backend.core.security import decode_access_token
from backend.core.exceptions import AuthenticationError, PermissionDenied
from backend.persistencia.repositories.user_repository import UserRepository
from backend.persistencia.models.user import User
from backend.core.config import settings

security = HTTPBearer(auto_error=False)


# ── Storage dependency ──

def get_storage():
    """Yield a MinIO storage repository instance.

    Can be swapped for a mock in tests by overriding this dependency.
    Lazy import prevents startup failure when minio is not installed.
    """
    from backend.persistencia.storage import MinioStorageRepository
    return MinioStorageRepository()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def _get_user_from_token_str(token_str: str, session: AsyncSession) -> User:
    """Shared helper: decode JWT and return User.

    Supports both token formats:
      - NEW: sub = user email  (e.g. "admin@example.com")
      - OLD: sub = user id     (e.g. "1")
    """
    import logging
    logger = logging.getLogger("auth.debug")

    # Strip whitespace just in case
    token_str = token_str.strip()

    payload = decode_access_token(token_str)
    if not payload:
        # Decode WITHOUT verification to see WHY it failed
        try:
            from jose import jwt as _jwt
            raw = _jwt.get_unverified_claims(token_str)
            logger.warning(
                "Token rejected by decode_access_token. "
                "Unverified claims: sub=%s, exp=%s",
                raw.get("sub"), raw.get("exp"),
            )
            # Check expiry manually
            import time
            exp = raw.get("exp", 0)
            now = time.time()
            if now > exp:
                logger.warning(
                    "TOKEN EXPIRED: expired %.0f seconds ago (%.1f minutes)",
                    now - exp, (now - exp) / 60,
                )
        except Exception as diag_err:
            logger.warning("Could not diagnose token: %s", diag_err)

        raise AuthenticationError("Invalid or expired token")

    sub = payload.get("sub")
    if not sub:
        raise AuthenticationError("Invalid token payload")

    logger.info("Token decoded OK — sub=%s", sub)

    repo = UserRepository(session)

    # Try email lookup first (new tokens)
    user = await repo.get_by_email(sub)

    # Fallback: treat sub as numeric user ID (old tokens)
    if not user and sub.isdigit():
        user = await repo.get_by_id(int(sub))

    if not user:
        logger.warning("No user found for sub=%s", sub)
        raise HTTPException(status_code=404, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    logger.info("Authenticated user: id=%s email=%s", user.id, user.email)
    return user


async def get_current_user(
    session: AsyncSession = Depends(get_db),
    token: HTTPAuthorizationCredentials | None = Depends(security)
) -> User:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await _get_user_from_token_str(token.credentials, session)


async def get_current_user_flexible(
    request: Request,
    session: AsyncSession = Depends(get_db),
    token: str | None = Query(None),
) -> User:
    """Auth dependency that accepts Bearer header OR ?token= query param (for SSE)."""
    if token:
        return await _get_user_from_token_str(token, session)
        
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return await _get_user_from_token_str(auth_header[7:], session)
        
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> None:
    """Dependency that enforces the current user has admin role."""
    if getattr(current_user, "role", None) != "admin":
        raise PermissionDenied("Admin access required")


def verify_api_key(x_api_key: str | None = Header(None, alias="X-API-Key")) -> str:
    """Dependency for external event ingestion via API key."""
    if not x_api_key or x_api_key != settings.EVENT_INGEST_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key",
        )
    return x_api_key
