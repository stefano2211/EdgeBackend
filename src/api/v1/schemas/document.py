from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    id: int
    knowledge_base_id: int
    filename: str
    content_type: str | None = None
    status: str
    s3_key: str | None = None
    uploaded_by: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    items: list[DocumentOut]
    total: int
