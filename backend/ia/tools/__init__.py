"""DeepAgents tools — unified exports.

All tools are created via factories that accept a `source` or `instance`
parameter to bind to proactive (chat) or reactive (event) context.

Backwards-compatible aliases are provided for legacy imports.
"""

from backend.ia.tools.unified.rag import create_rag_tool
from backend.ia.tools.unified.mcp import create_mcp_tool

# ── Backwards-compatible instances (proactive / chat defaults) ──
mcp_execute = create_mcp_tool(source="chat")

# ── Backwards-compatible instances (reactive defaults) ──
create_reactive_rag_tool = create_rag_tool  # signature compatible
reactive_mcp_execute = create_mcp_tool(source="reactive")

__all__ = [
    # Factories (new preferred API)
    "create_rag_tool",
    "create_mcp_tool",
    # Legacy aliases (proactive)
    "mcp_execute",
    # Legacy aliases (reactive)
    "create_reactive_rag_tool",
    "reactive_mcp_execute",
]
