from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ReactiveKnowledgeBaseCreate(BaseModel):
    name: str
    description: str | None = None


class ReactiveKnowledgeBaseUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_enabled: bool | None = None


class ReactiveKnowledgeBaseOut(BaseModel):
    id: int
    user_id: int
    name: str
    description: str | None = None
    is_enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReactiveKnowledgeDocumentOut(BaseModel):
    id: int
    file_id: str
    filename: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReactiveKnowledgeBaseDetailOut(ReactiveKnowledgeBaseOut):
    documents: list[ReactiveKnowledgeDocumentOut]
