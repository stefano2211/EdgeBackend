"""System 1 — Fast Intuition Routing (Stub).

Decides whether a chat request is simple (direct response) or complex
(requires Sistema 2 orchestration with subagents/tools/RAG).

Fase 3: heuristic stub.
Fase 4: LLM-based routing with prompt classification.
"""

from src.api.v1.schemas.chat import ChatRequest
from src.persistencia.models.message import Message


def system1_route(request: ChatRequest, history: list[Message]) -> str:
    """
    Returns: 'simple' | 'complex'

    Heuristic stub for Fase 3:
    - use_generalist=True  -> simple (direct response, no tools)
    - knowledge_base_id or mcp_source_id present -> complex (needs RAG/MCP)
    - history length > 10 -> complex (context heavy)
    - Otherwise -> simple
    """
    if request.use_generalist:
        return "simple"
    if request.knowledge_base_id or request.mcp_source_id:
        return "complex"
    if len(history) > 10:
        return "complex"
    return "simple"
