"""CredentialVault — Fernet symmetric encryption.

Reuses the exact same key-derivation logic as CredentialService so that
existing SECRET_KEY-based Fernet instances remain compatible.
"""

from __future__ import annotations

import base64
import hashlib
import logging

from cryptography.fernet import Fernet

from src.core.config import settings
from src.integrations.interfaces import ICredentialVault

logger = logging.getLogger(__name__)


def _derive_fernet_key() -> bytes:
    """Derive a URL-safe 32-byte Fernet key from the app SECRET_KEY."""
    raw = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    return base64.urlsafe_b64encode(raw)


_fernet = Fernet(_derive_fernet_key())


class CredentialVault(ICredentialVault):
    """Thread-safe Fernet wrapper. Stateless — safe to instantiate anywhere."""

    def encrypt(self, plain_text: str) -> bytes:
        return _fernet.encrypt(plain_text.encode())

    def decrypt(self, encrypted: bytes) -> str:
        try:
            return _fernet.decrypt(encrypted).decode()
        except Exception:
            logger.exception("CredentialVault decrypt failed")
            raise ValueError("Failed to decrypt credential — key mismatch or corrupted data")
