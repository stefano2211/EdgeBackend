"""Auth strategies — map raw credentials to Docker env vars.

Each strategy knows how to validate a payload and translate it into the
key names expected by the target MCP server container.
"""

from __future__ import annotations

import logging

from src.integrations.interfaces import IAuthStrategy

logger = logging.getLogger(__name__)


class TokenAuthStrategy(IAuthStrategy):
    """Simple bearer / PAT / API-key strategy."""

    def validate(self, credentials: dict[str, str]) -> bool:
        return bool(credentials.get("token"))

    def to_env_vars(
        self, credentials: dict[str, str], mapping: dict[str, str]
    ) -> dict[str, str]:
        # mapping: {"GITHUB_PERSONAL_ACCESS_TOKEN": "token"}
        # credentials: {"token": "ghp_xxx"}
        env: dict[str, str] = {}
        for env_var, cred_key in mapping.items():
            if cred_key in credentials:
                env[env_var] = credentials[cred_key]
        return env


class OAuth2AuthStrategy(IAuthStrategy):
    """OAuth 2.0 refresh-token strategy (e.g. Gmail)."""

    REQUIRED = {"refresh_token", "client_id", "client_secret"}

    def validate(self, credentials: dict[str, str]) -> bool:
        missing = self.REQUIRED - set(credentials.keys())
        if missing:
            logger.warning("OAuth2 credentials missing fields: %s", missing)
            return False
        return True

    def to_env_vars(
        self, credentials: dict[str, str], mapping: dict[str, str]
    ) -> dict[str, str]:
        # mapping: {"GMAIL_REFRESH_TOKEN": "refresh_token", ...}
        env: dict[str, str] = {}
        for env_var, cred_key in mapping.items():
            if cred_key in credentials:
                env[env_var] = credentials[cred_key]
        return env


class BasicAuthStrategy(IAuthStrategy):
    """User + password strategy."""

    def validate(self, credentials: dict[str, str]) -> bool:
        return bool(credentials.get("username") and credentials.get("password"))

    def to_env_vars(
        self, credentials: dict[str, str], mapping: dict[str, str]
    ) -> dict[str, str]:
        env: dict[str, str] = {}
        for env_var, cred_key in mapping.items():
            if cred_key in credentials:
                env[env_var] = credentials[cred_key]
        return env


class ApiKeyAuthStrategy(IAuthStrategy):
    """Generic API-key strategy (e.g. Notion)."""

    def validate(self, credentials: dict[str, str]) -> bool:
        return bool(credentials.get("api_key"))

    def to_env_vars(
        self, credentials: dict[str, str], mapping: dict[str, str]
    ) -> dict[str, str]:
        env: dict[str, str] = {}
        for env_var, cred_key in mapping.items():
            if cred_key in credentials:
                env[env_var] = credentials[cred_key]
        return env


class NoAuthStrategy(IAuthStrategy):
    """For public / local servers that need no credentials."""

    def validate(self, credentials: dict[str, str]) -> bool:
        return True

    def to_env_vars(
        self, credentials: dict[str, str], mapping: dict[str, str]
    ) -> dict[str, str]:
        return {}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

AUTH_STRATEGIES: dict[str, IAuthStrategy] = {
    "token": TokenAuthStrategy(),
    "oauth2": OAuth2AuthStrategy(),
    "basic": BasicAuthStrategy(),
    "api_key": ApiKeyAuthStrategy(),
    "none": NoAuthStrategy(),
}


def get_strategy(auth_type: str) -> IAuthStrategy:
    strategy = AUTH_STRATEGIES.get(auth_type)
    if not strategy:
        raise ValueError(f"Unknown auth_type '{auth_type}'. Supported: {list(AUTH_STRATEGIES.keys())}")
    return strategy
