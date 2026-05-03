"""Chat service facade — delegates to ConversationService, MessageService, and ChatOrchestrator.

Maintains backward-compatible API for routers while internal responsibilities are split.
"""

from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.chat import ChatRequest
from src.core.config import settings
from src.persistencia.models.conversation import Conversation
from src.persistencia.models.message import Message
from src.services.conversation_service import ConversationService
from src.services.message_service import MessageService
from src.services.chat_orchestrator import ChatOrchestrator


class ChatService:
    """Facade: conversation management + DeepAgents orchestrator streaming."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.conv_service = ConversationService(session)
        self.msg_service = MessageService(session)
        self.orchestrator = ChatOrchestrator()

    # ── Conversation delegation ──

    async def get_or_create_conversation(
        self, thread_id: str | None, user_id: int, title: str = "New Chat"
    ) -> Conversation:
        return await self.conv_service.get_or_create_conversation(
            thread_id, user_id, title
        )

    async def list_conversations(
        self, user_id: int, include_archived: bool = False
    ) -> list[Conversation]:
        return await self.conv_service.list_conversations(user_id, include_archived)

    async def archive_conversation(
        self, thread_id: str, archive: bool = True
    ) -> Conversation | None:
        return await self.conv_service.archive_conversation(thread_id, archive)

    async def delete_conversation(self, thread_id: str, user_id: int) -> bool:
        return await self.conv_service.delete_conversation(thread_id, user_id)

    # ── Message delegation ──

    async def get_messages(self, thread_id: str, user_id: int) -> list[Message]:
        return await self.msg_service.get_messages(thread_id, user_id)

    # ── Streaming / Non-streaming (orchestrates services) ──

    async def process_stream(
        self, request: ChatRequest, user_id: int
    ) -> AsyncIterator[dict]:
        conv = await self.conv_service.get_or_create_conversation(
            request.thread_id, user_id, title=request.query[:50]
        )
        await self.msg_service.create_user_message(conv.id, request.query)

        messages = await self.msg_service.build_langchain_messages(request, conv.id)
        yield {"type": "meta", "thread_id": conv.thread_id}

        full_content = ""
        reasoning_content = ""
        agents_used: list[str] = []

        async for event in self.orchestrator.stream(request, messages, conv.thread_id):
            if event.get("_internal"):
                full_content = event["full_content"]
                reasoning_content = event.get("reasoning_content") or ""
                agents_used = event.get("agents_used", [])
                continue
            yield event

        await self.msg_service.create_assistant_message(
            conversation_id=conv.id,
            content=full_content.strip(),
            reasoning_content=reasoning_content or None,
            meta={
                "model": "deepagents-orchestrator",
                "provider": settings.DEFAULT_LLM_PROVIDER,
                "route": "complex",
                "agents_used": agents_used,
            },
        )

    async def process_non_stream(self, request: ChatRequest, user_id: int) -> dict:
        conv = await self.conv_service.get_or_create_conversation(
            request.thread_id, user_id, title=request.query[:50]
        )
        await self.msg_service.create_user_message(conv.id, request.query)

        messages = await self.msg_service.build_langchain_messages(request, conv.id)
        result = await self.orchestrator.non_stream(request, messages, conv.thread_id)

        await self.msg_service.create_assistant_message(
            conversation_id=conv.id,
            content=result["content"],
            reasoning_content=result.get("reasoning_content"),
            meta={
                "model": "deepagents-orchestrator",
                "provider": settings.DEFAULT_LLM_PROVIDER,
                "route": "complex",
                "agents_used": result.get("agents_used", []),
            },
        )
        return result
