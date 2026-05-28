"""Reactive configuration API schemas."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ReactiveToolOut(BaseModel):
    id: int
    name: str
    description: str | None = None
    source_name: str | None = None
    is_enabled: bool

    model_config = ConfigDict(from_attributes=True)


class ReactiveToolListResponse(BaseModel):
    items: list[ReactiveToolOut]


class ReactiveToolToggleRequest(BaseModel):
    is_enabled: bool


class ReactiveKbOut(BaseModel):
    id: int
    name: str
    description: str | None = None
    document_count: int
    is_enabled: bool

    model_config = ConfigDict(from_attributes=True)


class ReactiveKbListResponse(BaseModel):
    items: list[ReactiveKbOut]


class ReactiveKbToggleRequest(BaseModel):
    is_enabled: bool
