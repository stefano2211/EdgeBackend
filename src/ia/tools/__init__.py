"""DeepAgents tools — exported for orchestrator and sub-agent registration."""

# Chat tools
from src.ia.tools.rag_tool import create_rag_tool
from src.ia.tools.mcp_tool import mcp_execute
from src.ia.tools.web_browser import (
    browser_navigate,
    browser_dom,
    computer,
)

# Reactive tools (isolated from chat)
from src.ia.tools.reactive_rag_tool import create_reactive_rag_tool
from src.ia.tools.reactive_mcp_tool import reactive_mcp_execute
from src.ia.tools.reactive_web_browser import (
    reactive_browser_navigate,
    reactive_browser_dom,
    reactive_computer,
)

__all__ = [
    # Chat
    "create_rag_tool",
    "mcp_execute",
    "browser_navigate",
    "browser_dom",
    "computer",
    # Reactive
    "create_reactive_rag_tool",
    "reactive_mcp_execute",
    "reactive_browser_navigate",
    "reactive_browser_dom",
    "reactive_computer",
]
