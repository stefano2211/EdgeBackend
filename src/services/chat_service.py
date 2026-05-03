"""Chat service: conversation management + DeepAgents orchestrator streaming."""

import asyncio
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.chat import ChatRequest
from src.core.config import settings
from src.core.logging import logging
from src.persistencia.models.conversation import Conversation
from src.persistencia.models.message import Message
from src.persistencia.repositories.conversation_repository import ConversationRepository
from src.persistencia.repositories.message_repository import MessageRepository
from src.ia.orchestrator_factory import create_orchestrator

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.conv_repo = ConversationRepository(session)
        self.msg_repo = MessageRepository(session)

    async def get_or_create_conversation(
        self, thread_id: str | None, user_id: int, title: str = "New Chat"
    ) -> Conversation:
        if thread_id:
            conv = await self.conv_repo.get_by_thread_id(thread_id)
            if conv and conv.user_id == user_id:
                return conv
        # create new
        conv = Conversation(user_id=user_id, title=title)
        await self.conv_repo.create(conv)
        await self.session.commit()
        await self.session.refresh(conv)
        return conv

    async def list_conversations(
        self, user_id: int, include_archived: bool = False
    ) -> list[Conversation]:
        return await self.conv_repo.list_by_user(user_id, include_archived)

    async def archive_conversation(
        self, thread_id: str, archive: bool = True
    ) -> Conversation | None:
        conv = await self.conv_repo.archive(thread_id, archive)
        if conv:
            await self.session.commit()
        return conv

    async def delete_conversation(self, thread_id: str, user_id: int) -> bool:
        conv = await self.conv_repo.get_by_thread_id(thread_id)
        if not conv or conv.user_id != user_id:
            return False
        await self.conv_repo.delete(conv)
        await self.session.commit()
        return True

    async def get_messages(self, thread_id: str, user_id: int) -> list[Message]:
        conv = await self.conv_repo.get_by_thread_id(thread_id)
        if not conv or conv.user_id != user_id:
            return []
        return await self.msg_repo.list_by_conversation(conv.id)

    async def _build_messages(
        self, request: ChatRequest, conversation_id: int
    ) -> list[dict[str, str]]:
        """Build LangChain-compatible message list: system + history + user query."""
        messages: list[dict[str, str]] = []

        # System prompt
        system_prompt = "You are a helpful assistant."
        messages.append({"role": "system", "content": system_prompt})

        # History (last 20 messages — DeepAgents handles summarization if needed)
        history = await self.msg_repo.list_by_conversation(conversation_id)
        for msg in history[-20:]:
            if msg.role in ("user", "assistant"):
                messages.append({"role": msg.role, "content": msg.content})

        messages.append({"role": "user", "content": request.query})
        return messages

    async def process_stream(
        self, request: ChatRequest, user_id: int
    ) -> AsyncIterator[dict]:
        """Process chat through DeepAgents orchestrator with real-time SSE streaming.

        Yields: meta, subagent, token, tool_call, tool_response, done events.
        """
        # 1. Conversation management
        conv = await self.get_or_create_conversation(
            request.thread_id, user_id, title=request.query[:50]
        )
        await self.msg_repo.create_message(
            conversation_id=conv.id, role="user", content=request.query
        )
        await self.session.commit()

        # 2. Load history and build messages
        messages = await self._build_messages(request, conv.id)

        # 3. Emit meta event
        yield {"type": "meta", "thread_id": conv.thread_id}

        full_content = ""
        reasoning_content = ""
        current_agent = "orchestrator"
        agents_used: set[str] = set()

        # 4. Create and stream through DeepAgents orchestrator
        try:
            orchestrator = create_orchestrator(
                knowledge_base_id=request.knowledge_base_id,
            )
        except Exception as e:
            logger.exception("Failed to create orchestrator: %s", e)
            # Fallback: mock response
            response_text = f"[Orchestrator unavailable — Echo: {request.query}]"
            for word in response_text.split():
                token = word + " "
                full_content += token
                yield {"type": "token", "content": token}
                await asyncio.sleep(0.02)
            yield {"type": "done", "full_content": full_content.strip()}
            return

        # Config enables checkpoint persistence via Redis per conversation thread
        config = {"configurable": {"thread_id": conv.thread_id}}

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

                    # Detect agent change from LangGraph metadata
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

                    # Extract text token
                    text = getattr(token, "text", None)
                    if text:
                        full_content += text
                        yield {
                            "type": "token",
                            "content": text,
                            "agent": agent_name,
                        }

                    # Extract reasoning content if present
                    reasoning_text = getattr(token, "reasoning_content", None)
                    if reasoning_text:
                        reasoning_content += reasoning_text
                        yield {
                            "type": "reasoning",
                            "content": reasoning_text,
                            "agent": agent_name,
                        }

                    # Extract tool calls
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
                    # Tool responses, state changes
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

        # Mark last agent complete
        if current_agent:
            yield {"type": "subagent", "name": current_agent, "status": "complete"}

        # Done
        yield {"type": "done", "full_content": full_content.strip()}

        # Save assistant message
        await self.msg_repo.create_message(
            conversation_id=conv.id,
            role="assistant",
            content=full_content.strip(),
            reasoning_content=reasoning_content or None,
            meta={
                "model": "deepagents-orchestrator",
                "provider": settings.DEFAULT_LLM_PROVIDER,
                "route": "complex",
                "agents_used": list(agents_used),
            },
        )
        await self.session.commit()

    async def process_non_stream(
        self, request: ChatRequest, user_id: int
    ) -> dict:
        """Non-streaming fallback using DeepAgents orchestrator."""
        conv = await self.get_or_create_conversation(
            request.thread_id, user_id, title=request.query[:50]
        )

        await self.msg_repo.create_message(
            conversation_id=conv.id, role="user", content=request.query
        )
        await self.session.commit()

        messages = await self._build_messages(request, conv.id)
        agents_used: set[str] = set()

        try:
            orchestrator = create_orchestrator(
                knowledge_base_id=request.knowledge_base_id,
            )
        except Exception as e:
            logger.exception("Failed to create orchestrator: %s", e)
            return {
                "thread_id": conv.thread_id,
                "content": f"[Orchestrator unavailable — Echo: {request.query}]",
                "reasoning_content": None,
                "model": "mock",
            }

        full_content = ""
        reasoning_content = ""
        current_agent = "orchestrator"

        # Config enables checkpoint persistence via Redis per conversation thread
        config = {"configurable": {"thread_id": conv.thread_id}}

        try:
            # Use sync stream and collect all tokens
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

        await self.msg_repo.create_message(
            conversation_id=conv.id,
            role="assistant",
            content=full_content.strip(),
            reasoning_content=reasoning_content or None,
            meta={
                "model": "deepagents-orchestrator",
                "provider": settings.DEFAULT_LLM_PROVIDER,
                "route": "complex",
                "agents_used": list(agents_used),
            },
        )
        await self.session.commit()

        return {
            "thread_id": conv.thread_id,
            "content": full_content.strip(),
            "reasoning_content": reasoning_content or None,
            "model": "deepagents-orchestrator",
        }
