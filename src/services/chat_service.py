"""Chat service: conversation management + LLM streaming responses."""

import asyncio
import json
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.chat import ChatRequest
from src.core.config import settings
from src.persistencia.models.conversation import Conversation
from src.persistencia.models.message import Message
from src.persistencia.repositories.conversation_repository import ConversationRepository
from src.persistencia.repositories.message_repository import MessageRepository
from src.ia.system1 import system1_route
from src.ia.llm_client import get_llm_client
from src.ia.rag_tool import rag_retrieve
from src.ia.agent_orchestrator import AgentOrchestrator


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
        """Build OpenAI-compatible message list: system + history + user query."""
        messages: list[dict[str, str]] = []

        # System prompt
        system_prompt = "You are a helpful assistant."
        if request.model_id:
            # Try to load custom system prompt from ModelConfig (optional)
            pass
        messages.append({"role": "system", "content": system_prompt})

        # History (last 10 messages)
        history = await self.msg_repo.list_by_conversation(conversation_id)
        for msg in history[-10:]:
            if msg.role in ("user", "assistant"):
                messages.append({"role": msg.role, "content": msg.content})

        # Current query (with RAG context if applicable)
        query = request.query
        if request.knowledge_base_id:
            context = await rag_retrieve(
                request.knowledge_base_id,
                request.query,
                top_k=5,
            )
            if context:
                query = (
                    f"{context}\n\n"
                    f"Answer the question using ONLY the sources above. "
                    f"If no relevant source is found, say you do not know."
                )

        messages.append({"role": "user", "content": query})
        return messages

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

        # Try to use real LLM; fallback to mock if not available
        try:
            llm = get_llm_client()
        except RuntimeError:
            llm = None

        if llm is None:
            # Fallback: mock response when no LLM is available
            response_text = f"[LLM unavailable — Echo: {request.query}]"
            for word in response_text.split():
                token = word + " "
                full_content += token
                yield {"type": "token", "content": token}
                await asyncio.sleep(0.02)
        else:
            messages = await self._build_messages(request, conv.id)

            if route == "complex":
                # System 2: Orchestrator handles multi-step reasoning
                orchestrator = AgentOrchestrator()
                plan = await orchestrator.analyze(
                    query=request.query,
                    history=history,
                    available_knowledge=[request.knowledge_base_id] if request.knowledge_base_id else None,
                )

                # Emit subagent events for each step
                for subagent in plan.get("subagents", []):
                    yield {
                        "type": "subagent",
                        "name": subagent,
                        "status": "running",
                        "input": {"query": request.query},
                    }

                async def _stream_cb(token: str) -> None:
                    # Callback for orchestrator streaming
                    nonlocal full_content
                    full_content += token
                    # Note: cannot yield from callback; tokens accumulate in full_content

                full_content = await orchestrator.execute_plan(
                    plan=plan,
                    messages=messages,
                    llm_stream_callback=_stream_cb,
                )

                # Stream accumulated tokens (orchestrator runs non-stream for now)
                # TODO: yield tokens as they arrive from execute_plan streaming
                for word in full_content.split():
                    token = word + " "
                    yield {"type": "token", "content": token}

                for subagent in plan.get("subagents", []):
                    yield {
                        "type": "subagent",
                        "name": subagent,
                        "status": "complete",
                    }
            else:
                # System 1: Direct LLM call
                params = request.params or {}
                stream = await llm.chat_completion(
                    messages=messages,
                    temperature=params.get("temperature", 0.7),
                    max_tokens=params.get("max_tokens"),
                    stream=True,
                )

                async for chunk in stream:
                    choices = chunk.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})

                    if "content" in delta and delta["content"]:
                        token = delta["content"]
                        full_content += token
                        yield {"type": "token", "content": token}

                    if "reasoning_content" in delta and delta["reasoning_content"]:
                        reasoning_content += delta["reasoning_content"]
                        yield {"type": "reasoning", "content": delta["reasoning_content"]}

        yield {"type": "done", "full_content": full_content.strip()}

        # 6. Save assistant message
        await self.msg_repo.create_message(
            conversation_id=conv.id,
            role="assistant",
            content=full_content.strip(),
            reasoning_content=reasoning_content or None,
            meta={
                "model": llm.model if llm else "mock",
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

        # Try to use real LLM; fallback to mock
        try:
            llm = get_llm_client()
        except RuntimeError:
            llm = None

        if llm is None:
            content = f"[LLM unavailable — Echo: {request.query}]"
            reasoning = None
        else:
            messages = await self._build_messages(request, conv.id)

            if route == "complex":
                # System 2: Orchestrator
                orchestrator = AgentOrchestrator()
                plan = await orchestrator.analyze(
                    query=request.query,
                    history=history,
                    available_knowledge=[request.knowledge_base_id] if request.knowledge_base_id else None,
                )
                content = await orchestrator.execute_plan(
                    plan=plan,
                    messages=messages,
                    llm_stream_callback=None,
                )
                reasoning = None
            else:
                # System 1: Direct LLM
                params = request.params or {}
                resp = await llm.chat_completion(
                    messages=messages,
                    temperature=params.get("temperature", 0.7),
                    max_tokens=params.get("max_tokens"),
                    stream=False,
                )
                content = resp["choices"][0]["message"]["content"]
                reasoning = resp["choices"][0]["message"].get("reasoning_content")

        await self.msg_repo.create_message(
            conversation_id=conv.id,
            role="assistant",
            content=content,
            reasoning_content=reasoning,
            meta={
                "model": llm.model if llm else "mock",
                "provider": settings.DEFAULT_LLM_PROVIDER,
                "route": route,
            },
        )
        await self.session.commit()

        return {
            "thread_id": conv.thread_id,
            "content": content,
            "reasoning_content": reasoning,
            "model": llm.model if llm else "mock",
        }
