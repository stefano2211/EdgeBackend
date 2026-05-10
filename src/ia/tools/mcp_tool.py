"""MCP tool for DeepAgents — dispatches to registered MCP tools.

Replicated from IndustrialBackend:
- Fetches tool configuration from DB by name
- Resolves execution URL via MCPSource or relative path + source.url
- Dispatches via MCPService (REST, stdio, or SSE)
- Returns structured JSON with key_figures + key_values
- Supports smart filtering (key_values, key_figures)
"""

from __future__ import annotations

import json

from langchain_core.tools import StructuredTool

from src.core.database import AsyncSessionLocal
from src.core.logging import logging
from src.persistencia.models.tool_config import MCPSource
from src.persistencia.repositories.tool_repository import ToolRepository
from src.services.mcp_service import MCPService

logger = logging.getLogger(__name__)

import asyncio

# Lazy-init singleton
_mcp_service: MCPService | None = None
_mcp_service_lock = asyncio.Lock()

# In-memory URL resolution cache
_url_cache: dict = {}
_url_cache_lock = asyncio.Lock()


async def _get_mcp_service() -> MCPService:
    global _mcp_service
    if _mcp_service is None:
        async with _mcp_service_lock:
            if _mcp_service is None:
                _mcp_service = MCPService()
    return _mcp_service


async def _mcp_execute(
    tool_config_name: str,
    parameters: dict | None = None,
    key_values: dict | None = None,
    key_figures: list | None = None,
) -> str:
    """Execute a registered MCP (Model Context Protocol) tool with smart filtering.

    Use this to get real-time data, sensor readings, or perform external actions.

    Args:
        tool_config_name: Name of the tool as registered in the system (e.g., 'get_maquinaria').
        parameters: Any standard parameters required by the API path/query.
        key_values: Filter by categorical field values. Format: {"FieldName": ["value1", "value2"]}
        key_figures: Filter by numeric field ranges. Format: [{"field": "FieldName", "min": X, "max": Y}]

    Returns:
        Structured JSON with source, key_figures (metrics) and key_values (categorical data).
    """
    if parameters is None:
        parameters = {}

    # Pack smart filters back into arguments for processing
    if key_values:
        parameters["key_values"] = key_values
    if key_figures:
        parameters["key_figures"] = key_figures

    logger.info(
        "[MCP Tool] Calling dynamic tool: %s with filters: kv=%s, kf=%s, args=%s",
        tool_config_name,
        bool(key_values),
        bool(key_figures),
        parameters,
    )

    async with AsyncSessionLocal() as session:
        return await _do_call_dynamic_mcp(session, tool_config_name, parameters)


async def _do_call_dynamic_mcp(
    session,
    tool_config_name: str,
    arguments: dict = {},
) -> str:
    repo = ToolRepository(session)
    tool_config = await repo.get_by_name(tool_config_name)

    if not tool_config:
        return json.dumps({"error": f"Tool configuration '{tool_config_name}' not found."})

    mcp_service = await _get_mcp_service()

    config_data = tool_config.config or {}
    execution_url = config_data.get("url", "")
    transport_type = config_data.get("transport", "mcp")
    method = config_data.get("method", "GET")

    parameter_schema = tool_config.parameter_schema or {}
    schema_hints = parameter_schema.get("response") or {}

    # -- Extract smart filters from arguments (pop before sending to API) --
    clean_arguments = arguments.copy()
    key_values_filter = clean_arguments.pop("key_values", None)
    key_figures_filter = clean_arguments.pop("key_figures", None)

    if key_values_filter:
        logger.info("[MCP Tool] Applying key_values filter: %s", key_values_filter)
    if key_figures_filter:
        logger.info("[MCP Tool] Applying key_figures filter: %s", key_figures_filter)

    # -- Robust URL resolution (with in-memory cache) -----------------------
    if execution_url and "://" not in execution_url:
        cache_key = f"{tool_config.source_id}:{execution_url}"
        if cache_key in _url_cache:
            execution_url = _url_cache[cache_key]
            logger.debug("[MCP Tool] URL resolved from cache: %s", execution_url)
        else:
            source = await session.get(MCPSource, tool_config.source_id)
            if source and source.url:
                base_url = source.url.rstrip("/")
                path = execution_url.lstrip("/")
                execution_url = f"{base_url}/{path}"
                _url_cache[cache_key] = execution_url
                logger.info("[MCP Tool] Resolved relative URL to: %s", execution_url)

    if execution_url and "://" in execution_url:
        scheme, rest = execution_url.split("://", 1)
        while "//" in rest:
            rest = rest.replace("//", "/")
        execution_url = f"{scheme}://{rest}"

    # Heuristic: Detect REST transport
    if transport_type == "mcp" and execution_url and "://" in execution_url:
        if any(domain in execution_url for domain in ["pokeapi.co", "api.", "/api/"]):
            logger.info("[MCP Tool] Heuristic detected REST transport for %s", execution_url)
            transport_type = "rest"

    logger.info(
        "[MCP Tool] Executing %s via %s at %s", tool_config_name, transport_type, execution_url
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
        "[MCP Tool] Returning %d key figures and %d key values for %s",
        len(result["key_figures"]),
        len(result["key_values"]),
        tool_config_name,
    )
    return json.dumps(result, ensure_ascii=False)


mcp_execute = StructuredTool.from_function(
    coroutine=_mcp_execute,
    name="mcp_execute",
    description=(
        "Execute a registered MCP (Model Context Protocol) tool dynamically with STRICT precision. "
        "Use this to get real-time data, sensor readings, or perform external actions.\n\n"
        "Input:\n"
        "  - tool_config_name: The name of the tool as registered (e.g., 'get_maquinaria').\n"
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
