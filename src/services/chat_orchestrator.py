"""Chat orchestrator: DeepAgents interaction only (streaming + non-streaming)."""

import asyncio
from typing import AsyncIterator

from src.api.v1.schemas.chat import ChatRequest
from src.core.config import settings
from src.core.logging import logging
from src.ia.orchestrator_factory import create_orchestrator

logger = logging.getLogger(__name__)


class ChatOrchestrator:
    """Handles interaction with DeepAgents orchestrator, isolated from persistence."""

    async def _create_orchestrator(self, knowledge_base_id: str | None):
        try:
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
                if chunk.get("type") == "messages":
                    token, metadata = chunk["data"]

                    agent_name = metadata.get("lc_agent_name", "orchestrator")
                    if agent_name != current_agent:
                        if current_agent:
                            yield {
                                "type": "subagent",
                                "name": current_agent,
                                "status": "complete",
                            }
                        current_agent = agent_name
                        agents_used.add(agent_name)
                        yield {
                            "type": "subagent",
                            "name": agent_name,
                            "status": "running",
                        }

                    text = getattr(token, "text", None)
                    if text:
                        full_content += text
                        yield {
                            "type": "token",
                            "content": text,
                            "agent": agent_name,
                        }

                    reasoning_text = getattr(token, "reasoning_content", None)
                    if reasoning_text:
                        reasoning_content += reasoning_text
                        yield {
                            "type": "reasoning",
                            "content": reasoning_text,
                            "agent": agent_name,
                        }

                    tool_chunks = getattr(token, "tool_call_chunks", None)
                    if tool_chunks:
                        for tc in tool_chunks:
                            if tc.get("name"):
                                yield {
                                    "type": "tool_call",
                                    "name": tc["name"],
                                    "args": tc.get("args", ""),
                                    "agent": agent_name,
                                }

                elif chunk.get("type") == "updates":
                    for source, update in chunk["data"].items():
                        if source == "tools":
                            msgs = update.get("messages", [])
                            if msgs:
                                content = str(msgs[-1].get("content", ""))[:200]
                                yield {
                                    "type": "tool_response",
                                    "source": source,
                                    "content": content,
                                }

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
                if chunk.get("type") == "messages":
                    token, metadata = chunk["data"]
                    agent_name = metadata.get("lc_agent_name", "orchestrator")
                    if agent_name != current_agent:
                        current_agent = agent_name
                        agents_used.add(agent_name)

                    text = getattr(token, "text", None)
                    if text:
                        full_content += text

                    reasoning_text = getattr(token, "reasoning_content", None)
                    if reasoning_text:
                        reasoning_content += reasoning_text

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
