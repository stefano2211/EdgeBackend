"""DEPRECATED — Replaced by src/ia/orchestrator_factory.py using DeepAgents.

This module is kept for backward compatibility. Import from orchestrator_factory
for the new DeepAgents-based implementation.
"""

from src.core.logging import logging

logger = logging.getLogger(__name__)
logger.warning(
    "src.ia.agent_orchestrator is deprecated. "
    "Use src.ia.orchestrator_factory.create_orchestrator() instead."
)

# Re-export for any existing imports
from src.ia.orchestrator_factory import create_orchestrator as _create_orchestrator

__all__ = ["AgentOrchestrator"]


class AgentOrchestrator:
    """DEPRECATED — Use create_orchestrator() from orchestrator_factory instead.

    Stub that raises on use to force migration.
    """

    def __init__(self) -> None:
        logger.error(
            "AgentOrchestrator is deprecated. "
            "Use src.ia.orchestrator_factory.create_orchestrator() "
            "with DeepAgents streaming."
        )
        raise RuntimeError(
            "AgentOrchestrator is deprecated. "
            "Use src.ia.orchestrator_factory.create_orchestrator()"
        )
