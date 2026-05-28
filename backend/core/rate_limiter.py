"""Sliding-window rate limiter backed by Redis.

Uses Redis INCR + EXPIRE for O(1) rate limit checks per key.
"""

from __future__ import annotations

import logging
from typing import Optional

from backend.core.config import settings

logger = logging.getLogger(__name__)

# Lazy redis client — imported on first use to avoid startup failures
_redis_client: Optional[object] = None


def _get_redis():
    global _redis_client
    if _redis_client is None:
        import redis.asyncio as redis
        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


class SlidingWindowRateLimiter:
    """Rate limiter using a simple Redis-based counter window.

    Not a true sliding window (that would require sorted sets),
    but good enough for webhook protection: it resets every N seconds.
    """

    async def is_allowed(
        self,
        key: str,
        max_requests: int,
        window_seconds: int = 60,
    ) -> bool:
        """Return True if the request is within the rate limit.

        Args:
            key: Unique identifier for the rate limit bucket (e.g. webhook id).
            max_requests: Maximum requests allowed within the window.
            window_seconds: Window size in seconds.
        """
        try:
            r = _get_redis()
            current = await r.incr(key)
            if current == 1:
                # First request in this window — set expiry
                await r.expire(key, window_seconds)
            return current <= max_requests
        except Exception as exc:
            # If Redis is unavailable, be permissive but log a warning
            logger.warning("Rate limiter Redis error (allowing request): %s", exc)
            return True

    async def get_remaining(
        self,
        key: str,
        max_requests: int,
    ) -> int:
        """Return remaining requests in the current window."""
        try:
            r = _get_redis()
            current = await r.get(key)
            if current is None:
                return max_requests
            return max(0, max_requests - int(current))
        except Exception:
            return max_requests
