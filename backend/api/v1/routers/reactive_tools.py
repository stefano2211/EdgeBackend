"""Reactive Tools router — functional CRUD for ReactiveToolConfig and ReactiveMCPSource.

⚠️  Route ordering matters: static routes MUST come before dynamic
`/{param}` segments, otherwise FastAPI matches the parameter route first
and the static route never gets hit.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.v1.schemas.reactive_tool import (
    ReactiveToolConfigCreate,
    ReactiveToolConfigUpdate,
    ReactiveToolConfigOut,
    ReactiveMCPSourceCreate,
    ReactiveMCPSourceUpdate,
    ReactiveMCPSourceOut,
)
from backend.core.deps import get_db, get_current_user
from backend.core.exceptions import NotFoundError
from backend.core.logging import logging
from backend.persistencia.models.user import User
from backend.services.reactive_tool_config_service import ReactiveToolConfigService
from backend.services.reactive_mcp_source_service import ReactiveMCPSourceService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reactive/tools", tags=["reactive-tools"])


# ── Helpers ──

def _raise_not_found(entity: str, entity_id: int) -> None:
    raise HTTPException(status_code=404, detail=f"{entity} {entity_id} not found")


def _raise_forbidden(detail: str = "Not authorized") -> None:
    raise HTTPException(status_code=403, detail=detail)


# ═══════════════════════════════════════════════════════════════════════════
#  STATIC ROUTES — must be registered BEFORE any `/{param}` routes
# ═══════════════════════════════════════════════════════════════════════════

# ── Reactive ToolConfig ──

@router.get("", response_model=list[ReactiveToolConfigOut])
async def list_reactive_tools(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ReactiveToolConfigService(session)
    return await service.repo.list_by_user(current_user.id)


@router.post("", response_model=ReactiveToolConfigOut, status_code=201)
async def create_reactive_tool(
    data: ReactiveToolConfigCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ReactiveToolConfigService(session)
    return await service.create_for_user(data, current_user.id)


# ═══════════════════════════════════════════════════════════════════════════
#  DYNAMIC ROUTES — `/{tool_id}` and sub-resources
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/{tool_id}", response_model=ReactiveToolConfigOut)
async def get_reactive_tool(
    tool_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ReactiveToolConfigService(session)
    try:
        tool = await service.get(tool_id)
    except NotFoundError:
        _raise_not_found("ReactiveToolConfig", tool_id)
    if tool.user_id != current_user.id:
        _raise_forbidden("Not authorized to access this tool")
    return tool


@router.patch("/{tool_id}", response_model=ReactiveToolConfigOut)
async def update_reactive_tool(
    tool_id: int,
    data: ReactiveToolConfigUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ReactiveToolConfigService(session)
    try:
        tool = await service.get(tool_id)
    except NotFoundError:
        _raise_not_found("ReactiveToolConfig", tool_id)
    if tool.user_id != current_user.id:
        _raise_forbidden("Not authorized to modify this tool")
    return await service.update(tool_id, data)


@router.delete("/{tool_id}", status_code=204)
async def delete_reactive_tool(
    tool_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ReactiveToolConfigService(session)
    try:
        tool = await service.get(tool_id)
    except NotFoundError:
        _raise_not_found("ReactiveToolConfig", tool_id)
    if tool.user_id != current_user.id:
        _raise_forbidden("Not authorized to delete this tool")
    await service.delete(tool_id)
    return None


# ── Reactive MCP Sources ──

@router.get("/sources/", response_model=list[ReactiveMCPSourceOut])
async def list_reactive_sources(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ReactiveMCPSourceService(session)
    return await service.repo.list_by_user(current_user.id)


@router.post("/sources/", response_model=ReactiveMCPSourceOut, status_code=201)
async def create_reactive_source(
    data: ReactiveMCPSourceCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ReactiveMCPSourceService(session)
    return await service.create_for_user(data, current_user.id)


@router.patch("/sources/{source_id}", response_model=ReactiveMCPSourceOut)
async def update_reactive_source(
    source_id: int,
    data: ReactiveMCPSourceUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ReactiveMCPSourceService(session)
    try:
        source = await service.get(source_id)
    except NotFoundError:
        _raise_not_found("ReactiveMCPSource", source_id)
    if source.user_id != current_user.id:
        _raise_forbidden("Not authorized to modify this source")
    return await service.update(source_id, data)


@router.delete("/sources/{source_id}", status_code=204)
async def delete_reactive_source(
    source_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ReactiveMCPSourceService(session)
    try:
        source = await service.get(source_id)
    except NotFoundError:
        _raise_not_found("ReactiveMCPSource", source_id)
    if source.user_id != current_user.id:
        _raise_forbidden("Not authorized to delete this source")
    await service.delete(source_id)
    return None
