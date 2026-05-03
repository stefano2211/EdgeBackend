from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MCPSourceCreate(BaseModel):
    name: str
    description: str | None = None
    url: str
    type: str = "rest"


class MCPSourceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    url: str | None = None
    type: str | None = None
    is_enabled: bool | None = None
    context_mode: str | None = None


class MCPSourceOut(BaseModel):
    id: int
    name: str
    description: str | None = None
    url: str
    type: str
    is_enabled: bool
    context_mode: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ToolConfigUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_enabled: bool | None = None
    context_mode: str | None = None
    config: dict | None = None
    parameter_schema: dict | None = None
    source_id: int | None = None


class ToolConfigCreate(BaseModel):
    name: str
    description: str | None = None
    is_enabled: bool = True
    context_mode: str = "both"
    config: dict | None = None
    parameter_schema: dict | None = None
    source_id: int | None = None


class ToolConfigOut(BaseModel):
    id: int
    name: str
    description: str | None = None
    is_enabled: bool
    context_mode: str
    config: dict | None = None
    parameter_schema: dict | None = None
    source_id: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
