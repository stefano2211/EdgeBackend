"""Unified MCP tool factory.

Replaces: mcp_tool.py + reactive_mcp_tool.py
"""

from __future__ import annotations

import asyncio
import json
from typing import Literal

from langchain_core.tools import StructuredTool

from src.core.database import AsyncSessionLocal
from src.core.logging import logging

logger = logging.getLogger(__name__)

# ── Configuration maps per context ──
class _LRUCache:
    """Simple bounded dict cache with FIFO eviction."""

    def __init__(self, maxsize: int = 256) -> None:
        self._maxsize = maxsize
        self._data: dict = {}
        self._order: list = []

    def get(self, key):
        return self._data.get(key)

    def set(self, key, value):
        if key in self._data:
            self._order.remove(key)
        elif len(self._data) >= self._maxsize:
            oldest = self._order.pop(0)
            del self._data[oldest]
        self._data[key] = value
        self._order.append(key)

    def invalidate(self, prefix: str | None = None) -> None:
        """Remove entries matching an optional key prefix."""
        if prefix is None:
            self._data.clear()
            self._order.clear()
            return
        keys_to_remove = [k for k in list(self._order) if k.startswith(prefix)]
        for k in keys_to_remove:
            self._data.pop(k, None)
            if k in self._order:
                self._order.remove(k)


_CONFIG = {
    "chat": {
        "repo_cls": "src.persistencia.repositories.tool_repository.ToolRepository",
        "source_cls": "src.persistencia.models.tool_config.MCPSource",
        "cache": _LRUCache(maxsize=256),
        "lock": asyncio.Lock(),
    },
    "reactive": {
        "repo_cls": "src.persistencia.repositories.reactive_tool_repository.ReactiveToolRepository",
        "source_cls": "src.persistencia.models.reactive_mcp_source.ReactiveMCPSource",
        "cache": _LRUCache(maxsize=256),
        "lock": asyncio.Lock(),
    },
}

# Lazy singleton for MCPService (shared, stateless)
_mcp_service = None
_mcp_service_lock = asyncio.Lock()


async def _get_mcp_service():
    global _mcp_service
    if _mcp_service is None:
        async with _mcp_service_lock:
            if _mcp_service is None:
                from src.services.mcp_service import MCPService
                _mcp_service = MCPService()
    return _mcp_service


def _import_class(dotted_path: str):
    parts = dotted_path.split(".")
    module_path = ".".join(parts[:-1])
    cls_name = parts[-1]
    mod = __import__(module_path, fromlist=[cls_name])
    return getattr(mod, cls_name)


async def _mcp_execute_impl(
    tool_config_name: str,
    parameters: dict | None,
    key_values: dict | None,
    key_figures: list | None,
    source: Literal["chat", "reactive"],
) -> str:
    """Execute MCP tool from the specified context."""
    cfg = _CONFIG[source]
    if parameters is None:
        parameters = {}
    if key_values:
        parameters["key_values"] = key_values
    if key_figures:
        parameters["key_figures"] = key_figures

    logger.info(
        "[%s MCP] Calling tool: %s kv=%s kf=%s",
        source,
        tool_config_name,
        bool(key_values),
        bool(key_figures),
    )

    async with AsyncSessionLocal() as session:
        RepoCls = _import_class(cfg["repo_cls"])
        SourceCls = _import_class(cfg["source_cls"])
        repo = RepoCls(session)
        tool_config = await repo.get_by_name(tool_config_name)

        if not tool_config:
            return json.dumps({"error": f"Tool '{tool_config_name}' not found in {source}."})

        mcp_service = await _get_mcp_service()
        config_data = tool_config.config or {}
        execution_url = config_data.get("url", "")
        transport_type = config_data.get("transport", "mcp")
        method = config_data.get("method", "GET")
        parameter_schema = tool_config.parameter_schema or {}
        schema_hints = parameter_schema.get("response") or {}

        clean_arguments = parameters.copy()
        kv_filter = clean_arguments.pop("key_values", None)
        kf_filter = clean_arguments.pop("key_figures", None)

        cache = cfg["cache"]
        lock = cfg["lock"]

        # URL resolution with per-context cache
        if execution_url and "://" not in execution_url:
            cache_key = f"{tool_config.source_id}:{execution_url}"
            cached_url = cache.get(cache_key)
            if cached_url is not None:
                execution_url = cached_url
            else:
                source_obj = await session.get(SourceCls, tool_config.source_id)
                if source_obj and source_obj.url:
                    base = source_obj.url.rstrip("/")
                    path = execution_url.lstrip("/")
                    execution_url = f"{base}/{path}"
                    async with lock:
                        cache.set(cache_key, execution_url)

        if execution_url and "://" in execution_url:
            scheme, rest = execution_url.split("://", 1)
            # Separate path and query to avoid corrupting query params
            if "?" in rest:
                path_part, query_part = rest.split("?", 1)
                while "//" in path_part:
                    path_part = path_part.replace("//", "/")
                execution_url = f"{scheme}://{path_part}?{query_part}"
            else:
                while "//" in rest:
                    rest = rest.replace("//", "/")
                execution_url = f"{scheme}://{rest}"

        # Heuristic REST detection
        if transport_type == "mcp" and execution_url and "://" in execution_url:
            if any(domain in execution_url for domain in ["api.", "/api/"]):
                transport_type = "rest"

        # Resolve stdio config if needed
        stdio_command = None
        stdio_args = None
        stdio_env = None
        if transport_type == "stdio":
            from sqlalchemy import select
            from src.integrations.models import IntegrationInstance
            from src.integrations.credentials import CredentialManager
            from src.integrations.repositories.integration_repository import (
                IntegrationInstanceRepository,
            )

            if source == "chat":
                stmt = select(IntegrationInstance).where(
                    IntegrationInstance.mcp_source_id == tool_config.source_id
                )
            else:
                stmt = select(IntegrationInstance).where(
                    IntegrationInstance.reactive_mcp_source_id == tool_config.source_id
                )
            result = await session.execute(stmt)
            instance = result.scalar_one_or_none()

            if instance and instance.catalog:
                catalog = instance.catalog
                stdio_command = catalog.command
                stdio_args = catalog.args or []

                cred_manager = CredentialManager(
                    IntegrationInstanceRepository(session)
                )
                credentials = await cred_manager.get_credentials(instance)
                stdio_env = cred_manager.inject_for_stdio(
                    credentials,
                    catalog.env_prefix,
                    auth_env_var_mapping=catalog.auth_env_var_mapping,
                )

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


def create_mcp_tool(source: Literal["chat", "reactive"] = "chat") -> StructuredTool:
    """Create an MCP tool bound to a context (chat or reactive).

    Args:
        source: Which DB tables to read from.

    Returns:
        StructuredTool ready for DeepAgents.
    """

    async def _bound_mcp_execute(
        tool_config_name: str,
        parameters: dict | None = None,
        key_values: dict | None = None,
        key_figures: list | None = None,
    ) -> str:
        return await _mcp_execute_impl(
            tool_config_name, parameters, key_values, key_figures, source=source
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
            "  - key_values (dict | None): optional filter for categorical fields in the response.\n"
            "  - key_figures (list | None): optional filter for numeric fields in the response.\n"
            "IMPORTANT: 'parameters' must contain ALL required arguments for the tool being called.\n"
            "For send_email: parameters={\"to\": \"<recipient>\", \"subject\": \"<subject>\", \"body\": \"<body>\"} is MANDATORY."
        ),
    )


def invalidate_mcp_cache(context: Literal["chat", "reactive"], source_id: int | None = None) -> None:
    """Invalidate the MCP URL cache for a given context.

    Call this after updating or deleting an MCP source so stale resolved
    URLs are evicted.
    """
    cfg = _CONFIG.get(context)
    if not cfg:
        return
    cache = cfg["cache"]
    if source_id is not None:
        cache.invalidate(f"{source_id}:")
    else:
        cache.invalidate(None)
    logger.info("[%s MCP] Cache invalidated for source_id=%s", context, source_id)
