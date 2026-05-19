"""IntegrationService — orchestrates the full lifecycle of a user integration.

Responsibilities:
  1. Create / update / delete IntegrationInstance records
  2. Encrypt and store credentials
  3. Launch stdio MCP processes (replaces Docker containers)
  4. Discover and register MCP tools into the existing ToolConfig system
  5. Handle both proactive (chat) and reactive contexts

Design: depends on abstractions (interfaces) so every collaborator can be
mocked in tests.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.integrations.auth_strategies import get_strategy
from src.integrations.credentials import CredentialManager
from src.integrations.credential_vault import CredentialVault
from src.integrations.interfaces import ICredentialVault
from src.integrations.models import IntegrationCatalog, IntegrationInstance
from src.integrations.repositories import IntegrationCatalogRepository, IntegrationInstanceRepository
from src.integrations.schemas import (
    CredentialsSubmit,
    IntegrationInstanceCreate,
    IntegrationInstanceUpdate,
    SyncResult,
)
from src.integrations.stdio_runner import StdioRunner
from src.services.mcp_service import MCPService
from src.integrations.credential_audit import log_credential_event, CredentialAction

logger = logging.getLogger(__name__)


class IntegrationService:
    """High-level orchestrator.  Stateless aside from injected collaborators."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        credential_vault: ICredentialVault | None = None,
        stdio_runner: StdioRunner | None = None,
    ) -> None:
        self._session = session
        self._catalog_repo = IntegrationCatalogRepository(session)
        self._instance_repo = IntegrationInstanceRepository(session)
        self._vault = credential_vault or CredentialVault()
        self._stdio = stdio_runner or StdioRunner()
        self._credential_manager = CredentialManager(self._instance_repo, self._vault)
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
        )
        instance = await self._instance_repo.create(instance)

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
        old_chat = instance.available_in_chat
        old_reactive = instance.available_in_reactive

        update_dict = data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(instance, field, value)
        await self._instance_repo.update(instance)
        logger.info("Updated integration instance id=%s", instance_id)

        # Auto-sync if toggles changed and credentials exist
        toggles_changed = (
            old_chat != instance.available_in_chat
            or old_reactive != instance.available_in_reactive
        )
        if toggles_changed and instance.credentials:
            try:
                # Reload instance to ensure fresh state (mcp_source_ids) after any previous commits
                instance = await self.get_instance(instance_id, user_id)
                await self.sync_tools(instance_id, user_id)
            except Exception as exc:
                logger.warning(
                    "Auto-sync failed after toggle for instance id=%s: %s",
                    instance_id,
                    exc,
                )
                # Clean up session state so the endpoint can still return the instance
                await self._session.rollback()

        return instance

    async def delete_instance(self, instance_id: int, user_id: int) -> None:
        instance = await self.get_instance(instance_id, user_id)

        # 1. Stop stdio process if running
        if instance.process_pid:
            try:
                self._stdio.stop(instance.process_pid)
            except Exception:
                logger.warning("Process cleanup failed for pid=%s", instance.process_pid)

        # 2. Delete associated MCP sources
        await self._cleanup_previous_sources(instance)

        # Audit: credential deletion
        try:
            cred_keys = [c.credential_key for c in instance.credentials]
            await log_credential_event(
                self._session,
                CredentialAction.DELETED,
                user_id=user_id,
                instance_id=instance_id,
                credential_key=",".join(cred_keys) if cred_keys else None,
                details=f"Instance deleted, {len(cred_keys)} credentials removed",
            )
        except Exception:
            pass

        # 3. Delete DB record (cascades to credentials)
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
    # Credentials submission + process launch
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

        # 2. Map to DB keys and encrypt
        db_keys = strategy.to_db_keys(data.credentials)
        encrypted = {
            key: self._vault.encrypt(value)
            for key, value in db_keys.items()
        }

        # Handle OAuth2 initial access_token + expiry if present
        expires_at_map: dict[str, Any] | None = None
        if strategy.supports_refresh() and "access_token" in db_keys:
            from datetime import datetime, timedelta, timezone
            expires_at_map = {
                "access_token": datetime.now(timezone.utc) + timedelta(seconds=3300)  # 55 min buffer
            }

        await self._instance_repo.save_credentials(instance_id, encrypted, expires_at_map)

        # 3. Refresh instance to pick up new credentials
        instance = await self.get_instance(instance_id, user_id)

        # 4. Launch stdio process with credentials
        await self._launch_stdio_process(instance)

        logger.info(
            "Credentials submitted and stdio process running for instance id=%s",
            instance_id,
        )

        # Audit: credential creation
        try:
            await log_credential_event(
                self._session,
                CredentialAction.CREATED,
                user_id=user_id,
                instance_id=instance_id,
                credential_key=",".join(data.credentials.keys()),
                details=f"Credentials submitted for catalog '{instance.catalog.slug}'",
            )
        except Exception:
            pass

        return instance

    # ------------------------------------------------------------------
    # OAuth completion
    # ------------------------------------------------------------------

    async def complete_oauth(
        self,
        code: str,
        state: str,
    ) -> IntegrationInstance:
        """Finish an OAuth2 flow: exchange code, store tokens, launch process."""
        from src.integrations.oauth.gmail_flow import exchange_code
        from src.integrations.oauth.state_manager import get_state_manager
        from src.core.config import settings

        # Recover context from Redis (one-time read)
        state_manager = get_state_manager()
        ctx = await state_manager.get(state)
        if not ctx:
            raise ValueError("Invalid or expired OAuth state — the authorization session may have timed out. Please try again.")

        instance_id = ctx["instance_id"]
        user_id = ctx["user_id"]

        instance = await self.get_instance(instance_id, user_id)
        catalog = instance.catalog

        # Exchange code for tokens
        token_data = await exchange_code(
            client_id=ctx["client_id"],
            client_secret=ctx["client_secret"],
            code=code,
            redirect_uri=settings.OAUTH_REDIRECT_URL,
            code_verifier=ctx["code_verifier"],
        )

        refresh_token = token_data.get("refresh_token")
        if not refresh_token:
            raise RuntimeError("Google did not return a refresh token. Ensure 'prompt=consent' was used.")

        # Build credentials payload
        credentials_payload = {
            "refresh_token": refresh_token,
            "client_id": ctx["client_id"],
            "client_secret": ctx["client_secret"],
            "access_token": token_data.get("access_token", ""),
        }

        # Delete previous credentials
        await self._instance_repo.delete_credentials(instance_id)

        # Encrypt and persist
        encrypted = {
            key: self._vault.encrypt(value)
            for key, value in credentials_payload.items()
        }

        # Set expiry for access_token
        from datetime import datetime, timedelta, timezone
        expires_in = token_data.get("expires_in", 3600)
        expires_at_map = {
            "access_token": datetime.now(timezone.utc) + timedelta(seconds=expires_in - 60)
        }
        await self._instance_repo.save_credentials(instance_id, encrypted, expires_at_map)

        # Refresh instance
        instance = await self.get_instance(instance_id, user_id)

        # Launch stdio process
        await self._launch_stdio_process(instance)

        logger.info(
            "OAuth completed for instance id=%s",
            instance_id,
        )

        # Audit: OAuth credential creation
        try:
            await log_credential_event(
                self._session,
                CredentialAction.CREATED,
                user_id=user_id,
                instance_id=instance_id,
                credential_key="refresh_token,client_id,client_secret,access_token",
                details=f"OAuth2 flow completed for catalog '{instance.catalog.slug}'",
            )
        except Exception:
            pass

        return instance

    # ------------------------------------------------------------------
    # Sync tools (MCP discovery → ToolConfig registration)
    # ------------------------------------------------------------------

    async def sync_tools(self, instance_id: int, user_id: int) -> SyncResult:
        instance = await self.get_instance(instance_id, user_id)

        # Ensure process is running
        if not instance.process_pid or not self._stdio.is_running(instance.process_pid):
            await self._launch_stdio_process(instance)

        catalog = instance.catalog

        # Discover tools from the running MCP server via stdio
        try:
            discovered = await self._mcp_service.discover_tools(
                base_url=catalog.command or "",  # Not used for stdio
                is_stdio=True,
                stdio_command=catalog.command,
                stdio_args=catalog.args,
                stdio_env=self._credential_manager.inject_for_stdio(
                    await self._credential_manager.get_credentials(instance),
                    catalog.env_prefix,
                    auth_env_var_mapping=catalog.auth_env_var_mapping,
                ),
            )
        except Exception as exc:
            logger.exception("Tool discovery failed for instance %s", instance_id)
            raise RuntimeError(f"Tool discovery failed: {exc}") from exc

        # Cleanup previous sources to avoid duplicates
        await self._cleanup_previous_sources(instance)

        # Determine context_mode
        if instance.available_in_chat and instance.available_in_reactive:
            context_mode = "both"
        elif instance.available_in_reactive:
            context_mode = "reactive"
        else:
            context_mode = "chat"

        # Register in proactive context
        mcp_source_id = None
        if instance.available_in_chat:
            mcp_source_id = await self._register_in_chat_context(instance, catalog, discovered, context_mode)

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

    async def _cleanup_previous_sources(self, instance: IntegrationInstance) -> None:
        """Delete previous MCP sources and their tools to avoid duplicates."""
        mcp_source_id = instance.mcp_source_id
        reactive_mcp_source_id = instance.reactive_mcp_source_id

        if mcp_source_id or reactive_mcp_source_id:
            instance.mcp_source_id = None
            instance.reactive_mcp_source_id = None
            await self._instance_repo.update(instance)

        if mcp_source_id:
            await self._delete_mcp_source(mcp_source_id)

        if reactive_mcp_source_id:
            await self._delete_reactive_mcp_source(reactive_mcp_source_id)

    async def _delete_mcp_source(self, source_id: int) -> None:
        from src.persistencia.repositories.tool_repository import (
            MCPSourceRepository,
            ToolRepository,
        )

        tool_repo = ToolRepository(self._session)
        tools = await tool_repo.list_by_source(source_id)
        for tool in tools:
            await self._session.delete(tool)

        source_repo = MCPSourceRepository(self._session)
        source = await source_repo.get_by_id(source_id)
        if source:
            await self._session.delete(source)

        await self._session.commit()
        logger.info("Deleted MCP source id=%s with %d tools", source_id, len(tools))

    async def _delete_reactive_mcp_source(self, source_id: int) -> None:
        from src.persistencia.repositories.reactive_tool_repository import (
            ReactiveMCPSourceRepository,
            ReactiveToolRepository,
        )

        tool_repo = ReactiveToolRepository(self._session)
        tools = await tool_repo.list_by_source(source_id)
        for tool in tools:
            await self._session.delete(tool)

        source_repo = ReactiveMCPSourceRepository(self._session)
        source = await source_repo.get_by_id(source_id)
        if source:
            await self._session.delete(source)

        await self._session.commit()
        logger.info("Deleted reactive MCP source id=%s with %d tools", source_id, len(tools))

    async def _register_in_chat_context(
        self,
        instance: IntegrationInstance,
        catalog: IntegrationCatalog,
        discovered: list[dict],
        context_mode: str = "chat",
    ) -> int:
        from src.persistencia.models.tool_config import MCPSource, ToolConfig
        from src.persistencia.repositories.tool_repository import MCPSourceRepository, ToolRepository

        source_repo = MCPSourceRepository(self._session)
        tool_repo = ToolRepository(self._session)

        source_name = f"{catalog.slug}-u{instance.user_id}-i{instance.id}"
        source = MCPSource(
            name=source_name,
            description=f"{catalog.name} integration for user {instance.user_id}",
            url="stdio",  # stdio transport
            type="stdio",
            is_enabled=True,
            context_mode=context_mode,
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
                config=tool_def.get("config", {"transport": "stdio"}),
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
            user_id=instance.user_id,
            name=source_name,
            description=f"{catalog.name} reactive integration for user {instance.user_id}",
            url="stdio",
            type="stdio",
            is_enabled=True,
        )
        await source_repo.create(source)
        await self._session.flush()

        for tool_def in discovered:
            name = tool_def.get("name")
            if not name:
                continue
            tool = ReactiveToolConfig(
                user_id=instance.user_id,
                name=name,
                description=tool_def.get("description") or "",
                parameter_schema=tool_def.get("parameter_schema")
                or tool_def.get("inputSchema")
                or {},
                config=tool_def.get("config", {"transport": "stdio"}),
                source_id=source.id,
                is_enabled=True,
            )
            await tool_repo.create(tool)

        await self._session.commit()
        return source.id

    # ------------------------------------------------------------------
    # Stdio process helpers
    # ------------------------------------------------------------------

    async def _launch_stdio_process(self, instance: IntegrationInstance) -> None:
        """Launch or restart the stdio process for an instance."""
        catalog = instance.catalog

        # Stop previous process if any
        if instance.process_pid and self._stdio.is_running(instance.process_pid):
            self._stdio.stop(instance.process_pid)

        # Get fresh credentials (with auto-refresh)
        credentials = await self._credential_manager.get_credentials(instance)
        env = self._credential_manager.inject_for_stdio(
            credentials,
            catalog.env_prefix,
            auth_env_var_mapping=catalog.auth_env_var_mapping,
        )

        # Launch new process (with one retry on failure)
        process_info = self._stdio.start(
            command=catalog.command or "",
            args=catalog.args,
            env=env,
        )

        if process_info.status == "error":
            # Retry once after a short delay
            import asyncio
            logger.warning(
                "Stdio process failed to start for instance=%s, retrying in 1s...",
                instance.id,
            )
            await asyncio.sleep(1)
            process_info = self._stdio.start(
                command=catalog.command or "",
                args=catalog.args,
                env=env,
            )
            if process_info.status == "error":
                instance.process_status = "error"
                await self._instance_repo.update(instance)
                raise RuntimeError(f"Stdio process failed to start: {process_info.error}")

        instance.process_pid = process_info.pid
        instance.process_status = process_info.status
        instance.last_used_at = datetime.now()
        await self._instance_repo.update(instance)

    # ------------------------------------------------------------------
    # Process lifecycle helpers (simplified)
    # ------------------------------------------------------------------

    async def get_status(self, instance_id: int, user_id: int) -> dict[str, Any]:
        instance = await self.get_instance(instance_id, user_id)
        process = None
        if instance.process_pid:
            info = self._stdio.get_info(instance.process_pid)
            if info:
                process = {
                    "pid": info.pid,
                    "status": info.status,
                    "command": info.command,
                }
        return {
            "instance": instance,
            "process": process,
        }

    async def stop_process(self, instance_id: int, user_id: int) -> IntegrationInstance:
        instance = await self.get_instance(instance_id, user_id)
        if instance.process_pid:
            self._stdio.stop(instance.process_pid)
        instance.process_status = "stopped"
        instance.process_pid = None
        await self._instance_repo.update(instance)
        return instance
