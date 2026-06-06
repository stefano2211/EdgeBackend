"""IntegrationService — orchestrates the lifecycle of a user integration.

Responsibilities:
  1. Create / update / delete IntegrationInstance records
  2. Encrypt and store credentials
  3. Verify connection health on credential submission
  4. Dynamically query process statuses from the MCP session cache
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.integrations.auth_strategies import get_strategy
from backend.integrations.credentials import CredentialManager
from backend.integrations.credential_vault import CredentialVault
from backend.integrations.interfaces import ICredentialVault
from backend.integrations.models import IntegrationInstance
from backend.integrations.repositories import IntegrationInstanceRepository
from backend.integrations.catalog_service import CatalogService
from backend.integrations.schemas import (
    CredentialsSubmit,
    IntegrationInstanceCreate,
    IntegrationInstanceUpdate,
    SyncResult,
)
from backend.integrations.credential_audit import log_credential_event, CredentialAction

logger = logging.getLogger(__name__)


class IntegrationService:
    """High-level orchestrator. Stateless aside from injected collaborators."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        credential_vault: ICredentialVault | None = None,
    ) -> None:
        self._session = session
        self._catalog_service = CatalogService(session)
        self._instance_repo = IntegrationInstanceRepository(session)
        self._vault = credential_vault or CredentialVault()
        self._credential_manager = CredentialManager(self._instance_repo, self._vault)

    # ------------------------------------------------------------------
    # Instance CRUD
    # ------------------------------------------------------------------

    async def create_instance(
        self, user_id: int, data: IntegrationInstanceCreate
    ) -> IntegrationInstance:
        catalog = await self._catalog_service.get_by_slug(data.catalog_slug)
        if not catalog:
            raise ValueError(f"Catalog '{data.catalog_slug}' not found")
        if not catalog.is_enabled:
            raise ValueError(f"Catalog '{data.catalog_slug}' is disabled")

        instance = IntegrationInstance(
            user_id=user_id,
            catalog_slug=catalog.slug,
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

        update_dict = data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(instance, field, value)
        await self._instance_repo.update(instance)

        logger.info("Updated integration instance id=%s", instance_id)
        return instance

    async def delete_instance(self, instance_id: int, user_id: int) -> None:
        instance = await self.get_instance(instance_id, user_id)

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

        # Delete DB record (cascades to credentials)
        await self._instance_repo.delete(instance)
        logger.info("Deleted integration instance id=%s", instance_id)

    # ------------------------------------------------------------------
    # Setup guide
    # ------------------------------------------------------------------

    async def get_setup_guide(self, instance_id: int, user_id: int) -> dict[str, Any]:
        instance = await self.get_instance(instance_id, user_id)
        catalog = instance.catalog
        if not catalog:
            raise ValueError(f"Catalog config not found for instance '{instance_id}'")
        required_fields = list(catalog.auth_env_var_mapping.values())
        return {
            "catalog_name": catalog.name,
            "setup_guide_markdown": catalog.auth_setup_guide_markdown or "No guide available.",
            "required_fields": required_fields,
            "auth_type": catalog.auth_type,
        }

    # ------------------------------------------------------------------
    # Credentials submission
    # ------------------------------------------------------------------

    async def submit_credentials(
        self, instance_id: int, user_id: int, data: CredentialsSubmit
    ) -> IntegrationInstance:
        instance = await self.get_instance(instance_id, user_id)
        catalog = instance.catalog
        if not catalog:
            raise ValueError(f"Catalog config not found for instance '{instance_id}'")

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

        # 4. Set status to running
        instance.process_status = "running"
        instance.process_pid = None
        await self._instance_repo.update(instance)

        logger.info(
            "Credentials submitted and instance set to running for instance id=%s",
            instance_id,
        )

        # 5. Discover tools from the MCP server to verify connection health
        discovered = await self._discover_tools(instance)
        logger.info(
            "Instance id=%s verified. Discovered %d tools dynamically.",
            instance_id,
            len(discovered),
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
        """Finish an OAuth2 flow: exchange code, store tokens, set status."""
        from backend.integrations.oauth.gmail_flow import exchange_code
        from backend.integrations.oauth.state_manager import get_state_manager
        from backend.core.config import settings

        # Recover context from Redis (one-time read)
        state_manager = get_state_manager()
        ctx = await state_manager.get(state)
        if not ctx:
            raise ValueError("Invalid or expired OAuth state — the authorization session may have timed out. Please try again.")

        instance_id = ctx["instance_id"]
        user_id = ctx["user_id"]

        instance = await self.get_instance(instance_id, user_id)
        catalog = instance.catalog
        if not catalog:
            raise ValueError(f"Catalog config not found for instance '{instance_id}'")

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

        # Set status to running
        instance.process_status = "running"
        instance.process_pid = None
        await self._instance_repo.update(instance)

        logger.info(
            "OAuth completed and instance set to running for instance id=%s",
            instance_id,
        )

        # Discover tools from the MCP server to verify connection health
        discovered = await self._discover_tools(instance)
        logger.info(
            "OAuth completed. Discovered %d tools dynamically for instance id=%s",
            len(discovered),
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

    async def _discover_tools(
        self, instance: IntegrationInstance
    ) -> list[dict]:
        """Connect via MCP stdio client, discover tools, and return structured list.

        Spins up a temporary MCP stdio client using the same credentials/env as
        the running process, calls tools/list, and normalises the result.
        """
        catalog = instance.catalog
        if not catalog:
            logger.warning("Catalog config not found for instance %s", instance.id)
            return []

        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client

            # Build same env as the running process
            credentials = await self._credential_manager.get_credentials(instance)
            env = self._credential_manager.inject_for_stdio(
                credentials,
                catalog.env_prefix,
                auth_env_var_mapping=catalog.auth_env_var_mapping,
            )

            # Ensure child process keeps necessary environment variables
            import os
            stdio_env = {**os.environ, **(env or {})}

            server_params = StdioServerParameters(
                command=catalog.command or "python",
                args=catalog.args or [],
                env=stdio_env,
            )

            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    discovered = []
                    for tool in result.tools:
                        discovered.append({
                            "name": tool.name,
                            "description": tool.description,
                            "parameter_schema": tool.inputSchema,
                            "config": {"transport": "stdio"},
                        })
                    return discovered

        except Exception as exc:
            logger.exception(
                "Tool discovery failed for instance id=%s: %s", instance.id, exc
            )
            return []

    async def get_status(self, instance_id: int, user_id: int) -> dict[str, Any]:
        """Query process status. Checks if the instance is active in the MCPService session cache."""
        instance = await self.get_instance(instance_id, user_id)
        
        status = "stopped"
        if instance.credentials and instance.process_status != "stopped":
            status = "ready"
            
        from backend.services.mcp_service import MCPService
        from mcp import StdioServerParameters
        import os
        
        is_active = False
        try:
            catalog = instance.catalog
            if catalog:
                credentials = await self._credential_manager.get_credentials(instance)
                env = self._credential_manager.inject_for_stdio(
                    credentials,
                    catalog.env_prefix,
                    auth_env_var_mapping=catalog.auth_env_var_mapping,
                )
                stdio_env = {**os.environ, **(env or {})}
                server_params = StdioServerParameters(
                    command=catalog.command or "",
                    args=catalog.args or [],
                    env=stdio_env,
                )
                cache_key = MCPService._stdio_cache_key(server_params)
                if cache_key in MCPService._stdio_cache:
                    is_active = True
                    status = "running"
        except Exception:
            pass

        command_list = []
        if instance.catalog:
            command_list = [instance.catalog.command] + (instance.catalog.args or [])

        tools_registered = []
        if status in ("running", "ready"):
            tools_registered = await self._discover_tools(instance)

        return {
            "instance": instance,
            "process": {
                "pid": 0 if is_active else None,
                "status": status,
                "command": command_list,
            },
            "tools_registered": tools_registered,
        }

    async def sync_instance(self, instance_id: int, user_id: int) -> IntegrationInstance:
        """Force re-discovery of tools for an instance to verify it is healthy."""
        instance = await self.get_instance(instance_id, user_id)

        instance.process_pid = None
        instance.process_status = "running"
        await self._instance_repo.update(instance)

        # Discover current tools from the MCP server to verify health
        discovered = await self._discover_tools(instance)
        logger.info(
            "Synced instance id=%s — verified %d tools dynamically (chat=%s, reactive=%s)",
            instance_id,
            len(discovered),
            instance.available_in_chat,
            instance.available_in_reactive,
        )

        return instance

    async def stop_process(self, instance_id: int, user_id: int) -> IntegrationInstance:
        """Stop the integration process. Clears process_status to 'stopped'."""
        instance = await self.get_instance(instance_id, user_id)
        instance.process_status = "stopped"
        instance.process_pid = None
        await self._instance_repo.update(instance)
        
        # Note: Any cached dynamic session in MCPService._stdio_cache will expire automatically
        # after 5 minutes of inactivity.
        return instance
