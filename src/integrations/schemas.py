"""Pydantic schemas for the integrations API.

Input schemas validate user payloads; output schemas serialise DB models.
All datetime fields are rendered as ISO-8601 strings.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# IntegrationCatalog
# ---------------------------------------------------------------------------

class IntegrationCatalogCreate(BaseModel):
    slug: str = Field(..., max_length=50, pattern=r"^[a-z0-9_-]+$")
    name: str = Field(..., max_length=100)
    description: str | None = None
    icon_url: str | None = None
    category: str | None = None
    source_type: str = Field(..., pattern=r"^(official|custom|rest_bridge)$")
    official_package: str | None = None
    official_command: str | None = None
    official_args: list | None = None
    custom_module_path: str | None = None
    rest_bridge_url_template: str | None = None
    auth_type: str = Field(..., pattern=r"^(token|oauth2|basic|api_key|none)$")
    auth_env_var_mapping: dict = Field(default_factory=dict)
    auth_setup_guide_markdown: str | None = None
    docker_image: str | None = None
    docker_command: list | None = None
    requires_docker: bool = True
    is_enabled: bool = True
    is_official_verified: bool = False


class IntegrationCatalogUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    description: str | None = None
    icon_url: str | None = None
    category: str | None = None
    is_enabled: bool | None = None
    auth_setup_guide_markdown: str | None = None
    docker_image: str | None = None


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
    requires_docker: bool
    is_enabled: bool
    is_official_verified: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IntegrationCatalogDetailOut(IntegrationCatalogOut):
    """Full detail including sensitive setup config."""

    official_package: str | None = None
    official_command: str | None = None
    official_args: list | None = None
    custom_module_path: str | None = None
    rest_bridge_url_template: str | None = None
    docker_image: str | None = None
    docker_command: list | None = None


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
    container_name: str | None = None
    container_status: str | None = None
    container_endpoint: str | None = None
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


class IntegrationCredentialOut(BaseModel):
    id: int
    instance_id: int
    credential_key: str
    expires_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Sync / Status
# ---------------------------------------------------------------------------

class SyncResult(BaseModel):
    tools_discovered: int
    tools_added: int
    mcp_source_id: int | None = None
    reactive_mcp_source_id: int | None = None


class InstanceStatusOut(BaseModel):
    instance: IntegrationInstanceOut
    container: dict[str, Any] | None = None
    tools_registered: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Setup guide
# ---------------------------------------------------------------------------

class SetupGuideOut(BaseModel):
    catalog_name: str
    setup_guide_markdown: str
    required_fields: list[str] = Field(default_factory=list)
    auth_type: str
