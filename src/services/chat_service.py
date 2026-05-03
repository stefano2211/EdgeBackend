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

    def __init__(
        self,
        session: AsyncSession,
        *,
        conv_service: ConversationService | None = None,
        msg_service: MessageService | None = None,
        orchestrator: ChatOrchestrator | None = None,
    ) -> None:
        self.session = session
        self.conv_service = conv_service or ConversationService(session)
        self.msg_service = msg_service or MessageService(session)
        self.orchestrator = orchestrator or ChatOrchestrator()

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

    # ── Internal helpers ──

    async def _prepare_chat(
        self, request: ChatRequest, user_id: int
    ) -> tuple[Conversation, list[dict[str, str]]]:
        """Create/fetch conversation, persist user message, build LangChain messages."""
        conv = await self.conv_service.get_or_create_conversation(
            request.thread_id, user_id, title=request.query[:50]
        )
        await self.msg_service.create_user_message(conv.id, request.query)
        messages = await self.msg_service.build_langchain_messages(request, conv.id)
        return conv, messages

    async def _persist_assistant_message(
        self,
        conv_id: int,
        content: str,
        reasoning_content: str | None,
        agents_used: list[str],
    ) -> None:
        """Persist the assistant response and metadata."""
        await self.msg_service.create_assistant_message(
            conversation_id=conv_id,
            content=content,
            reasoning_content=reasoning_content,
            meta={
                "model": "deepagents-orchestrator",
                "provider": settings.DEFAULT_LLM_PROVIDER,
                "route": "complex",
                "agents_used": agents_used,
            },
        )

    # ── Streaming / Non-streaming ──

    async def process_stream(
        self, request: ChatRequest, user_id: int
    ) -> AsyncIterator[dict]:
        conv, messages = await self._prepare_chat(request, user_id)
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

        await self._persist_assistant_message(
            conv.id, full_content.strip(), reasoning_content or None, agents_used
        )

    async def process_non_stream(self, request: ChatRequest, user_id: int) -> dict:
        conv, messages = await self._prepare_chat(request, user_id)
        result = await self.orchestrator.non_stream(request, messages, conv.thread_id)

        await self._persist_assistant_message(
            conv.id,
            result["content"],
            result.get("reasoning_content"),
            result.get("agents_used", []),
        )
        return result
