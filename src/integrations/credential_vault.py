"""CredentialVault — AES-256-GCM symmetric encryption with key rotation.

Upgraded from Fernet (AES-128-CBC) to AES-256-GCM for production-grade security.
Supports dual-key rotation: current + previous key for seamless migration.

Encrypted format: version_byte (1B) | salt (16B) | nonce (12B) | ciphertext+tag
"""

from __future__ import annotations

import logging
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

from src.core.config import settings
from src.integrations.interfaces import ICredentialVault

logger = logging.getLogger(__name__)

# Current encryption version
_VERSION = b"\x02"  # v2 = AES-256-GCM
_SALT_SIZE = 16
_NONCE_SIZE = 12
_KDF_ITERATIONS = 600_000


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derive a 256-bit key from a passphrase using PBKDF2-HMAC-SHA256."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,  # 256-bit key for AES-256
        salt=salt,
        iterations=_KDF_ITERATIONS,
    )
    return kdf.derive(passphrase.encode())


def _get_current_passphrase() -> str:
    """Return the current encryption passphrase."""
    return settings.CREDENTIAL_ENCRYPTION_KEY or settings.SECRET_KEY


def _get_previous_passphrase() -> str | None:
    """Return the previous encryption passphrase for key rotation."""
    return settings.CREDENTIAL_ENCRYPTION_KEY_PREVIOUS


class CredentialVault(ICredentialVault):
    """Thread-safe AES-256-GCM wrapper with key rotation support.

    Encryption format (per value):
        version (1 byte) | salt (16 bytes) | nonce (12 bytes) | ciphertext + GCM tag

    Key rotation:
        - Encrypts always with the CURRENT key.
        - Decrypts trying CURRENT first, then PREVIOUS (if configured).
        - Callers can detect stale encryption via `needs_reencryption()`.
    """

    def encrypt(self, plain_text: str) -> bytes:
        """Encrypt with the current key using AES-256-GCM."""
        salt = os.urandom(_SALT_SIZE)
        nonce = os.urandom(_NONCE_SIZE)
        key = _derive_key(_get_current_passphrase(), salt)
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, plain_text.encode(), None)
        return _VERSION + salt + nonce + ciphertext

    def decrypt(self, encrypted: bytes) -> str:
        """Decrypt, trying current key first, then previous for rotation."""
        if len(encrypted) < 1 + _SALT_SIZE + _NONCE_SIZE + 1:
            raise ValueError("Encrypted data too short — corrupted or wrong format")

        version = encrypted[0:1]
        if version != _VERSION:
            # Attempt legacy Fernet decryption for backward compatibility
            return self._decrypt_legacy_fernet(encrypted)

        salt = encrypted[1:1 + _SALT_SIZE]
        nonce = encrypted[1 + _SALT_SIZE:1 + _SALT_SIZE + _NONCE_SIZE]
        ciphertext = encrypted[1 + _SALT_SIZE + _NONCE_SIZE:]

        # Try current key
        try:
            key = _derive_key(_get_current_passphrase(), salt)
            aesgcm = AESGCM(key)
            return aesgcm.decrypt(nonce, ciphertext, None).decode()
        except Exception:
            pass

        # Try previous key (rotation support)
        previous = _get_previous_passphrase()
        if previous:
            try:
                key = _derive_key(previous, salt)
                aesgcm = AESGCM(key)
                result = aesgcm.decrypt(nonce, ciphertext, None).decode()
                logger.info("Decrypted with previous key — credential should be re-encrypted")
                return result
            except Exception:
                pass

        logger.error("CredentialVault: decryption failed with all available keys")
        raise ValueError("Failed to decrypt credential — key mismatch or corrupted data")

    def needs_reencryption(self, encrypted: bytes) -> bool:
        """Check if data was encrypted with a non-current key or legacy format."""
        if len(encrypted) < 1:
            return True
        version = encrypted[0:1]
        if version != _VERSION:
            return True  # Legacy Fernet format
        # Try decrypting with current key — if it fails, needs re-encryption
        salt = encrypted[1:1 + _SALT_SIZE]
        nonce = encrypted[1 + _SALT_SIZE:1 + _SALT_SIZE + _NONCE_SIZE]
        ciphertext = encrypted[1 + _SALT_SIZE + _NONCE_SIZE:]
        try:
            key = _derive_key(_get_current_passphrase(), salt)
            aesgcm = AESGCM(key)
            aesgcm.decrypt(nonce, ciphertext, None)
            return False  # Current key works
        except Exception:
            return True  # Encrypted with old key

    @staticmethod
    def _decrypt_legacy_fernet(encrypted: bytes) -> str:
        """Backward compatibility: try decrypting Fernet (v1) data."""
        try:
            import base64
            import hashlib
            from cryptography.fernet import Fernet

            passphrase = _get_current_passphrase()
            raw = hashlib.sha256(passphrase.encode()).digest()
            fernet_key = base64.urlsafe_b64encode(raw)
            f = Fernet(fernet_key)
            result = f.decrypt(encrypted).decode()
            logger.warning("Decrypted legacy Fernet credential — should be re-encrypted with AES-256-GCM")
            return result
        except Exception:
            pass

        # Try with previous key in Fernet format
        previous = _get_previous_passphrase()
        if previous:
            try:
                import base64
                import hashlib
                from cryptography.fernet import Fernet

                raw = hashlib.sha256(previous.encode()).digest()
                fernet_key = base64.urlsafe_b64encode(raw)
                f = Fernet(fernet_key)
                result = f.decrypt(encrypted).decode()
                logger.warning("Decrypted legacy Fernet credential with previous key")
                return result
            except Exception:
                pass

        raise ValueError("Failed to decrypt legacy Fernet credential — key mismatch")
