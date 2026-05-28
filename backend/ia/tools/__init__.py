"""DeepAgents tools — unified exports.

All tools are created via factories that accept a `source` or `instance`
parameter to bind to proactive (chat) or reactive (event) context.

Backwards-compatible aliases are provided for legacy imports.
"""

from backend.ia.tools.unified.rag import create_rag_tool
from backend.ia.tools.unified.mcp import create_mcp_tool
from backend.ia.tools.unified.computer import (
    create_computer_tool,
    create_browser_navigate_tool,
    create_browser_dom_tool,
)

# ── Backwards-compatible instances (proactive / chat defaults) ──
mcp_execute = create_mcp_tool(source="chat")
browser_navigate = create_browser_navigate_tool(instance="chat")
browser_dom = create_browser_dom_tool(instance="chat")
computer = create_computer_tool(instance="chat")

# ── Backwards-compatible instances (reactive defaults) ──
create_reactive_rag_tool = create_rag_tool  # signature compatible
reactive_mcp_execute = create_mcp_tool(source="reactive")
reactive_browser_navigate = create_browser_navigate_tool(instance="reactive")
reactive_browser_dom = create_browser_dom_tool(instance="reactive")
reactive_computer = create_computer_tool(instance="reactive")

__all__ = [
    # Factories (new preferred API)
    "create_rag_tool",
    "create_mcp_tool",
    "create_computer_tool",
    "create_browser_navigate_tool",
    "create_browser_dom_tool",
    # Legacy aliases (proactive)
    "mcp_execute",
    "browser_navigate",
    "browser_dom",
    "computer",
    # Legacy aliases (reactive)
    "create_reactive_rag_tool",
    "reactive_mcp_execute",
    "reactive_browser_navigate",
    "reactive_browser_dom",
    "reactive_computer",
]
