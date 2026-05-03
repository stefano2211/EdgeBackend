"""Auth endpoints: login and register."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.auth import UserLogin, UserRegister, TokenResponse
from src.core.deps import get_db
from src.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    service = AuthService(session)
    token = await service.login(credentials.email, credentials.password)
    return TokenResponse(access_token=token)


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    data: UserRegister,
    session: AsyncSession = Depends(get_db),
):
    service = AuthService(session)
    user = await service.register(data.username, data.email, data.password)
    return {"id": user.id, "username": user.username, "email": user.email}
