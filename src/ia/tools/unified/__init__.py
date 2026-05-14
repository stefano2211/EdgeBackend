"""Unified tool factories for DeepAgents.

All tools are context-agnostic at the factory level. The caller binds them to
proactive (chat) or reactive (event) context via parameters.

This eliminates duplication between:
  - rag_tool.py / reactive_rag_tool.py
  - mcp_tool.py / reactive_mcp_tool.py
  - web_browser.py / reactive_web_browser.py
"""

from src.ia.tools.unified.rag import create_rag_tool
from src.ia.tools.unified.mcp import create_mcp_tool
from src.ia.tools.unified.computer import create_computer_tool

__all__ = ["create_rag_tool", "create_mcp_tool", "create_computer_tool"]
