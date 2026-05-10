"""Reactive MCP tool for DeepAgents — dispatches to registered REACTIVE MCP tools.

Isolated from chat MCP tools:
- Fetches tool configuration from reactive_tool_configs table
- Resolves execution URL via ReactiveMCPSource
- Uses separate singleton instances for service and cache
"""

from __future__ import annotations

import asyncio
import json

from langchain_core.tools import StructuredTool

from src.core.database import AsyncSessionLocal
from src.core.logging import logging
from src.persistencia.models.reactive_mcp_source import ReactiveMCPSource
from src.persistencia.repositories.reactive_tool_repository import ReactiveToolRepository
from src.services.mcp_service import MCPService

logger = logging.getLogger(__name__)

# Lazy-init singletons (isolated from chat mcp_tool.py)
_reactive_mcp_service: MCPService | None = None
_reactive_mcp_service_lock = asyncio.Lock()

# In-memory URL resolution cache (isolated from chat)
_reactive_url_cache: dict = {}
_reactive_url_cache_lock = asyncio.Lock()


async def _get_reactive_mcp_service() -> MCPService:
    global _reactive_mcp_service
    if _reactive_mcp_service is None:
        async with _reactive_mcp_service_lock:
            if _reactive_mcp_service is None:
                _reactive_mcp_service = MCPService()
    return _reactive_mcp_service


async def _reactive_mcp_execute(
    tool_config_name: str,
    parameters: dict | None = None,
    key_values: dict | None = None,
    key_figures: list | None = None,
) -> str:
    """Execute a registered REACTIVE MCP tool with smart filtering.

    Use this to get real-time data, sensor readings, or perform external actions
    within the reactive event pipeline.

    Args:
        tool_config_name: Name of the tool as registered in the reactive system.
        parameters: Any standard parameters required by the API path/query.
        key_values: Filter by categorical field values.
        key_figures: Filter by numeric field ranges.

    Returns:
        Structured JSON with source, key_figures and key_values.
    """
    if parameters is None:
        parameters = {}

    if key_values:
        parameters["key_values"] = key_values
    if key_figures:
        parameters["key_figures"] = key_figures

    logger.info(
        "[Reactive MCP Tool] Calling dynamic tool: %s with filters: kv=%s, kf=%s, args=%s",
        tool_config_name,
        bool(key_values),
        bool(key_figures),
        parameters,
    )

    async with AsyncSessionLocal() as session:
        return await _do_call_reactive_mcp(session, tool_config_name, parameters)


async def _do_call_reactive_mcp(
    session,
    tool_config_name: str,
    arguments: dict = {},
) -> str:
    repo = ReactiveToolRepository(session)
    tool_config = await repo.get_by_name(tool_config_name)

    if not tool_config:
        return json.dumps({"error": f"Reactive tool configuration '{tool_config_name}' not found."})

    mcp_service = await _get_reactive_mcp_service()

    config_data = tool_config.config or {}
    execution_url = config_data.get("url", "")
    transport_type = config_data.get("transport", "mcp")
    method = config_data.get("method", "GET")

    parameter_schema = tool_config.parameter_schema or {}
    schema_hints = parameter_schema.get("response") or {}

    # -- Extract smart filters from arguments --
    clean_arguments = arguments.copy()
    key_values_filter = clean_arguments.pop("key_values", None)
    key_figures_filter = clean_arguments.pop("key_figures", None)

    if key_values_filter:
        logger.info("[Reactive MCP Tool] Applying key_values filter: %s", key_values_filter)
    if key_figures_filter:
        logger.info("[Reactive MCP Tool] Applying key_figures filter: %s", key_figures_filter)

    # -- Robust URL resolution (with isolated in-memory cache) --
    if execution_url and "://" not in execution_url:
        cache_key = f"reactive:{tool_config.source_id}:{execution_url}"
        if cache_key in _reactive_url_cache:
            execution_url = _reactive_url_cache[cache_key]
            logger.debug("[Reactive MCP Tool] URL resolved from cache: %s", execution_url)
        else:
            source = await session.get(ReactiveMCPSource, tool_config.source_id)
            if source and source.url:
                base_url = source.url.rstrip("/")
                path = execution_url.lstrip("/")
                execution_url = f"{base_url}/{path}"
                _reactive_url_cache[cache_key] = execution_url
                logger.info("[Reactive MCP Tool] Resolved relative URL to: %s", execution_url)

    if execution_url and "://" in execution_url:
        scheme, rest = execution_url.split("://", 1)
        while "//" in rest:
            rest = rest.replace("//", "/")
        execution_url = f"{scheme}://{rest}"

    # Heuristic: Detect REST transport
    if transport_type == "mcp" and execution_url and "://" in execution_url:
        if any(domain in execution_url for domain in ["pokeapi.co", "api.", "/api/"]):
            logger.info("[Reactive MCP Tool] Heuristic detected REST transport for %s", execution_url)
            transport_type = "rest"

    logger.info(
        "[Reactive MCP Tool] Executing %s via %s at %s", tool_config_name, transport_type, execution_url
    )

    response = await mcp_service.execute_tool(
        base_url=execution_url,
        tool_name=tool_config_name,
        arguments=clean_arguments,
        is_stdio=(transport_type == "stdio"),
        transport_type=transport_type,
        method=method,
        schema_hints=schema_hints or None,
        key_values_filter=key_values_filter,
        key_figures_filter=key_figures_filter,
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
        result["warning"] = "No structured data could be extracted from the response."

    logger.info(
        "[Reactive MCP Tool] Returning %d key figures and %d key values for %s",
        len(result["key_figures"]),
        len(result["key_values"]),
        tool_config_name,
    )
    return json.dumps(result, ensure_ascii=False)


reactive_mcp_execute = StructuredTool.from_function(
    coroutine=_reactive_mcp_execute,
    name="reactive_mcp_execute",
    description=(
        "Execute a registered REACTIVE MCP (Model Context Protocol) tool dynamically with STRICT precision. "
        "Use this to get real-time data, sensor readings, or perform external actions within the reactive pipeline.\n\n"
        "Input:\n"
        "  - tool_config_name: The name of the tool as registered in the reactive system (e.g., 'get_maquinaria').\n"
        "  - parameters: Standard parameters required by the API path/query.\n"
        "  - key_values: (REQUIRED if user asks for specific items) Filter by categorical values. "
        "Format: {\"FieldName\": [\"value1\", \"value2\"]}\n"
        "  - key_figures: (REQUIRED if user asks for ranges) Filter by numeric ranges. "
        "Format: [{\"field\": \"FieldName\", \"min\": X, \"max\": Y}]\n\n"
        "Rules:\n"
        "  - STRICT FILTERING MANDATE: You MUST use key_values or key_figures to narrow down data.\n"
        "  - NEVER fetch the entire dataset lazily without filtering unless explicitly asked.\n"
        "  - ALWAYS extract exact field names from the tool's 'Filterable fields'."
    ),
)
