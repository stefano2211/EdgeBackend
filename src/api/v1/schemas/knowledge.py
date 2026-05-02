from datetime import datetime

from pydantic import BaseModel, ConfigDict


class KnowledgeBaseCreate(BaseModel):
    name: str
    description: str | None = None
    context_mode: str = "both"


class KnowledgeBaseUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class KnowledgeBaseOut(BaseModel):
    id: int
    user_id: int
    name: str
    description: str | None = None
    context_mode: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KnowledgeDocumentOut(BaseModel):
    id: int
    file_id: str
    filename: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class KnowledgeBaseDetailOut(KnowledgeBaseOut):
    documents: list[KnowledgeDocumentOut]
