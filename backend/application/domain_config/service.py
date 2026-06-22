"""Domain configuration service — encapsulates CRUD and business rules for user-defined domains."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.exceptions import ConflictError, NotFoundError
from backend.domain.models.domain_config import DomainConfig
from backend.infrastructure.persistence.domain_config_repository import DomainConfigRepository
from backend.core._helpers import apply_patch, commit_and_refresh


class DomainConfigService:
    """Business-logic layer for domain configurations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = DomainConfigRepository(session)

    async def list_for_user(self, user_id: int) -> list[DomainConfig]:
        return await self.repo.list_for_user(user_id)

    async def get_for_user(self, domain_id: int, user_id: int) -> DomainConfig:
        domain = await self.repo.get_by_id(domain_id)
        if not domain or domain.user_id != user_id:
            raise NotFoundError(f"Domain {domain_id} not found")
        return domain

    async def create(
        self, user_id: int, name: str, display_name: str, detection_rules: dict | None, is_default: bool
    ) -> DomainConfig:
        existing = await self.repo.get_by_name_for_user(user_id, name)
        if existing:
            raise ConflictError(f"Domain '{name}' already exists")

        domain = DomainConfig(
            user_id=user_id,
            name=name,
            display_name=display_name,
            detection_rules=detection_rules,
            is_default=is_default,
        )
        await self.repo.create(domain)
        await commit_and_refresh(self.session, domain)
        return domain

    async def update(
        self, domain_id: int, user_id: int, data: dict
    ) -> DomainConfig:
        domain = await self.get_for_user(domain_id, user_id)
        apply_patch(domain, data)
        await commit_and_refresh(self.session, domain)
        return domain

    async def delete(self, domain_id: int, user_id: int) -> None:
        domain = await self.get_for_user(domain_id, user_id)
        await self.repo.delete(domain)
        await self.session.commit()
