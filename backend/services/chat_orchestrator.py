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
import logging
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.v1.schemas.chat import ChatRequest
from backend.core.config import settings

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
    token_type = getattr(token, "type", None)
    
    if token_type in ("ai", "AIMessageChunk"):
        text = getattr(token, "content", None) or ""
        # Anthropic / DeepSeek extended-thinking support (optional)
        reasoning_text = getattr(token, "reasoning_content", None) or ""
    elif token_type in ("tool", "ToolMessageChunk"):
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

    async def _resolve_chat_tool_schemas(
        self, session: AsyncSession
    ) -> list[dict]:
        """Resolve MCP tool schemas for the chat (proactive) context.

        Reads enabled ToolConfig records from the chat MCP sources,
        returning {name, description, parameter_schema} for each.
        """
        try:
            from backend.persistencia.repositories.tool_repository import ToolRepository
            repo = ToolRepository(session)
            tools = await repo.list_enabled()
            return [
                {
                    "name": t.name,
                    "description": t.description,
                    "parameter_schema": t.parameter_schema,
                }
                for t in tools
            ]
        except Exception as e:
            logger.warning("Failed to resolve chat tool schemas: %s", e)
            return []

    async def _resolve_chat_kb_names(
        self, session: AsyncSession, knowledge_base_id: str | None
    ) -> list[str]:
        """Resolve knowledge base names for prompt injection."""
        if not knowledge_base_id:
            return []
        try:
            from backend.persistencia.repositories.knowledge_repository import KnowledgeRepository
            repo = KnowledgeRepository(session)
            kb = await repo.get_by_id(int(knowledge_base_id))
            if kb:
                return [kb.name]
        except Exception as e:
            logger.warning("Failed to resolve chat KB names: %s", e)
        return []

    async def _create_orchestrator(
        self, request: ChatRequest, session: AsyncSession | None = None
    ):
        """Create a DeepAgents orchestrator respecting user RAG/MCP toggles.

        Toggle logic (matches IndustrialBackend AgentService pattern):
        - knowledge_base_id is None → enable_knowledge=False (no RAG tool)
        - knowledge_base_id is a UUID → enable_knowledge=True
        - mcp_source_id is "none" → enable_mcp=False (no MCP tool)
        - mcp_source_id is None or UUID → enable_mcp=True
        """
        try:
            from backend.ia.orchestrator_factory import create_orchestrator

            enable_knowledge = bool(request.knowledge_base_id)
            enable_mcp = request.mcp_source_id != "none"

            # Resolve dynamic schemas from DB if session available
            tool_schemas = None
            kb_names = None
            if session:
                if enable_mcp:
                    tool_schemas = await self._resolve_chat_tool_schemas(session)
                if enable_knowledge:
                    kb_names = await self._resolve_chat_kb_names(
                        session, request.knowledge_base_id
                    )

            logger.info(
                "Creating orchestrator | enable_knowledge=%s enable_mcp=%s "
                "kb_id=%s mcp_source_id=%s tool_schemas=%d kb_names=%d",
                enable_knowledge, enable_mcp,
                request.knowledge_base_id, request.mcp_source_id,
                len(tool_schemas) if tool_schemas else 0,
                len(kb_names) if kb_names else 0,
            )

            return create_orchestrator(
                knowledge_base_id=request.knowledge_base_id,
                enable_knowledge=enable_knowledge,
                enable_mcp=enable_mcp,
                tool_schemas=tool_schemas,
                kb_names=kb_names,
            )
        except Exception as e:
            logger.exception("Failed to create orchestrator: %s", e)
            return None

    async def stream(
        self,
        request: ChatRequest,
        messages: list[dict[str, str]],
        thread_id: str,
        session: AsyncSession | None = None,
    ) -> AsyncIterator[dict]:
        """Yield SSE events from DeepAgents streaming."""
        orchestrator = await self._create_orchestrator(request, session=session)
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

        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": 40,  # hard cap: prevents infinite tool-call loops
        }
        
        from backend.core.context import chat_stream_queue
        from backend.services.browser_manager import BrowserManager
        q: asyncio.Queue = asyncio.Queue()
        chat_stream_queue.set(q)
        # Establecer thread_id activo en el BrowserController "chat" para HITL
        BrowserManager.get_instance("chat").get_controller().set_active_thread_id(thread_id)
        
        full_content = ""
        reasoning_content = ""
        current_agent = "orchestrator"
        agents_used: set[str] = set()

        async def _run_astream():
            try:
                async for chunk in orchestrator.astream(
                    {"messages": messages},
                    config=config,
                    stream_mode="messages",
                    subgraphs=True,
                    version="v2",
                ):
                    await q.put({"chunk": chunk})
            except Exception as e:
                await q.put({"error": e})
            finally:
                await q.put({"done": True})

        task = asyncio.create_task(_run_astream())

        while True:
            item = await q.get()
            
            if "chunk" in item:
                agent_name, text, reasoning, agents_used, events = _extract_chunk_payload(
                    item["chunk"], current_agent=current_agent, agents_used=agents_used
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
                    
            elif "screenshot" in item:
                yield {"type": "screenshot", "data": item["screenshot"]}

            elif "type" in item and item["type"] == "takeover":
                # Human-in-the-loop: reenviar evento takeover tal cual al frontend
                yield item

            elif "thought" in item:
                # Modo Cinema: pensamiento del agente
                yield {"type": "thought", "content": item["thought"]}
                
            elif "error" in item:
                logger.exception("Orchestrator streaming failed: %s", item["error"])
                error_msg = f"\n\n[System error during processing: {item['error']}]"
                full_content += error_msg
                yield {"type": "token", "content": error_msg}
                
            elif "done" in item:
                break

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
        session: AsyncSession | None = None,
    ) -> dict:
        """Non-streaming chat via DeepAgents."""
        orchestrator = await self._create_orchestrator(request, session=session)
        if orchestrator is None:
            return {
                "thread_id": thread_id,
                "content": f"[Orchestrator unavailable — Echo: {request.query}]",
                "reasoning_content": None,
                "model": "mock",
            }

        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": 40,  # hard cap: prevents infinite tool-call loops
        }
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
