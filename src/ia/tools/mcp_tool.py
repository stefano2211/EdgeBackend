"""MCP tool for DeepAgents — dispatches to registered MCP tools.

TODO: Wire up to MCPSourceService for real tool execution.
Currently returns a placeholder to prevent breaking the orchestrator.
"""

from langchain_core.tools import StructuredTool

from src.core.logging import logging

logger = logging.getLogger(__name__)


async def _mcp_execute(tool_name: str, parameters: dict) -> str:
    """Execute a registered MCP (Model Context Protocol) tool.

    Args:
        tool_name: Name of the registered MCP tool to execute.
        parameters: Dictionary of parameters for the tool call.

    Returns:
        Tool execution result as a formatted string.

    TODO:
        - Integrate with src.services.mcp_source_service.MCPSourceService
        - Fetch tool configuration from DB (URL, auth headers, parameter schema)
        - Dispatch via httpx.AsyncClient to the MCP endpoint
        - Handle errors gracefully and return structured response
    """
    logger.warning(
        "MCP tool call stub: %s with params %s. "
        "Real implementation pending in MCPSourceService integration.",
        tool_name, parameters,
    )
    raise NotImplementedError(
        f"MCP tool '{tool_name}' execution is not yet implemented. "
        "Integrate with MCPSourceService to enable real MCP dispatch."
    )


mcp_execute = StructuredTool.from_function(
    coroutine=_mcp_execute,
    name="mcp_execute",
    description=(
        "Execute a registered MCP (Model Context Protocol) tool. "
        "Use to call external APIs, databases, or services registered in the MCP tool registry. "
        "The tool must be pre-registered in the ToolConfig database. "
        "NOTE: Full MCP dispatch is pending implementation."
    ),
)
