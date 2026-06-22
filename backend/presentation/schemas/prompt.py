from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PromptCreate(BaseModel):
    title: str
    description: str | None = None
    query: str | None = None
    icon: str | None = None
    system_prompt: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None


class PromptUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    query: str | None = None
    icon: str | None = None
    system_prompt: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    is_enabled: bool | None = None


class PromptOut(BaseModel):
    id: int
    title: str
    description: str | None = None
    query: str | None = None
    icon: str | None = None
    is_enabled: bool
    system_prompt: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
