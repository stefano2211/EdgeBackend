"""DeepAgents tools — exported for orchestrator and sub-agent registration."""

from src.ia.tools.rag_tool import rag_retrieve
from src.ia.tools.mcp_tool import mcp_execute
from src.ia.tools.web_browser import (
    browser_navigate,
    browser_click,
    browser_type,
    browser_screenshot,
    browser_extract_text,
)

__all__ = [
    "rag_retrieve",
    "mcp_execute",
    "browser_navigate",
    "browser_click",
    "browser_type",
    "browser_screenshot",
    "browser_extract_text",
]
