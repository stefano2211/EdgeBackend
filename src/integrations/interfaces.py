"""Domain interfaces (ABCs) for the integrations module.

All high-level services depend on these abstractions, not on concrete
implementations.  This keeps the codebase testable and aligned with SOLID.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
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
# Docker runner
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DockerConfig:
    """Immutable description of a container to run."""

    image: str
    name: str
    env: dict[str, str]
    network: str
    command: list[str] | None = None
    ports: dict[int, int] | None = None
    restart_policy: dict[str, Any] | None = None


@dataclass(frozen=True)
class ContainerInfo:
    """Lightweight snapshot of a running (or failed) container."""

    name: str
    status: str
    endpoint: str | None = None
    error: str | None = None


class IDockerRunner(ABC):
    """Lifecycle management for MCP server containers."""

    @abstractmethod
    async def create_and_start(self, cfg: DockerConfig) -> ContainerInfo:
        """Pull image if missing, create container, start it, return snapshot."""
        ...

    @abstractmethod
    async def stop(self, name: str) -> None:
        """Gracefully stop a running container."""
        ...

    @abstractmethod
    async def remove(self, name: str) -> None:
        """Remove a stopped container permanently."""
        ...

    @abstractmethod
    async def inspect(self, name: str) -> ContainerInfo:
        """Return current snapshot (status + endpoint)."""
        ...


# ---------------------------------------------------------------------------
# Auth strategies
# ---------------------------------------------------------------------------

class IAuthStrategy(ABC):
    """Transform raw user credentials into Docker env-vars."""

    @abstractmethod
    def validate(self, credentials: dict[str, str]) -> bool:
        """Return True if the payload contains every required field."""
        ...

    @abstractmethod
    def to_env_vars(
        self, credentials: dict[str, str], mapping: dict[str, str]
    ) -> dict[str, str]:
        """Map internal credential keys to environment variable names."""
        ...


# ---------------------------------------------------------------------------
# MCP server configuration factory
# ---------------------------------------------------------------------------

class IMCPServerConfig(ABC):
    """Produce Docker configuration for a specific MCP server flavour."""

    @abstractmethod
    def get_docker_config(
        self,
        instance: Any,  # IntegrationInstance (avoid circular import)
        env_vars: dict[str, str],
    ) -> DockerConfig:
        """Build a DockerConfig tailored to this server type."""
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
