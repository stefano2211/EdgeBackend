"""Unified MCP tool factory.

Replaces: mcp_tool.py + reactive_mcp_tool.py
"""

from __future__ import annotations

import asyncio
import json
from typing import Literal

from langchain_core.tools import StructuredTool
from langchain_core.runnables import RunnableConfig

from backend.core.database import AsyncSessionLocal
from backend.core.logging import logging

logger = logging.getLogger(__name__)


# Lazy singleton for MCPService (shared, stateless)
_mcp_service = None
_mcp_service_lock = asyncio.Lock()


async def _get_mcp_service():
    global _mcp_service
    if _mcp_service is None:
        async with _mcp_service_lock:
            if _mcp_service is None:
                from backend.services.mcp_service import MCPService
                _mcp_service = MCPService()
    return _mcp_service


async def _mcp_execute_impl(
    tool_config_name: str,
    parameters: dict | None,
    source: Literal["chat", "reactive"],
    config: RunnableConfig | None = None,
) -> str:
    """Execute MCP tool from the specified context dynamically."""
    if parameters is None:
        parameters = {}

    logger.info(
        "[%s MCP] Calling tool: %s",
        source,
        tool_config_name,
    )

    async with AsyncSessionLocal() as session:
        # Resolve user_id from thread_id in config
        configurable = config.get("configurable", {}) if config else {}
        thread_id = configurable.get("thread_id")
        user_id = None
        if thread_id:
            try:
                from sqlalchemy import select
                if thread_id.startswith("event-"):
                    parts = thread_id.split("-")
                    if len(parts) >= 2:
                        event_id = int(parts[1])
                        from backend.persistencia.models.event import Event
                        res = await session.execute(select(Event).where(Event.id == event_id))
                        evt = res.scalar_one_or_none()
                        if evt:
                            user_id = evt.triggered_by_user_id
                else:
                    from backend.persistencia.models.conversation import Conversation
                    res = await session.execute(select(Conversation).where(Conversation.thread_id == thread_id))
                    conv = res.scalar_one_or_none()
                    if conv:
                        user_id = conv.user_id
            except Exception as e:
                logger.warning("Error resolving user_id from thread_id=%s: %s", thread_id, e)

        if not user_id:
            # Fallback for health checks or testing when user context is missing
            user_id = 1

        # Find which active IntegrationInstance of the user has the tool
        from sqlalchemy import select
        from backend.integrations.models import IntegrationInstance
        from backend.integrations.integration_service import IntegrationService
        from backend.integrations.repositories.integration_repository import IntegrationInstanceRepository
        from backend.integrations.credentials import CredentialManager

        stmt = select(IntegrationInstance).where(
            IntegrationInstance.user_id == user_id,
            IntegrationInstance.is_enabled.is_(True)
        )
        if source == "chat":
            stmt = stmt.where(IntegrationInstance.available_in_chat.is_(True))
        else:
            stmt = stmt.where(IntegrationInstance.available_in_reactive.is_(True))
        
        result = await session.execute(stmt)
        instances = result.scalars().all()

        target_instance = None
        target_tool = None
        integration_service = IntegrationService(session)

        for instance in instances:
            discovered = await integration_service._discover_tools(instance)
            matching = next((t for t in discovered if t["name"] == tool_config_name), None)
            if matching:
                target_instance = instance
                target_tool = matching
                break

        if not target_instance or not target_tool:
            return json.dumps({"error": f"Tool '{tool_config_name}' not found for user {user_id} in {source} context."})

        mcp_service = await _get_mcp_service()
        config_data = target_tool.get("config") or {"transport": "stdio"}
        execution_url = config_data.get("url", "")
        transport_type = config_data.get("transport", "stdio")
        method = config_data.get("method", "GET")
        parameter_schema = target_tool.get("parameter_schema") or {}
        schema_hints = parameter_schema.get("response") or {}

        clean_arguments = parameters.copy()
        kv_filter = clean_arguments.pop("key_values", None)
        kf_filter = clean_arguments.pop("key_figures", None)

        # Stdio environment resolution
        stdio_command = None
        stdio_args = None
        stdio_env = None
        
        if target_instance.catalog and (transport_type == "stdio" or target_instance.catalog.command):
            transport_type = "stdio"
            catalog = target_instance.catalog
            stdio_command = catalog.command
            stdio_args = catalog.args or []

            cred_manager = CredentialManager(
                IntegrationInstanceRepository(session)
            )
            credentials = await cred_manager.get_credentials(target_instance)
            cred_env = cred_manager.inject_for_stdio(
                credentials,
                catalog.env_prefix,
                auth_env_var_mapping=catalog.auth_env_var_mapping,
            )
            import os
            stdio_env = {**os.environ, **(cred_env or {})}

        response = await mcp_service.execute_tool(
            base_url=execution_url,
            tool_name=tool_config_name,
            arguments=clean_arguments,
            is_stdio=(transport_type == "stdio"),
            stdio_command=stdio_command,
            stdio_args=stdio_args,
            stdio_env=stdio_env,
            transport_type=transport_type,
            method=method,
            schema_hints=schema_hints or None,
            key_values_filter=kv_filter,
            key_figures_filter=kf_filter,
        )

        if response.error:
            return json.dumps({"error": f"Error from {tool_config_name}: {response.error}"})

        # MCP native: return raw JSON directly so the LLM sees structured data
        if response.raw_response is not None:
            return json.dumps({
                "source": response.source,
                "data": response.raw_response,
            }, ensure_ascii=False)

        # Legacy fallback
        result = {
            "source": response.source,
            "key_figures": [
                {"name": kf.name, "value": kf.value, "unit": kf.unit}
                for kf in response.key_figures
            ],
            "key_values": [
                {"name": kv.name, "value": kv.value}
                for kv in response.key_values
            ],
        }
        if not response.key_figures and not response.key_values:
            result["warning"] = "No structured data extracted."

        return json.dumps(result, ensure_ascii=False)


def create_mcp_tool(source: Literal["chat", "reactive"]) -> StructuredTool:
    """Create a LangChain tool wrapper for MCP execution."""
    
    async def _bound_mcp_execute(
        tool_config_name: str,
        parameters: dict | None = None,
        config: RunnableConfig | None = None,
    ) -> str:
        return await _mcp_execute_impl(
            tool_config_name, parameters, source=source, config=config
        )

    return StructuredTool.from_function(
        coroutine=_bound_mcp_execute,
        name="mcp_execute",
        description=(
            "Execute a registered MCP integration tool by name.\n"
            "Parameters:\n"
            "  - tool_config_name (str): exact name of the registered tool (e.g. 'send_email', 'list_emails', 'get_email').\n"
            "  - parameters (dict): tool-specific input arguments. For email tools: {\"to\": \"addr\", \"subject\": \"...\", \"body\": \"...\"}.\n"
            "    For sensor tools: {\"equipment\": \"...\", \"metric\": \"...\"}. Pass ALL required fields here.\n"
            "Returns: JSON object with a 'data' field containing the tool's raw structured response.\n"
            "IMPORTANT: 'parameters' must contain ALL required arguments for the tool being called.\n"
            "For send_email: parameters={\"to\": \"<recipient>\", \"subject\": \"<subject>\", \"body\": \"<body>\"} is MANDATORY."
        ),
    )


def invalidate_mcp_cache(context: Literal["chat", "reactive"], source_id: int | None = None) -> None:
    # No-op since we dynamically discover tools and caches are handled by MCPService connection TTL
    pass
