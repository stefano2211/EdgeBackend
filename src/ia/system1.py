"""DEPRECATED — Routing is now handled by the DeepAgents orchestrator.

System 1 routing has been replaced by DeepAgents' built-in planning
and task delegation (TodoListMiddleware + SubAgentMiddleware).

This module is kept for backward compatibility only.
"""

from src.core.logging import logging

logger = logging.getLogger(__name__)
logger.warning(
    "src.ia.system1 is deprecated. "
    "DeepAgents orchestrator handles routing and planning automatically."
)


def system1_route(request, history) -> str:
    """DEPRECATED — DeepAgents orchestrator handles all routing."""
    logger.warning(
        "system1_route is deprecated and always returns 'complex'. "
        "Use the DeepAgents orchestrator in orchestrator_factory instead."
    )
    return "complex"
