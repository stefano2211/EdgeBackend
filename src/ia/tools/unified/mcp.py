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
_CONFIG = {
    "chat": {
        "repo_cls": "src.persistencia.repositories.tool_repository.ToolRepository",
        "source_cls": "src.persistencia.models.tool_config.MCPSource",
        "cache": {},
        "lock": asyncio.Lock(),
    },
    "reactive": {
        "repo_cls": "src.persistencia.repositories.reactive_tool_repository.ReactiveToolRepository",
        "source_cls": "src.persistencia.models.reactive_mcp_source.ReactiveMCPSource",
        "cache": {},
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
            if cache_key in cache:
                execution_url = cache[cache_key]
            else:
                source_obj = await session.get(SourceCls, tool_config.source_id)
                if source_obj and source_obj.url:
                    base = source_obj.url.rstrip("/")
                    path = execution_url.lstrip("/")
                    execution_url = f"{base}/{path}"
                    async with lock:
                        cache[cache_key] = execution_url

        if execution_url and "://" in execution_url:
            scheme, rest = execution_url.split("://", 1)
            while "//" in rest:
                rest = rest.replace("//", "/")
            execution_url = f"{scheme}://{rest}"

        # Heuristic REST detection
        if transport_type == "mcp" and execution_url and "://" in execution_url:
            if any(domain in execution_url for domain in ["api.", "/api/"]):
                transport_type = "rest"

        response = await mcp_service.execute_tool(
            base_url=execution_url,
            tool_name=tool_config_name,
            arguments=clean_arguments,
            is_stdio=(transport_type == "stdio"),
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
