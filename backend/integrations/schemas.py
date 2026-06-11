"""Pydantic schemas for the integrations API.

Input schemas validate user payloads; output schemas serialise DB models.
All datetime fields are rendered as ISO-8601 strings.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# IntegrationCatalog
# ---------------------------------------------------------------------------

class IntegrationCatalogOut(BaseModel):
    id: int
    slug: str
    name: str
    description: str | None = None
    icon_url: str | None = None
    category: str | None = None
    source_type: str
    auth_type: str
    auth_env_var_mapping: dict
    auth_setup_guide_markdown: str | None = None
    command: str | None = None
    args: list | None = None
    env_prefix: str | None = None
    is_enabled: bool
    is_official_verified: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# IntegrationInstance
# ---------------------------------------------------------------------------

class IntegrationInstanceCreate(BaseModel):
    catalog_slug: str = Field(..., max_length=50)
    instance_name: str = Field(..., max_length=100)
    available_in_chat: bool = True
    available_in_reactive: bool = False


class IntegrationInstanceUpdate(BaseModel):
    instance_name: str | None = Field(None, max_length=100)
    is_enabled: bool | None = None
    available_in_chat: bool | None = None
    available_in_reactive: bool | None = None


class IntegrationInstanceOut(BaseModel):
    id: int
    user_id: int
    catalog_id: int
    instance_name: str
    is_enabled: bool
    process_pid: int | None = None
    process_status: str | None = None
    last_used_at: datetime | None = None
    available_in_chat: bool
    available_in_reactive: bool
    mcp_source_id: int | None = None
    reactive_mcp_source_id: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IntegrationInstanceDetailOut(IntegrationInstanceOut):
    """Includes nested catalog info."""

    catalog: IntegrationCatalogOut | None = None


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------

class CredentialsSubmit(BaseModel):
    """Raw credentials from user. Keys must match catalog.auth_env_var_mapping values."""

    credentials: dict[str, str] = Field(..., description="Key-value map of raw secrets")


# ---------------------------------------------------------------------------
# Setup guide
# ---------------------------------------------------------------------------

class SetupGuideOut(BaseModel):
    catalog_name: str
    setup_guide_markdown: str
    required_fields: list[str] = Field(default_factory=list)
    auth_type: str
