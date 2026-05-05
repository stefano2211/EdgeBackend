"""Prompts for DeepAgents orchestrator and sub-agents.

All system prompts live here as plain strings — easy to edit, version, and reuse.
"""

from src.ia.prompts.orchestrator import ORCHESTRATOR_SYSTEM_PROMPT, build_orchestrator_prompt
from src.ia.prompts.subagents import (
    INDUSTRIAL_AGENT_DESCRIPTION,
    INDUSTRIAL_AGENT_SYSTEM_PROMPT,
    HISTORICAL_AGENT_DESCRIPTION,
    HISTORICAL_AGENT_SYSTEM_PROMPT,
    VL_AGENT_DESCRIPTION,
    VL_AGENT_SYSTEM_PROMPT,
)

__all__ = [
    "ORCHESTRATOR_SYSTEM_PROMPT",
    "INDUSTRIAL_AGENT_DESCRIPTION",
    "INDUSTRIAL_AGENT_SYSTEM_PROMPT",
    "HISTORICAL_AGENT_DESCRIPTION",
    "HISTORICAL_AGENT_SYSTEM_PROMPT",
    "VL_AGENT_DESCRIPTION",
    "VL_AGENT_SYSTEM_PROMPT",
]
