"""Auth service: registration, login, password hashing."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import verify_password, get_password_hash, create_access_token
from src.core.exceptions import AuthenticationError, ConflictError
from src.persistencia.models.user import User
from src.persistencia.repositories.user_repository import UserRepository


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)

    async def register(
        self, username: str, email: str, password: str
    ) -> User:
        # Check for existing user
        existing_email = await self.user_repo.get_by_email(email)
        if existing_email:
            raise ConflictError("Email already registered")

        existing_username = await self.user_repo.get_by_username(username)
        if existing_username:
            raise ConflictError("Username already taken")

        hashed = get_password_hash(password)
        user = User(
            username=username,
            email=email,
            hashed_password=hashed,
        )
        await self.user_repo.create(user)
        await self.session.commit()
        return user

    async def login(self, email: str, password: str) -> str:
        user = await self.user_repo.get_by_email(email)
        if not user or not verify_password(password, user.hashed_password):
            raise AuthenticationError("Invalid email or password")
        if not user.is_active:
            raise AuthenticationError("User is deactivated")

        token = create_access_token({"sub": str(user.id)})
        return token
