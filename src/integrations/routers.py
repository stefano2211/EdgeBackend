"""Integrations router — exposes the full third-party MCP lifecycle.

Endpoints:
  /integrations/catalog          → browse available integrations
  /integrations/instances        → manage user instances
  /integrations/instances/{id}/setup-guide   → setup instructions
  /integrations/instances/{id}/credentials   → submit secrets + launch container
  /integrations/instances/{id}/sync          → discover & register tools
  /integrations/instances/{id}/start|stop    → container lifecycle
  /integrations/instances/{id}/status        → runtime status
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import get_current_user, get_db
from src.integrations.catalog_service import CatalogService
from src.integrations.integration_service import IntegrationService
from src.integrations.schemas import (
    CredentialsSubmit,
    IntegrationCatalogOut,
    IntegrationInstanceCreate,
    IntegrationInstanceOut,
    IntegrationInstanceUpdate,
    IntegrationInstanceDetailOut,
    SetupGuideOut,
    SyncResult,
)
from src.persistencia.models.user import User

router = APIRouter(prefix="/integrations", tags=["integrations"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _service(session: AsyncSession) -> IntegrationService:
    return IntegrationService(session)


def _catalog_service(session: AsyncSession) -> CatalogService:
    return CatalogService(session)


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

@router.get("/catalog", response_model=list[IntegrationCatalogOut])
async def list_catalog(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """List all enabled integrations available for setup."""
    service = _catalog_service(session)
    items = await service.list_catalog(enabled_only=True)
    return items


@router.get("/catalog/{slug}", response_model=IntegrationCatalogOut)
async def get_catalog_item(
    slug: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Get details of a single catalog entry."""
    service = _catalog_service(session)
    catalog = await service.get_by_slug(slug)
    if not catalog:
        raise HTTPException(status_code=404, detail=f"Catalog '{slug}' not found")
    return catalog


# ---------------------------------------------------------------------------
# Instances
# ---------------------------------------------------------------------------

@router.post("/instances", response_model=IntegrationInstanceOut, status_code=201)
async def create_instance(
    data: IntegrationInstanceCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Create a new integration instance (container NOT started yet)."""
    service = _service(session)
    try:
        instance = await service.create_instance(current_user.id, data)
        return instance
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/instances", response_model=list[IntegrationInstanceOut])
async def list_instances(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """List all integration instances owned by the current user."""
    service = _service(session)
    return await service.list_instances(current_user.id)


@router.get("/instances/{instance_id}", response_model=IntegrationInstanceDetailOut)
async def get_instance(
    instance_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Get detailed view of a single instance including nested catalog."""
    service = _service(session)
    try:
        instance = await service.get_instance(instance_id, current_user.id)
        return instance
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.patch("/instances/{instance_id}", response_model=IntegrationInstanceOut)
async def update_instance(
    instance_id: int,
    data: IntegrationInstanceUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Update instance metadata (name, availability flags)."""
    service = _service(session)
    try:
        return await service.update_instance(instance_id, current_user.id, data)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/instances/{instance_id}", status_code=204)
async def delete_instance(
    instance_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Delete instance, container, credentials, and registered tools permanently."""
    service = _service(session)
    try:
        await service.delete_instance(instance_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return None


# ---------------------------------------------------------------------------
# Setup guide
# ---------------------------------------------------------------------------

@router.get("/instances/{instance_id}/setup-guide", response_model=SetupGuideOut)
async def get_setup_guide(
    instance_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Return setup instructions and required credential fields."""
    service = _service(session)
    try:
        guide = await service.get_setup_guide(instance_id, current_user.id)
        return SetupGuideOut(**guide)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------

@router.post("/instances/{instance_id}/credentials", response_model=IntegrationInstanceOut)
async def submit_credentials(
    instance_id: int,
    data: CredentialsSubmit,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Submit raw credentials, encrypt them, and launch the MCP container."""
    service = _service(session)
    try:
        return await service.submit_credentials(instance_id, current_user.id, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


# ---------------------------------------------------------------------------
# Sync tools
# ---------------------------------------------------------------------------

@router.post("/instances/{instance_id}/sync", response_model=SyncResult)
async def sync_instance_tools(
    instance_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Discover tools from the running MCP container and register them in DB."""
    service = _service(session)
    try:
        return await service.sync_tools(instance_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


# ---------------------------------------------------------------------------
# Container lifecycle
# ---------------------------------------------------------------------------

@router.post("/instances/{instance_id}/start", response_model=IntegrationInstanceOut)
async def start_instance(
    instance_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Start (or restart) the Docker container for this instance."""
    service = _service(session)
    try:
        return await service.start_instance(instance_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/instances/{instance_id}/stop", response_model=IntegrationInstanceOut)
async def stop_instance(
    instance_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Stop the Docker container (preserves data in DB)."""
    service = _service(session)
    try:
        return await service.stop_instance(instance_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/instances/{instance_id}/status")
async def get_instance_status(
    instance_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get container runtime status and registered tools."""
    service = _service(session)
    try:
        return await service.get_status(instance_id, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
