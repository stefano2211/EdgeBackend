"""Credential service — AES-256-GCM encryption for reactive agent secrets.

Uses the unified CredentialVault (from integrations layer) for production-grade
encryption.  Credentials are stored as AES-256-GCM ciphertext in the database
and only decrypted at the moment a sub-agent requests reactive automation tools.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from backend.application.integrations.vault import CredentialVault
from backend.domain.models.reactive_credential import ReactiveCredential
from backend.infrastructure.persistence.reactive_credential_repository import (
    ReactiveCredentialRepository,
)

logger = logging.getLogger(__name__)


class CredentialService:
    """CRUD + encrypt/decrypt for reactive credentials using AES-256-GCM."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = ReactiveCredentialRepository(session)
        self._vault = CredentialVault()

    # ── Public API ──

    async def create(
        self,
        user_id: int,
        name: str,
        key_identifier: str,
        plain_value: str,
        description: str | None = None,
    ) -> ReactiveCredential:
        encrypted = self._vault.encrypt(plain_value)
        cred = ReactiveCredential(
            user_id=user_id,
            name=name,
            key_identifier=key_identifier.upper().replace(" ", "_"),
            encrypted_value=encrypted,
            description=description,
        )
        await self._repo.create(cred)
        await self._session.commit()
        await self._session.refresh(cred)
        logger.info("Created credential '%s' (key=%s) for user %s", name, cred.key_identifier, user_id)
        return cred

    async def list_for_user(self, user_id: int) -> list[ReactiveCredential]:
        return await self._repo.list_by_user(user_id)

    async def delete(self, cred_id: int, user_id: int) -> bool:
        cred = await self._repo.get_by_id_for_user(cred_id, user_id)
        if not cred:
            return False
        await self._repo.delete(cred)
        await self._session.commit()
        logger.info("Deleted credential id=%s for user %s", cred_id, user_id)
        return True

    async def get_decrypted_value(self, key_identifier: str) -> str | None:
        """Decrypt and return the secret. Used only by agent tools."""
        cred = await self._repo.get_by_key(key_identifier.upper())
        if not cred:
            return None
        try:
            return self._vault.decrypt(cred.encrypted_value)
        except Exception:
            logger.exception("Failed to decrypt credential key=%s", key_identifier)
            return None
