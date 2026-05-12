"""Credential service — Fernet encryption for reactive agent secrets.

Uses the application SECRET_KEY (padded/hashed to 32 bytes) as the
symmetric encryption key.  Credentials are stored as Fernet ciphertext
in the database and only decrypted at the moment a sub-agent requests
them via the `get_secret_credential` tool.
"""

from __future__ import annotations

import base64
import hashlib
import logging

from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.persistencia.models.reactive_credential import ReactiveCredential
from src.persistencia.repositories.reactive_credential_repository import (
    ReactiveCredentialRepository,
)

logger = logging.getLogger(__name__)


def _derive_fernet_key() -> bytes:
    """Derive a URL-safe 32-byte Fernet key from the app SECRET_KEY."""
    raw = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return base64.urlsafe_b64encode(raw)


_fernet = Fernet(_derive_fernet_key())


class CredentialService:
    """CRUD + encrypt/decrypt for reactive credentials."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = ReactiveCredentialRepository(session)

    # ── Public API ──

    async def create(
        self,
        user_id: int,
        name: str,
        key_identifier: str,
        plain_value: str,
        description: str | None = None,
    ) -> ReactiveCredential:
        encrypted = _fernet.encrypt(plain_value.encode())
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
            return _fernet.decrypt(cred.encrypted_value).decode()
        except Exception:
            logger.exception("Failed to decrypt credential key=%s", key_identifier)
            return None
