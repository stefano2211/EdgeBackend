"""Chat service: conversation management + streaming responses (mock in Fase 3)."""

import asyncio
import json
import uuid
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.chat import ChatRequest
from src.core.config import settings
from src.persistencia.models.conversation import Conversation
from src.persistencia.models.message import Message
from src.persistencia.repositories.conversation_repository import ConversationRepository
from src.persistencia.repositories.message_repository import MessageRepository
from src.ia.system1 import system1_route


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

    async def process_stream(
        self, request: ChatRequest, user_id: int
    ) -> AsyncIterator[dict]:
        """Yields SSE event dicts."""
        # 1. Get or create conversation
        conv = await self.get_or_create_conversation(
            request.thread_id, user_id, title=request.query[:50]
        )

        # 2. Save user message
        await self.msg_repo.create_message(
            conversation_id=conv.id, role="user", content=request.query
        )
        await self.session.commit()

        # 3. Load history
        history = await self.msg_repo.list_by_conversation(conv.id)

        # 4. System 1 routing
        route = system1_route(request, history)

        # 5. Emit meta event
        yield {"type": "meta", "thread_id": conv.thread_id}

        full_content = ""
        reasoning_content = ""

        if route == "simple":
            # Mock simple response for Fase 3
            response_text = f"Echo: {request.query}"
            for word in response_text.split():
                token = word + " "
                full_content += token
                yield {"type": "token", "content": token}
                await asyncio.sleep(0.02)  # simulate streaming
        else:
            # Complex route — subagent events (stub)
            yield {
                "type": "subagent",
                "name": "rag-mcp-expert",
                "status": "running",
                "input": {"query": request.query},
            }
            await asyncio.sleep(0.1)
            response_text = "[Complex analysis stub — Sistema 2 orchestrator will handle this in Fase 4]"
            for word in response_text.split():
                token = word + " "
                full_content += token
                yield {"type": "token", "content": token}
                await asyncio.sleep(0.02)
            yield {
                "type": "subagent",
                "name": "rag-mcp-expert",
                "status": "complete",
            }

        yield {"type": "done", "full_content": full_content.strip()}

        # 6. Save assistant message
        await self.msg_repo.create_message(
            conversation_id=conv.id,
            role="assistant",
            content=full_content.strip(),
            reasoning_content=reasoning_content or None,
            meta={
                "model": settings.VLLM_MODEL if settings.VLLM_ENABLED else settings.OLLAMA_MODEL,
                "provider": settings.DEFAULT_LLM_PROVIDER,
                "route": route,
            },
        )
        await self.session.commit()

    async def process_non_stream(
        self, request: ChatRequest, user_id: int
    ) -> dict:
        """Non-streaming fallback. Returns ChatResponse-like dict."""
        conv = await self.get_or_create_conversation(
            request.thread_id, user_id, title=request.query[:50]
        )

        await self.msg_repo.create_message(
            conversation_id=conv.id, role="user", content=request.query
        )
        await self.session.commit()

        history = await self.msg_repo.list_by_conversation(conv.id)
        route = system1_route(request, history)

        if route == "simple":
            content = f"Echo: {request.query}"
        else:
            content = "[Complex analysis stub — Sistema 2 orchestrator will handle this in Fase 4]"

        await self.msg_repo.create_message(
            conversation_id=conv.id,
            role="assistant",
            content=content,
            meta={
                "model": settings.VLLM_MODEL if settings.VLLM_ENABLED else settings.OLLAMA_MODEL,
                "provider": settings.DEFAULT_LLM_PROVIDER,
                "route": route,
            },
        )
        await self.session.commit()

        return {
            "thread_id": conv.thread_id,
            "content": content,
            "reasoning_content": None,
            "model": settings.DEFAULT_LLM_PROVIDER,
        }
