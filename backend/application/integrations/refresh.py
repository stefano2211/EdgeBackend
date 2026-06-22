"""OAuth2 token refresh implementations per provider.

Extensible registry: add a provider by registering its refresh handler.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Coroutine

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Google
# ---------------------------------------------------------------------------

_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


async def refresh_google_token(
    refresh_token: str,
    client_id: str,
    client_secret: str,
) -> dict[str, Any]:
    """Exchange a Google refresh token for a new access token."""
    payload = {
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(_GOOGLE_TOKEN_URL, data=payload)

    data = resp.json()

    if resp.status_code != 200:
        error = data.get("error", "unknown")
        error_desc = data.get("error_description", "")
        logger.error("Google token refresh failed: %s — %s", error, error_desc)
        raise RuntimeError(f"Google OAuth refresh error: {error} — {error_desc}")

    logger.info("Google token refresh succeeded")
    return data


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

RefreshHandler = Callable[..., Coroutine[Any, Any, dict[str, Any]]]

REFRESH_HANDLERS: dict[str, RefreshHandler] = {
    "google": refresh_google_token,
}


def get_refresh_handler(provider: str) -> RefreshHandler | None:
    """Return the refresh handler for a given provider slug, or None."""
    return REFRESH_HANDLERS.get(provider)
