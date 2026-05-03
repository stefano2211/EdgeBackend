"""MCP tool for DeepAgents — dispatches to registered MCP tools."""

from langchain_core.tools import tool

from src.core.logging import logging

logger = logging.getLogger(__name__)


@tool
def mcp_execute(tool_name: str, parameters: dict) -> str:
    """Execute a registered MCP (Model Context Protocol) tool.

    Use this to call external APIs, databases, or services registered
    in the MCP tool registry. The tool must be pre-registered in the
    ToolConfig database.

    Args:
        tool_name: Name of the registered MCP tool to execute.
        parameters: Dictionary of parameters for the tool call.

    Returns:
        Tool execution result as a formatted string.
    """
    logger.info("MCP tool call: %s with params %s", tool_name, parameters)
    # TODO: wire up to ToolService for real execution
    return (
        f"[MCP tool '{tool_name}' executed with parameters: {parameters}. "
        "Full MCP dispatch pending implementation.]"
    )
