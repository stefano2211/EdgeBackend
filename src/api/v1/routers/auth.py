"""Auth endpoints: login, register, and current user."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.auth import UserLogin, UserRegister, TokenResponse, UserOut
from src.core.deps import get_db, get_current_user
from src.services.auth_service import AuthService
from src.persistencia.models.user import User
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
    current_user: User = Depends(get_current_user),
) -> UserOut:
    return UserOut.model_validate(current_user)


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user),
):
    """
    Logout the current user.
    Since the application uses stateless JWTs, the server doesn't invalidate
    the token. The client is responsible for discarding it.
    """
    return {"message": "Successfully logged out"}
