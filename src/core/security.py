"""JWT and password hashing utilities."""

import base64
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import jwt, JWTError

from src.core.config import settings

ALGORITHM = settings.JWT_ALGORITHM
SECRET_KEY = settings.SECRET_KEY


def _prehash(password: str) -> bytes:
    """SHA-256 pre-hash to work around bcrypt's 72-byte password limit.

    Returns 32 raw bytes (well under the 72-byte bcrypt limit) instead of
    64 hex chars, avoiding the passlib/bcrypt 4.1+ compatibility crash.
    """
    return hashlib.sha256(password.encode("utf-8")).digest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    plain_hash = _prehash(plain_password)
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(plain_hash, hashed_bytes)


def get_password_hash(password: str) -> str:
    plain_hash = _prehash(password)
    return bcrypt.hashpw(plain_hash, bcrypt.gensalt()).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
