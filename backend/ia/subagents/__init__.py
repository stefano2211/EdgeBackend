"""Sub-agent registry for DeepAgents orchestrator."""

from backend.ia.subagents.plugin_registry import SubagentRegistry
from backend.ia.subagents.builders import *  # auto-register plugins

__all__ = ["SubagentRegistry"]
