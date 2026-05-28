"""Domain interfaces (ABCs) for the integrations module.

All high-level services depend on these abstractions, not on concrete
implementations.  This keeps the codebase testable and aligned with SOLID.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


# ---------------------------------------------------------------------------
# Credential vault
# ---------------------------------------------------------------------------

class ICredentialVault(ABC):
    """Encrypt / decrypt plain-text secrets."""

    @abstractmethod
    def encrypt(self, plain_text: str) -> bytes:
        """Return ciphertext bytes."""
        ...

    @abstractmethod
    def decrypt(self, encrypted: bytes) -> str:
        """Return original plain text."""
        ...


# ---------------------------------------------------------------------------
# Stdio runner (replaces IDockerRunner)
# ---------------------------------------------------------------------------

class IStdioRunner(ABC):
    """Lifecycle management for MCP server stdio processes."""

    @abstractmethod
    def start(
        self,
        command: str,
        args: list[str] | None,
        env: dict[str, str] | None,
    ) -> Any:
        """Launch a stdio process and return a handle (e.g. ProcessInfo)."""
        ...

    @abstractmethod
    def stop(self, pid: int) -> None:
        """Gracefully stop a running process."""
        ...

    @abstractmethod
    def is_running(self, pid: int) -> bool:
        """Return True if the process is still alive."""
        ...


# ---------------------------------------------------------------------------
# Auth strategies
# ---------------------------------------------------------------------------

class IAuthStrategy(ABC):
    """Transform raw user credentials into a flat dict for storage / injection."""

    @abstractmethod
    def validate(self, credentials: dict[str, str]) -> bool:
        """Return True if the payload contains every required field."""
        ...

    @abstractmethod
    def to_db_keys(self, credentials: dict[str, str]) -> dict[str, str]:
        """Return a flat dict ready for DB storage (keys = credential_key)."""
        ...

    @abstractmethod
    def supports_refresh(self) -> bool:
        """Whether this strategy supports OAuth2-style token refresh."""
        ...


# ---------------------------------------------------------------------------
# Repositories (async)
# ---------------------------------------------------------------------------

class IIntegrationCatalogRepository(ABC):
    """Persistence for IntegrationCatalog."""

    @abstractmethod
    async def get_by_slug(self, slug: str) -> Any | None: ...

    @abstractmethod
    async def list_all(self) -> list[Any]: ...


class IIntegrationInstanceRepository(ABC):
    """Persistence for IntegrationInstance."""

    @abstractmethod
    async def get_by_id(self, instance_id: int) -> Any | None: ...

    @abstractmethod
    async def create(self, obj: Any) -> Any: ...

    @abstractmethod
    async def update(self, obj: Any) -> Any: ...

    @abstractmethod
    async def delete(self, obj: Any) -> None: ...

    @abstractmethod
    async def save_credentials(self, instance_id: int, encrypted: dict[str, bytes]) -> None: ...

    @abstractmethod
    async def list_for_user(self, user_id: int) -> list[Any]: ...
