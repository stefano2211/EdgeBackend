"""Auth strategies — map raw credentials to a flat dict for storage and injection.

Each strategy knows how to validate a payload and translate it into the
key names expected by the target MCP server (via env_prefix).
"""

from __future__ import annotations

import logging

from backend.domain.ports.integration_ports import IAuthStrategy

logger = logging.getLogger(__name__)


class TokenAuthStrategy(IAuthStrategy):
    """Simple bearer / PAT / API-key strategy."""

    REQUIRED = {"token"}

    def validate(self, credentials: dict[str, str]) -> bool:
        return bool(credentials.get("token"))

    def _validate_required(self, credentials: dict[str, str]) -> bool:
        """Return True only if every required key is present and non-empty."""
        missing = self.REQUIRED - set(credentials.keys())
        if missing:
            logger.warning("%s missing fields: %s", self.__class__.__name__, missing)
            return False
        return all(credentials.get(k) for k in self.REQUIRED)

    def to_db_keys(self, credentials: dict[str, str]) -> dict[str, str]:
        """Return flat dict ready for DB."""
        return {"token": credentials["token"]}

    def supports_refresh(self) -> bool:
        return False


class OAuth2AuthStrategy(IAuthStrategy):
    """OAuth 2.0 refresh-token strategy (e.g. Gmail)."""

    REQUIRED = {"refresh_token", "client_id", "client_secret"}

    def validate(self, credentials: dict[str, str]) -> bool:
        missing = self.REQUIRED - set(credentials.keys())
        if missing:
            logger.warning("OAuth2 credentials missing fields: %s", missing)
            return False
        return all(credentials.get(k) for k in self.REQUIRED)

    def to_db_keys(self, credentials: dict[str, str]) -> dict[str, str]:
        """Return flat dict ready for DB.

        For OAuth2 we store:
          - refresh_token (long-lived)
          - client_id
          - client_secret
          - access_token (short-lived, will be refreshed)
        """
        result = {
            "refresh_token": credentials["refresh_token"],
            "client_id": credentials["client_id"],
            "client_secret": credentials["client_secret"],
        }
        # access_token may be present after an initial OAuth flow
        if "access_token" in credentials:
            result["access_token"] = credentials["access_token"]
        return result

    def supports_refresh(self) -> bool:
        return True


class BasicAuthStrategy(IAuthStrategy):
    """User + password strategy."""

    REQUIRED = {"username", "password"}

    def validate(self, credentials: dict[str, str]) -> bool:
        return bool(credentials.get("username") and credentials.get("password"))

    def _validate_required(self, credentials: dict[str, str]) -> bool:
        """Return True only if every required key is present and non-empty."""
        missing = self.REQUIRED - set(credentials.keys())
        if missing:
            logger.warning("%s missing fields: %s", self.__class__.__name__, missing)
            return False
        return all(credentials.get(k) for k in self.REQUIRED)

    def to_db_keys(self, credentials: dict[str, str]) -> dict[str, str]:
        return {
            "username": credentials["username"],
            "password": credentials["password"],
        }

    def supports_refresh(self) -> bool:
        return False


class ConnectionStringAuthStrategy(IAuthStrategy):
    """Connection-string strategy (e.g. PostgreSQL, MongoDB, Redis)."""

    REQUIRED = {"connection_string"}

    def validate(self, credentials: dict[str, str]) -> bool:
        return bool(credentials.get("connection_string"))

    def _validate_required(self, credentials: dict[str, str]) -> bool:
        """Return True only if every required key is present and non-empty."""
        missing = self.REQUIRED - set(credentials.keys())
        if missing:
            logger.warning("%s missing fields: %s", self.__class__.__name__, missing)
            return False
        return all(credentials.get(k) for k in self.REQUIRED)

    def to_db_keys(self, credentials: dict[str, str]) -> dict[str, str]:
        return {"connection_string": credentials["connection_string"]}

    def supports_refresh(self) -> bool:
        return False


class ApiKeyAuthStrategy(IAuthStrategy):
    """Generic API-key strategy (e.g. Notion)."""

    REQUIRED = {"api_key"}

    def validate(self, credentials: dict[str, str]) -> bool:
        return bool(credentials.get("api_key"))

    def _validate_required(self, credentials: dict[str, str]) -> bool:
        """Return True only if every required key is present and non-empty."""
        missing = self.REQUIRED - set(credentials.keys())
        if missing:
            logger.warning("%s missing fields: %s", self.__class__.__name__, missing)
            return False
        return all(credentials.get(k) for k in self.REQUIRED)

    def to_db_keys(self, credentials: dict[str, str]) -> dict[str, str]:
        return {"api_key": credentials["api_key"]}

    def supports_refresh(self) -> bool:
        return False


class NoAuthStrategy(IAuthStrategy):
    """For public / local servers that need no credentials."""

    def validate(self, credentials: dict[str, str]) -> bool:
        return True

    def to_db_keys(self, credentials: dict[str, str]) -> dict[str, str]:
        return {}

    def supports_refresh(self) -> bool:
        return False

    def _validate_required(self, credentials: dict[str, str]) -> bool:
        """No-op: no auth required."""
        return True


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

AUTH_STRATEGIES: dict[str, IAuthStrategy] = {
    "token": TokenAuthStrategy(),
    "oauth2": OAuth2AuthStrategy(),
    "basic": BasicAuthStrategy(),
    "connection_string": ConnectionStringAuthStrategy(),
    "api_key": ApiKeyAuthStrategy(),
    "none": NoAuthStrategy(),
}


def get_strategy(auth_type: str) -> IAuthStrategy:
    strategy = AUTH_STRATEGIES.get(auth_type)
    if not strategy:
        raise ValueError(f"Unknown auth_type '{auth_type}'. Supported: {list(AUTH_STRATEGIES.keys())}")
    return strategy
