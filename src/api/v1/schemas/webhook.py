"""Webhook API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class WebhookSourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    description: str | None = Field(None, max_length=500)
    is_enabled: bool = True
    mapping_config: dict | None = None
    rate_limit_rpm: int = Field(60, ge=1, le=10000)
    domain: str | None = Field(None, max_length=50, description="Optional domain override. If not set, auto-detected from first event payload.")


class WebhookSourceUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    is_enabled: bool | None = None
    mapping_config: dict | None = None
    rate_limit_rpm: int | None = Field(None, ge=1, le=10000)
    domain: str | None = Field(None, max_length=50, description="Set to auto-learn from first event, or provide explicit domain.")


class WebhookSourceOut(BaseModel):
    id: int
    user_id: int
    name: str
    slug: str
    description: str | None
    is_enabled: bool
    mapping_config: dict | None
    auto_discovered: bool
    domain: str | None
    rate_limit_rpm: int
    last_payload_preview: dict | None
    last_received_at: datetime | None
    total_received: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WebhookTestPayload(BaseModel):
    payload: dict[str, Any]


class WebhookTestResult(BaseModel):
    mapping_used: dict | None
    auto_discovered: bool
    extracted_fields: dict[str, Any]
    body_preview: dict[str, Any]
    would_create_event: bool = True
