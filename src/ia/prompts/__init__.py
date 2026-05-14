"""Prompts for DeepAgents orchestrator and sub-agents.

All system prompts loaded from Jinja2 templates in templates/.
"""

from src.ia.prompts.orchestrator import ORCHESTRATOR_SYSTEM_PROMPT, build_orchestrator_prompt
from src.ia.prompts.subagents import (
    RAG_AGENT_DESCRIPTION,
    RAG_AGENT_SYSTEM_PROMPT,
    MCP_AGENT_DESCRIPTION,
    MCP_AGENT_SYSTEM_PROMPT,
    HISTORICAL_AGENT_DESCRIPTION,
    HISTORICAL_AGENT_SYSTEM_PROMPT,
    VL_AGENT_DESCRIPTION,
    VL_AGENT_SYSTEM_PROMPT,
)

__all__ = [
    "ORCHESTRATOR_SYSTEM_PROMPT",
    "RAG_AGENT_DESCRIPTION",
    "RAG_AGENT_SYSTEM_PROMPT",
    "MCP_AGENT_DESCRIPTION",
    "MCP_AGENT_SYSTEM_PROMPT",
    "HISTORICAL_AGENT_DESCRIPTION",
    "HISTORICAL_AGENT_SYSTEM_PROMPT",
    "VL_AGENT_DESCRIPTION",
    "VL_AGENT_SYSTEM_PROMPT",
]
