"""Sub-agent registry for DeepAgents orchestrator."""

from backend.ia.agents.plugin_registry import SubagentRegistry
from backend.ia.agents.builders import *  # auto-register plugins

__all__ = ["SubagentRegistry"]
