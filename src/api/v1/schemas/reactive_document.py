from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ReactiveDocumentOut(BaseModel):
    id: int
    reactive_knowledge_base_id: int
    file_id: str
    filename: str
    content_type: str | None = None
    status: str
    qdrant_collection: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReactiveDocumentListResponse(BaseModel):
    items: list[ReactiveDocumentOut]
    total: int
