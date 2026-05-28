"""Gmail OAuth2 flow helpers.

Generates the authorization URL with PKCE and exchanges the
authorization code for a refresh token.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
from typing import Any

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.modify"


def generate_pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, code_challenge)."""
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).decode().rstrip("=")
    return verifier, challenge


def build_authorization_url(
    client_id: str,
    redirect_uri: str,
    state: str,
    code_challenge: str,
) -> str:
    """Build the Google OAuth2 authorization URL."""
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": GMAIL_SCOPE,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "access_type": "offline",
        "prompt": "consent",
    }
    from urllib.parse import urlencode
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_code(
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
    code_verifier: str,
) -> dict[str, Any]:
    """Exchange authorization code for tokens.

    Returns a dict with keys like: access_token, refresh_token, expires_in, token_type.
    Raises RuntimeError on failure.
    """
    import httpx

    payload = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(GOOGLE_TOKEN_URL, data=payload)

    data = resp.json()

    if resp.status_code != 200:
        error = data.get("error", "unknown")
        error_desc = data.get("error_description", "")
        logger.error("Google token exchange failed: %s — %s", error, error_desc)
        raise RuntimeError(f"Google OAuth error: {error} — {error_desc}")

    logger.info("Google token exchange succeeded. Has refresh_token=%s", bool(data.get("refresh_token")))
    return data
