"""Message domain service — CRUD for messages within conversations."""

from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.v1.schemas.chat import ChatRequest
from backend.persistencia.models.message import Message
from backend.persistencia.repositories.conversation_repository import ConversationRepository
from backend.persistencia.repositories.message_repository import MessageRepository


class MessageService:
    """Handles message lifecycle: creation, retrieval, LangChain history building."""

    def __init__(
        self,
        session: AsyncSession,
        msg_repo: MessageRepository | None = None,
        conv_repo: ConversationRepository | None = None,
    ) -> None:
        self.session = session
        self.msg_repo = msg_repo or MessageRepository(session)
        self.conv_repo = conv_repo or ConversationRepository(session)

    async def get_messages(self, thread_id: str, user_id: int) -> list[Message]:
        conv = await self.conv_repo.get_by_thread_id(thread_id)
        if not conv or conv.user_id != user_id:
            return []
        return await self.msg_repo.list_by_conversation(conv.id)

    async def create_user_message(self, conversation_id: int, query: str) -> Message:
        msg = await self.msg_repo.create_message(
            conversation_id=conversation_id, role="user", content=query
        )
        await self.session.commit()
        return msg

    async def create_assistant_message(
        self,
        conversation_id: int,
        content: str,
        reasoning_content: str | None = None,
        meta: dict | None = None,
    ) -> Message:
        msg = await self.msg_repo.create_message(
            conversation_id=conversation_id,
            role="assistant",
            content=content,
            reasoning_content=reasoning_content,
            meta=meta,
        )
        await self.session.commit()
        return msg

    async def build_langchain_messages(
        self,
        request: ChatRequest,
        conversation_id: int,
        system_prompt: str = "You are a helpful assistant.",
        history_limit: int = 20,
    ) -> list[dict[str, str]]:
        """Build LangChain-compatible message list: system + history + user query."""
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt}
        ]
        history = await self.msg_repo.list_by_conversation(conversation_id)
        for msg in history[-history_limit:]:
            if msg.role in ("user", "assistant"):
                messages.append({"role": msg.role, "content": msg.content})
        
        if not history or history[-1].role != "user" or history[-1].content != request.query:
            messages.append({"role": "user", "content": request.query})
        return messages
