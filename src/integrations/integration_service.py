"""IntegrationService — orchestrates the full lifecycle of a user integration.

Responsibilities:
  1. Create / update / delete IntegrationInstance records
  2. Encrypt and store credentials
  3. Spin up / tear down Docker containers
  4. Discover and register MCP tools into the existing ToolConfig system
  5. Handle both proactive (chat) and reactive contexts

Design: depends on abstractions (interfaces) so every collaborator can be
mocked in tests.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.integrations.auth_strategies import get_strategy
from src.integrations.credential_vault import CredentialVault
from src.integrations.docker_runner import DockerRunner
from src.integrations.interfaces import (
    ICredentialVault,
    IDockerRunner,
    IMCPServerConfig,
)
from src.integrations.mcp_server_factory import create as create_server_config
from src.integrations.models import IntegrationCatalog, IntegrationInstance
from src.integrations.repositories import IntegrationCatalogRepository, IntegrationInstanceRepository
from src.integrations.schemas import (
    CredentialsSubmit,
    IntegrationInstanceCreate,
    IntegrationInstanceUpdate,
    SyncResult,
)
from src.services.mcp_service import MCPService

logger = logging.getLogger(__name__)


class IntegrationService:
    """High-level orchestrator.  Stateless aside from injected collaborators."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        credential_vault: ICredentialVault | None = None,
        docker_runner: IDockerRunner | None = None,
    ) -> None:
        self._session = session
        self._catalog_repo = IntegrationCatalogRepository(session)
        self._instance_repo = IntegrationInstanceRepository(session)
        self._vault = credential_vault or CredentialVault()
        self._docker = docker_runner or DockerRunner()
        self._mcp_service = MCPService()

    # ------------------------------------------------------------------
    # Instance CRUD
    # ------------------------------------------------------------------

    async def create_instance(
        self, user_id: int, data: IntegrationInstanceCreate
    ) -> IntegrationInstance:
        catalog = await self._catalog_repo.get_by_slug(data.catalog_slug)
        if not catalog:
            raise ValueError(f"Catalog '{data.catalog_slug}' not found")
        if not catalog.is_enabled:
            raise ValueError(f"Catalog '{data.catalog_slug}' is disabled")

        instance = IntegrationInstance(
            user_id=user_id,
            catalog_id=catalog.id,
            instance_name=data.instance_name,
            available_in_chat=data.available_in_chat,
            available_in_reactive=data.available_in_reactive,
            container_name=f"mcp-{catalog.slug}-u{user_id}-tmp",
        )
        # container_name is a placeholder until we have the real id
        instance = await self._instance_repo.create(instance)

        # Update with the real id for a deterministic name
        instance.container_name = f"mcp-{catalog.slug}-u{user_id}-i{instance.id}"
        await self._instance_repo.update(instance)

        logger.info(
            "Created integration instance id=%s catalog=%s user=%s",
            instance.id,
            catalog.slug,
            user_id,
        )
        return instance

    async def get_instance(self, instance_id: int, user_id: int) -> IntegrationInstance:
        instance = await self._instance_repo.get_by_id_for_user(instance_id, user_id)
        if not instance:
            raise ValueError(f"Instance {instance_id} not found")
        return instance

    async def list_instances(self, user_id: int) -> list[IntegrationInstance]:
        return await self._instance_repo.list_for_user(user_id)

    async def update_instance(
        self, instance_id: int, user_id: int, data: IntegrationInstanceUpdate
    ) -> IntegrationInstance:
        instance = await self.get_instance(instance_id, user_id)
        update_dict = data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(instance, field, value)
        await self._instance_repo.update(instance)
        logger.info("Updated integration instance id=%s", instance_id)
        return instance

    async def delete_instance(self, instance_id: int, user_id: int) -> None:
        instance = await self.get_instance(instance_id, user_id)

        # 1. Tear down container
        if instance.container_name:
            try:
                await self._docker.stop(instance.container_name)
                await self._docker.remove(instance.container_name)
            except Exception:
                logger.warning("Container cleanup failed for '%s'", instance.container_name)

        # 2. Delete DB record (cascades to credentials)
        await self._instance_repo.delete(instance)
        logger.info("Deleted integration instance id=%s", instance_id)

    # ------------------------------------------------------------------
    # Setup guide
    # ------------------------------------------------------------------

    async def get_setup_guide(self, instance_id: int, user_id: int) -> dict[str, Any]:
        instance = await self.get_instance(instance_id, user_id)
        catalog = instance.catalog
        required_fields = list(catalog.auth_env_var_mapping.values())
        return {
            "catalog_name": catalog.name,
            "setup_guide_markdown": catalog.auth_setup_guide_markdown or "No guide available.",
            "required_fields": required_fields,
            "auth_type": catalog.auth_type,
        }

    # ------------------------------------------------------------------
    # Credentials submission + container launch
    # ------------------------------------------------------------------

    async def submit_credentials(
        self, instance_id: int, user_id: int, data: CredentialsSubmit
    ) -> IntegrationInstance:
        instance = await self.get_instance(instance_id, user_id)
        catalog = instance.catalog

        # 1. Validate credentials
        strategy = get_strategy(catalog.auth_type)
        if not strategy.validate(data.credentials):
            raise ValueError(f"Invalid credentials for auth_type '{catalog.auth_type}'")

        # 2. Encrypt and persist
        encrypted = {
            key: self._vault.encrypt(value)
            for key, value in data.credentials.items()
        }
        await self._instance_repo.save_credentials(instance_id, encrypted)

        # 3. Map to env vars
        env_vars = strategy.to_env_vars(data.credentials, catalog.auth_env_var_mapping)

        # 4. Build image if custom and missing
        if catalog.source_type == "custom" and catalog.docker_image:
            if catalog.slug == "gmail":
                # Build on-demand
                await self._docker.build_image_if_missing(
                    tag=catalog.docker_image,
                    dockerfile_path="src/integrations/docker/gmail-mcp/Dockerfile",
                    build_context=".",
                )

        # 5. Create and start container
        server_config: IMCPServerConfig = create_server_config(catalog.source_type)
        docker_cfg = server_config.get_docker_config(instance, env_vars)

        container_info = await self._docker.create_and_start(docker_cfg)
        if container_info.status == "error":
            instance.container_status = "error"
            await self._instance_repo.update(instance)
            raise RuntimeError(f"Container failed to start: {container_info.error}")

        instance.container_status = container_info.status
        instance.container_endpoint = container_info.endpoint
        await self._instance_repo.update(instance)

        # Allow container DNS to propagate before discovery
        await asyncio.sleep(3)

        logger.info(
            "Credentials submitted and container running for instance id=%s endpoint=%s",
            instance_id,
            instance.container_endpoint,
        )
        return instance

    # ------------------------------------------------------------------
    # Sync tools (MCP discovery → ToolConfig registration)
    # ------------------------------------------------------------------

    async def sync_tools(self, instance_id: int, user_id: int) -> SyncResult:
        instance = await self.get_instance(instance_id, user_id)
        catalog = instance.catalog

        if not instance.container_endpoint:
            raise ValueError("Instance has no container endpoint — submit credentials first")

        # Discover tools from the running MCP server
        try:
            discovered = await self._mcp_service.discover_tools(
                base_url=instance.container_endpoint,
                is_stdio=False,
            )
        except Exception as exc:
            logger.exception("Tool discovery failed for instance %s", instance_id)
            raise RuntimeError(f"Tool discovery failed: {exc}") from exc

        # Register in proactive context
        mcp_source_id = None
        if instance.available_in_chat:
            mcp_source_id = await self._register_in_chat_context(instance, catalog, discovered)

        # Register in reactive context
        reactive_mcp_source_id = None
        if instance.available_in_reactive:
            reactive_mcp_source_id = await self._register_in_reactive_context(
                instance, catalog, discovered
            )

        # Update instance with source IDs
        instance.mcp_source_id = mcp_source_id
        instance.reactive_mcp_source_id = reactive_mcp_source_id
        await self._instance_repo.update(instance)

        total_tools = len(discovered)
        logger.info(
            "Synced instance id=%s: discovered=%s chat_source=%s reactive_source=%s",
            instance_id,
            total_tools,
            mcp_source_id,
            reactive_mcp_source_id,
        )
        return SyncResult(
            tools_discovered=total_tools,
            tools_added=total_tools,
            mcp_source_id=mcp_source_id,
            reactive_mcp_source_id=reactive_mcp_source_id,
        )

    async def _register_in_chat_context(
        self,
        instance: IntegrationInstance,
        catalog: IntegrationCatalog,
        discovered: list[dict],
    ) -> int:
        from src.persistencia.models.tool_config import MCPSource, ToolConfig
        from src.persistencia.repositories.tool_repository import MCPSourceRepository, ToolRepository

        source_repo = MCPSourceRepository(self._session)
        tool_repo = ToolRepository(self._session)

        # Create or reuse MCPSource
        source_name = f"{catalog.slug}-u{instance.user_id}-i{instance.id}"
        source = MCPSource(
            name=source_name,
            description=f"{catalog.name} integration for user {instance.user_id}",
            url=instance.container_endpoint,
            type="sse",
            is_enabled=True,
        )
        await source_repo.create(source)
        await self._session.flush()

        for tool_def in discovered:
            name = tool_def.get("name")
            if not name:
                continue
            tool = ToolConfig(
                name=name,
                description=tool_def.get("description") or "",
                parameter_schema=tool_def.get("parameter_schema")
                or tool_def.get("inputSchema")
                or {},
                config=tool_def.get("config", {"transport": "sse", "url": instance.container_endpoint}),
                source_id=source.id,
                is_enabled=True,
            )
            await tool_repo.create(tool)

        await self._session.commit()
        return source.id

    async def _register_in_reactive_context(
        self,
        instance: IntegrationInstance,
        catalog: IntegrationCatalog,
        discovered: list[dict],
    ) -> int:
        from src.persistencia.models.reactive_mcp_source import ReactiveMCPSource
        from src.persistencia.models.reactive_tool_config import ReactiveToolConfig
        from src.persistencia.repositories.reactive_tool_repository import (
            ReactiveMCPSourceRepository,
            ReactiveToolRepository,
        )

        source_repo = ReactiveMCPSourceRepository(self._session)
        tool_repo = ReactiveToolRepository(self._session)

        source_name = f"{catalog.slug}-u{instance.user_id}-i{instance.id}-reactive"
        source = ReactiveMCPSource(
            name=source_name,
            description=f"{catalog.name} reactive integration for user {instance.user_id}",
            url=instance.container_endpoint,
            type="sse",
            is_enabled=True,
        )
        await source_repo.create(source)
        await self._session.flush()

        for tool_def in discovered:
            name = tool_def.get("name")
            if not name:
                continue
            tool = ReactiveToolConfig(
                name=name,
                description=tool_def.get("description") or "",
                parameter_schema=tool_def.get("parameter_schema")
                or tool_def.get("inputSchema")
                or {},
                config=tool_def.get("config", {"transport": "sse", "url": instance.container_endpoint}),
                source_id=source.id,
                is_enabled=True,
            )
            await tool_repo.create(tool)

        await self._session.commit()
        return source.id

    # ------------------------------------------------------------------
    # Container lifecycle helpers
    # ------------------------------------------------------------------

    async def start_instance(self, instance_id: int, user_id: int) -> IntegrationInstance:
        instance = await self.get_instance(instance_id, user_id)
        if not instance.container_name:
            raise ValueError("Instance has no container name")

        container = await self._docker.inspect(instance.container_name)
        if container.status == "running":
            return instance

        # Re-submit credentials to recreate container
        # (credentials are still in DB, we just need to re-launch)
        # For simplicity, we rebuild env vars from stored credentials
        strategy = get_strategy(instance.catalog.auth_type)
        decrypted = {
            cred.credential_key: self._vault.decrypt(cred.encrypted_value)
            for cred in instance.credentials
        }
        env_vars = strategy.to_env_vars(decrypted, instance.catalog.auth_env_var_mapping)

        server_config = create_server_config(instance.catalog.source_type)
        docker_cfg = server_config.get_docker_config(instance, env_vars)
        info = await self._docker.create_and_start(docker_cfg)

        instance.container_status = info.status
        instance.container_endpoint = info.endpoint
        await self._instance_repo.update(instance)
        return instance

    async def stop_instance(self, instance_id: int, user_id: int) -> IntegrationInstance:
        instance = await self.get_instance(instance_id, user_id)
        if instance.container_name:
            await self._docker.stop(instance.container_name)
        instance.container_status = "stopped"
        await self._instance_repo.update(instance)
        return instance

    async def get_status(self, instance_id: int, user_id: int) -> dict[str, Any]:
        instance = await self.get_instance(instance_id, user_id)
        container = None
        if instance.container_name:
            container_info = await self._docker.inspect(instance.container_name)
            container = {
                "name": container_info.name,
                "status": container_info.status,
                "endpoint": container_info.endpoint,
                "error": container_info.error,
            }
        return {
            "instance": instance,
            "container": container,
        }
