"""Chat orchestrator: DeepAgents interaction only (streaming + non-streaming).

DeepAgents v2 streaming format (stream_mode="messages", version="v2", subgraphs=True):
- chunk["type"] == "messages" → chunk["data"] is (token, metadata)
  * token.content       : str | None  (AI message text)
  * token.type          : "ai" | "tool" | ...
  * token.tool_call_chunks: list[dict] | None
  * metadata["lc_agent_name"]: str | None  (subagent name)
- chunk["type"] == "updates" → chunk["data"] is dict[node_name, node_output]
- chunk["ns"]           : tuple[str, ...] | ()  (namespace; contains "tools:..." for subagents)

See: https://docs.langchain.com/oss/python/deepagents/streaming
"""

import asyncio
from typing import AsyncIterator

from src.api.v1.schemas.chat import ChatRequest
from src.core.config import settings
from src.core.logging import logging

logger = logging.getLogger(__name__)


def _detect_agent_name(chunk: dict, metadata: dict) -> str:
    """Return the semantic agent name from DeepAgents metadata / namespace.

    Priority:
    1. metadata["lc_agent_name"]  (official DeepAgents subagent name)
    2. Extract from chunk["ns"]   (fallback: "tools:<id>" → "subagent")
    3. "orchestrator"            (default main agent)
    """
    agent_name = metadata.get("lc_agent_name")
    if agent_name:
        return agent_name

    ns = chunk.get("ns") or ()
    for segment in ns:
        if segment.startswith("tools:"):
            return f"subagent:{segment.split(':', 1)[1]}"

    return "orchestrator"


def _extract_chunk_payload(
    chunk: dict,
    *,
    current_agent: str,
    agents_used: set[str],
) -> tuple[str, str, str, set[str], list[dict]]:
    """Parse a single DeepAgents v2 chunk and return updated state + events.

    Returns: (new_agent, text, reasoning_text, updated_agents, extra_events)
    """
    chunk_type = chunk.get("type")

    # ── Updates mode (subagent lifecycle / tool results) ──
    if chunk_type == "updates":
        extra_events: list[dict] = []
        ns = chunk.get("ns") or ()
        is_subagent = any(s.startswith("tools:") for s in ns)

        for node_name, node_output in chunk["data"].items():
            # Tool results from subagents
            if node_name == "tools" and isinstance(node_output, dict):
                msgs = node_output.get("messages", [])
                if msgs:
                    last = msgs[-1]
                    content = str(getattr(last, "content", last) or "")[:200]
                    extra_events.append({
                        "type": "tool_response",
                        "source": "subagent" if is_subagent else "orchestrator",
                        "content": content,
                    })
        return current_agent, "", "", agents_used, extra_events

    # ── Messages mode (tokens / tool-call chunks) ──
    if chunk_type != "messages":
        return current_agent, "", "", agents_used, []

    token, metadata = chunk["data"]
    agent_name = _detect_agent_name(chunk, metadata)
    events: list[dict] = []

    # Subagent lifecycle events
    if agent_name != current_agent:
        if current_agent:
            events.append({"type": "subagent", "name": current_agent, "status": "complete"})
        current_agent = agent_name
        agents_used.add(agent_name)
        events.append({"type": "subagent", "name": agent_name, "status": "running"})

    # DeepAgents token attributes (LangChain message chunks)
    text = ""
    reasoning_text = ""
    if getattr(token, "type", None) == "ai":
        text = getattr(token, "content", None) or ""
        # Anthropic / DeepSeek extended-thinking support (optional)
        reasoning_text = getattr(token, "reasoning_content", None) or ""
    elif getattr(token, "type", None) == "tool":
        # Tool result content — stream as an event rather than raw text
        tool_content = getattr(token, "content", None) or ""
        if tool_content:
            events.append({
                "type": "tool_result",
                "agent": agent_name,
                "content": str(tool_content)[:200],
            })

    # Tool-call invocations (streaming function calls)
    tool_chunks = getattr(token, "tool_call_chunks", None)
    if tool_chunks:
        for tc in tool_chunks:
            if tc.get("name"):
                events.append({
                    "type": "tool_call",
                    "name": tc["name"],
                    "args": tc.get("args", ""),
                    "agent": agent_name,
                })

    return current_agent, text, reasoning_text, agents_used, events


class ChatOrchestrator:
    """Handles interaction with DeepAgents orchestrator, isolated from persistence."""

    async def _create_orchestrator(self, knowledge_base_id: str | None):
        try:
            from src.ia.orchestrator_factory import create_orchestrator
            return create_orchestrator(knowledge_base_id=knowledge_base_id)
        except Exception as e:
            logger.exception("Failed to create orchestrator: %s", e)
            return None

    async def stream(
        self,
        request: ChatRequest,
        messages: list[dict[str, str]],
        thread_id: str,
    ) -> AsyncIterator[dict]:
        """Yield SSE events from DeepAgents streaming."""
        orchestrator = await self._create_orchestrator(request.knowledge_base_id)
        if orchestrator is None:
            response_text = f"[Orchestrator unavailable — Echo: {request.query}]"
            full_content = ""
            for word in response_text.split():
                token = word + " "
                full_content += token
                yield {"type": "token", "content": token}
                await asyncio.sleep(0.02)
            yield {"type": "done", "full_content": full_content.strip()}
            return

        config = {"configurable": {"thread_id": thread_id}}
        full_content = ""
        reasoning_content = ""
        current_agent = "orchestrator"
        agents_used: set[str] = set()

        try:
            async for chunk in orchestrator.astream(
                {"messages": messages},
                config=config,
                stream_mode="messages",
                subgraphs=True,
                version="v2",
            ):
                agent_name, text, reasoning, agents_used, events = _extract_chunk_payload(
                    chunk, current_agent=current_agent, agents_used=agents_used
                )
                current_agent = agent_name
                if text:
                    full_content += text
                    yield {"type": "token", "content": text, "agent": agent_name}
                if reasoning:
                    reasoning_content += reasoning
                    yield {"type": "reasoning", "content": reasoning, "agent": agent_name}
                for ev in events:
                    yield ev

        except Exception as e:
            logger.exception("Orchestrator streaming failed: %s", e)
            error_msg = f"\n\n[System error during processing: {e}]"
            full_content += error_msg
            yield {"type": "token", "content": error_msg}

        if current_agent:
            yield {"type": "subagent", "name": current_agent, "status": "complete"}

        yield {"type": "done", "full_content": full_content.strip()}
        yield {
            "_internal": True,
            "full_content": full_content.strip(),
            "reasoning_content": reasoning_content or None,
            "agents_used": list(agents_used),
        }

    async def non_stream(
        self,
        request: ChatRequest,
        messages: list[dict[str, str]],
        thread_id: str,
    ) -> dict:
        """Non-streaming chat via DeepAgents."""
        orchestrator = await self._create_orchestrator(request.knowledge_base_id)
        if orchestrator is None:
            return {
                "thread_id": thread_id,
                "content": f"[Orchestrator unavailable — Echo: {request.query}]",
                "reasoning_content": None,
                "model": "mock",
            }

        config = {"configurable": {"thread_id": thread_id}}
        full_content = ""
        reasoning_content = ""
        current_agent = "orchestrator"
        agents_used: set[str] = set()

        try:
            for chunk in orchestrator.stream(
                {"messages": messages},
                config=config,
                stream_mode="messages",
                subgraphs=True,
                version="v2",
            ):
                agent_name, text, reasoning, agents_used, _ = _extract_chunk_payload(
                    chunk, current_agent=current_agent, agents_used=agents_used
                )
                current_agent = agent_name
                full_content += text
                reasoning_content += reasoning

        except Exception as e:
            logger.exception("Orchestrator non-stream failed: %s", e)
            full_content += f"\n\n[System error: {e}]"

        return {
            "thread_id": thread_id,
            "content": full_content.strip(),
            "reasoning_content": reasoning_content or None,
            "model": "deepagents-orchestrator",
            "agents_used": list(agents_used),
        }
