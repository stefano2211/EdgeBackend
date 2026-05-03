"""Sub-agent registry for DeepAgents orchestrator."""

from src.ia.subagents.registry import (
    SUBAGENT_BUILDERS,
    get_available_subagents,
    get_subagent_descriptions,
)

__all__ = [
    "SUBAGENT_BUILDERS",
    "get_available_subagents",
    "get_subagent_descriptions",
]
