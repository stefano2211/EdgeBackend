from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ConversationCreate(BaseModel):
    title: str = "New Chat"


class ConversationOut(BaseModel):
    id: int
    thread_id: str
    title: str
    is_archived: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessageItem(BaseModel):
    role: str
    content: str
    reasoning_content: str | None = None


class MessageOut(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str
    reasoning_content: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
