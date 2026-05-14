"""MCP Server configuration factory.

Produces DockerConfig objects for different source types without
polluting the service layer with Docker details.
"""

from __future__ import annotations

import logging

from src.integrations.interfaces import DockerConfig, IMCPServerConfig
from src.integrations.models import IntegrationInstance

logger = logging.getLogger(__name__)


class OfficialMCPServer(IMCPServerConfig):
    """MCP servers installed via npx / uvx (Node / Python ecosystem)."""

    def get_docker_config(
        self,
        instance: IntegrationInstance,
        env_vars: dict[str, str],
    ) -> DockerConfig:
        catalog = instance.catalog
        command: list[str] | None = None
        if catalog.official_command and catalog.official_args:
            command = [catalog.official_command] + catalog.official_args

        # Default to node:20-alpine for npx, python:3.13-slim for uvx
        image = (
            "python:3.13-slim"
            if catalog.official_command == "uvx"
            else "node:20-alpine"
        )

        return DockerConfig(
            image=image,
            name=instance.container_name or f"mcp-{catalog.slug}-u{instance.user_id}-i{instance.id}",
            env=env_vars,
            network="edge-network",
            command=command,
        )


class CustomMCPServer(IMCPServerConfig):
    """Our own Dockerised MCP servers (e.g. Gmail)."""

    def get_docker_config(
        self,
        instance: IntegrationInstance,
        env_vars: dict[str, str],
    ) -> DockerConfig:
        catalog = instance.catalog
        if not catalog.docker_image:
            raise ValueError(f"Custom catalog '{catalog.slug}' missing docker_image")

        return DockerConfig(
            image=catalog.docker_image,
            name=instance.container_name or f"mcp-{catalog.slug}-u{instance.user_id}-i{instance.id}",
            env=env_vars,
            network="edge-network",
            command=catalog.docker_command,
        )


class RestBridgeMCPServer(IMCPServerConfig):
    """REST APIs bridged via AI discovery — no container needed."""

    def get_docker_config(
        self,
        instance: IntegrationInstance,
        env_vars: dict[str, str],
    ) -> DockerConfig:
        raise NotImplementedError("REST bridge does not use Docker containers")


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_SERVER_CONFIGS: dict[str, IMCPServerConfig] = {
    "official": OfficialMCPServer(),
    "custom": CustomMCPServer(),
    "rest_bridge": RestBridgeMCPServer(),
}


def create(source_type: str) -> IMCPServerConfig:
    cfg = _SERVER_CONFIGS.get(source_type)
    if not cfg:
        raise ValueError(f"Unknown source_type '{source_type}'")
    return cfg
