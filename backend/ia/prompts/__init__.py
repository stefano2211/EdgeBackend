"""Prompts for DeepAgents orchestrator and sub-agents.

All system prompts loaded from Jinja2 templates in templates/.
Dynamic builders accept tool/KB catalogs for runtime injection.
"""

from backend.ia.prompts.orchestrator import ORCHESTRATOR_SYSTEM_PROMPT, build_orchestrator_prompt
from backend.ia.prompts.subagents import (
    RAG_AGENT_DESCRIPTION,
    RAG_AGENT_SYSTEM_PROMPT,
    MCP_AGENT_DESCRIPTION,
    MCP_AGENT_SYSTEM_PROMPT,
    HISTORICAL_AGENT_DESCRIPTION,
    HISTORICAL_AGENT_SYSTEM_PROMPT,
    DB_AGENT_DESCRIPTION,
    DB_AGENT_SYSTEM_PROMPT,
    build_mcp_system_prompt,
    build_rag_system_prompt,
    build_db_system_prompt,
)

__all__ = [
    "ORCHESTRATOR_SYSTEM_PROMPT",
    "build_orchestrator_prompt",
    "RAG_AGENT_DESCRIPTION",
    "RAG_AGENT_SYSTEM_PROMPT",
    "MCP_AGENT_DESCRIPTION",
    "MCP_AGENT_SYSTEM_PROMPT",
    "HISTORICAL_AGENT_DESCRIPTION",
    "HISTORICAL_AGENT_SYSTEM_PROMPT",
    "DB_AGENT_DESCRIPTION",
    "DB_AGENT_SYSTEM_PROMPT",
    "build_mcp_system_prompt",
    "build_rag_system_prompt",
    "build_db_system_prompt",
]
