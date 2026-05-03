"""Auth endpoints: login, register, and current user."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.auth import UserLogin, UserRegister, TokenResponse, UserOut
from src.core.deps import get_db, get_current_user_id
from src.services.auth_service import AuthService
from src.persistencia.repositories.user_repository import UserRepository

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    service = AuthService(session)
    token = await service.login(credentials.email, credentials.password)
    return TokenResponse(access_token=token)


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(
    data: UserRegister,
    session: AsyncSession = Depends(get_db),
):
    service = AuthService(session)
    user = await service.register(data.username, data.email, data.password)
    return UserOut.model_validate(user)


@router.get("/me", response_model=UserOut)
async def get_current_auth_user(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> UserOut:
    repo = UserRepository(session)
    user = await repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserOut.model_validate(user)
