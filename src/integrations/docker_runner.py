"""DockerRunner — lifecycle management for MCP server containers.

Uses the Docker SDK for Python.  Every container is attached to the same
Docker Compose network (`edge-network`) so the backend can reach it by
container name without host-port mapping.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from src.integrations.interfaces import ContainerInfo, DockerConfig, IDockerRunner

logger = logging.getLogger(__name__)


class DockerRunner(IDockerRunner):
    """Concrete Docker runner.  Lazy-imports the SDK to fail gracefully."""

    def __init__(self) -> None:
        self._client: Any | None = None

    def _ensure_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import docker

            self._client = docker.from_env()
            logger.info("DockerRunner connected to Docker daemon")
            return self._client
        except Exception as exc:
            logger.error("Docker SDK unavailable: %s", exc)
            raise RuntimeError(
                "Docker SDK not installed or Docker daemon unreachable. "
                "Ensure 'docker' package is installed and the socket is mounted."
            ) from exc

    async def create_and_start(self, cfg: DockerConfig) -> ContainerInfo:
        """Idempotent creation: if container exists we remove + recreate."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_create_and_start, cfg)

    def _resolve_network(self, client, network_name: str) -> str:
        """Return the exact Docker network name, handling Compose prefixes."""
        try:
            client.networks.get(network_name)
            return network_name
        except Exception:
            pass

        # Fallback: search for a network containing the base name
        # (Docker Compose prepends the project dir, e.g. edgebackend_edge-network)
        for net in client.networks.list():
            if network_name in net.name:
                logger.info("Resolved network '%s' -> '%s'", network_name, net.name)
                return net.name

        # Nothing found — return original and let Docker raise a clear error
        return network_name

    def _sync_create_and_start(self, cfg: DockerConfig) -> ContainerInfo:
        client = self._ensure_client()

        # Remove pre-existing container with same name
        try:
            old = client.containers.get(cfg.name)
            old.stop(timeout=5)
            old.remove(force=True)
            logger.info("Removed pre-existing container '%s'", cfg.name)
        except Exception:
            pass

        resolved_network = self._resolve_network(client, cfg.network)

        run_kwargs: dict[str, Any] = {
            "image": cfg.image,
            "name": cfg.name,
            "environment": cfg.env,
            "network": resolved_network,
            "detach": True,
            "restart_policy": cfg.restart_policy or {"Name": "unless-stopped"},
        }
        if cfg.command:
            run_kwargs["command"] = cfg.command
        if cfg.ports:
            run_kwargs["ports"] = cfg.ports

        try:
            container = client.containers.run(**run_kwargs)
            logger.info(
                "Started container '%s' image=%s network=%s",
                cfg.name,
                cfg.image,
                resolved_network,
            )
            # SSE endpoint is predictable because we control the internal port
            endpoint = f"http://{cfg.name}:8080/sse"
            return ContainerInfo(
                name=cfg.name,
                status="running",
                endpoint=endpoint,
            )
        except Exception as exc:
            logger.exception("Failed to start container '%s'", cfg.name)
            return ContainerInfo(
                name=cfg.name,
                status="error",
                error=str(exc),
            )

    async def stop(self, name: str) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._sync_stop, name)

    def _sync_stop(self, name: str) -> None:
        client = self._ensure_client()
        try:
            container = client.containers.get(name)
            container.stop(timeout=5)
            logger.info("Stopped container '%s'", name)
        except Exception:
            logger.warning("Container '%s' not found or already stopped", name)

    async def remove(self, name: str) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._sync_remove, name)

    def _sync_remove(self, name: str) -> None:
        client = self._ensure_client()
        try:
            container = client.containers.get(name)
            container.remove(force=True)
            logger.info("Removed container '%s'", name)
        except Exception:
            logger.warning("Container '%s' not found or already removed", name)

    async def inspect(self, name: str) -> ContainerInfo:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_inspect, name)

    def _sync_inspect(self, name: str) -> ContainerInfo:
        client = self._ensure_client()
        try:
            container = client.containers.get(name)
            status = container.status  # e.g. 'running', 'exited'
            endpoint = f"http://{name}:8080/sse" if status == "running" else None
            return ContainerInfo(name=name, status=status, endpoint=endpoint)
        except Exception:
            return ContainerInfo(name=name, status="missing", endpoint=None)

    # ------------------------------------------------------------------
    # Image helpers (used on-demand for custom servers)
    # ------------------------------------------------------------------

    async def build_image_if_missing(self, tag: str, dockerfile_path: str, build_context: str) -> bool:
        """Build image if it does not exist locally. Returns True if built or already present."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._sync_build_image_if_missing, tag, dockerfile_path, build_context
        )

    def _sync_build_image_if_missing(self, tag: str, dockerfile_path: str, build_context: str) -> bool:
        client = self._ensure_client()
        try:
            client.images.get(tag)
            logger.info("Docker image '%s' already exists", tag)
            return True
        except Exception:
            pass

        logger.info("Building Docker image '%s' from %s ...", tag, dockerfile_path)
        try:
            client.images.build(
                path=build_context,
                dockerfile=dockerfile_path,
                tag=tag,
                rm=True,
                forcerm=True,
            )
            logger.info("Docker image '%s' built successfully", tag)
            return True
        except Exception as exc:
            logger.exception("Failed to build Docker image '%s'", tag)
            raise RuntimeError(f"Docker build failed for {tag}: {exc}") from exc
