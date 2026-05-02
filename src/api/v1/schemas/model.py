from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ModelConfigCreate(BaseModel):
    name: str
    description: str | None = None
    base_model_id: str
    tags: list[str] | None = None
    system_prompt: str | None = None
    params: dict | None = None


class ModelConfigUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    base_model_id: str | None = None
    tags: list[str] | None = None
    system_prompt: str | None = None
    params: dict | None = None
    is_enabled: bool | None = None


class ModelConfigOut(BaseModel):
    id: int
    name: str
    description: str | None = None
    base_model_id: str
    tags: list[str] | None = None
    system_prompt: str | None = None
    params: dict | None = None
    knowledge_ids: list[str] | None = None
    tool_ids: list[str] | None = None
    capabilities: list[str] | None = None
    is_enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
