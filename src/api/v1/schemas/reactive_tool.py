from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ReactiveMCPSourceCreate(BaseModel):
    name: str
    description: str | None = None
    url: str
    type: str = "rest"


class ReactiveMCPSourceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    url: str | None = None
    type: str | None = None
    is_enabled: bool | None = None


class ReactiveMCPSourceOut(BaseModel):
    id: int
    user_id: int
    name: str
    description: str | None = None
    url: str
    type: str
    is_enabled: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReactiveToolConfigUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_enabled: bool | None = None
    config: dict | None = None
    parameter_schema: dict | None = None
    source_id: int | None = None


class ReactiveToolConfigCreate(BaseModel):
    name: str
    description: str | None = None
    is_enabled: bool = True
    config: dict | None = None
    parameter_schema: dict | None = None
    source_id: int | None = None


class ReactiveToolConfigOut(BaseModel):
    id: int
    user_id: int
    name: str
    description: str | None = None
    is_enabled: bool
    config: dict | None = None
    parameter_schema: dict | None = None
    source_id: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
