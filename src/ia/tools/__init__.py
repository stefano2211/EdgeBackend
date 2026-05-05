"""DeepAgents tools — exported for orchestrator and sub-agent registration."""

from src.ia.tools.rag_tool import create_rag_tool
from src.ia.tools.mcp_tool import mcp_execute
from src.ia.tools.web_browser import (
    browser_navigate,
    browser_click,
    browser_type,
    browser_screenshot,
    browser_extract_text,
)

__all__ = [
    "create_rag_tool",
    "mcp_execute",
    "browser_navigate",
    "browser_click",
    "browser_type",
    "browser_screenshot",
    "browser_extract_text",
]
