"""OAuth state manager — stores PKCE + metadata in Redis with TTL.

Each OAuth flow gets a random state token that lives for 10 minutes.
The callback endpoint uses this token to recover flow context without
exposing secrets in URLs.
"""

from __future__ import annotations

import json
import logging
import secrets
from typing import Any

import redis.asyncio as redis

from backend.core.config import settings

logger = logging.getLogger(__name__)

# Redis key prefix
_PREFIX = "oauth:state"
_DEFAULT_TTL = 600  # 10 minutes


class OAuthStateManager:
    """Async Redis-backed state store for OAuth flows."""

    def __init__(self) -> None:
        self._redis: redis.Redis | None = None

    async def _client(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
        return self._redis

    async def create(
        self,
        instance_id: int,
        user_id: int,
        client_id: str,
        client_secret: str,
        code_verifier: str,
        provider: str,
        frontend_origin: str | None = None,
        ttl: int = _DEFAULT_TTL,
    ) -> str:
        """Generate a random state, store context in Redis, return the state."""
        state = secrets.token_urlsafe(32)
        payload = {
            "instance_id": instance_id,
            "user_id": user_id,
            "client_id": client_id,
            "client_secret": client_secret,
            "code_verifier": code_verifier,
            "provider": provider,
            "frontend_origin": frontend_origin,
        }
        client = await self._client()
        key = f"{_PREFIX}:{state}"
        await client.setex(key, ttl, json.dumps(payload))
        logger.info("[OAuthState] Stored state=%s instance=%s ttl=%s", state[:8] + "...", instance_id, ttl)
        return state

    async def peek(self, state: str) -> dict[str, Any] | None:
        """Retrieve the stored context without deleting it."""
        client = await self._client()
        key = f"{_PREFIX}:{state}"
        raw = await client.get(key)
        if raw:
            return json.loads(raw)
        return None

    async def get(self, state: str) -> dict[str, Any] | None:
        """Retrieve and delete the stored context (one-time read)."""
        client = await self._client()
        key = f"{_PREFIX}:{state}"
        raw = await client.get(key)
        if raw:
            await client.delete(key)
            logger.info("[OAuthState] Consumed state=%s", state[:8] + "...")
            return json.loads(raw)
        logger.warning("[OAuthState] State not found or expired: %s", state[:8] + "...")
        return None


# Global singleton
_state_manager: OAuthStateManager | None = None


def get_state_manager() -> OAuthStateManager:
    global _state_manager
    if _state_manager is None:
        _state_manager = OAuthStateManager()
    return _state_manager
