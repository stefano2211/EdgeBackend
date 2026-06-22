from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    id: int
    knowledge_base_id: int
    file_id: str
    filename: str
    content_type: str | None = None
    status: str
    qdrant_collection: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    items: list[DocumentOut]
    total: int
