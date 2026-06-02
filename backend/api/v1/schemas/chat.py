from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1)
    thread_id: str | None = None
    knowledge_base_id: str | None = None
    mcp_source_id: str | None = None
    db_connection_ids: list[str] | None = None
    model_id: str | None = None
    params: dict | None = None
    use_generalist: bool = False


class ChatResponse(BaseModel):
    thread_id: str
    content: str
    reasoning_content: str | None = None
    model: str | None = None


class ChatStreamEvent(BaseModel):
    """Base for SSE events. Each event is serialized and prefixed with data: """
    type: str  # token | reasoning | meta | subagent | screenshot | done | error


class ChatStreamMeta(ChatStreamEvent):
    thread_id: str


class ChatStreamToken(ChatStreamEvent):
    content: str


class ChatStreamDone(ChatStreamEvent):
    full_content: str


class ChatStreamError(ChatStreamEvent):
    detail: str



