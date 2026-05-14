"""Sub-agent registry for DeepAgents orchestrator."""

from src.ia.subagents.plugin_registry import SubagentRegistry
from src.ia.subagents.builders import *  # auto-register plugins

__all__ = ["SubagentRegistry"]
