"""Tools router — functional CRUD for ToolConfig and MCPSource.

⚠️  Route ordering matters: static routes MUST come before dynamic
`/{param}` segments, otherwise FastAPI matches the parameter route first
and the static route never gets hit (e.g. /registry → tool_id="registry").
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.tool import (
    ToolConfigCreate,
    ToolConfigUpdate,
    ToolConfigOut,
    MCPSourceCreate,
    MCPSourceUpdate,
    MCPSourceOut,
    MCPRegistryItem,
)
from src.core.deps import get_db, get_current_user
from src.core.exceptions import NotFoundError
from src.core.logging import logging
from src.persistencia.models.user import User
from src.services.tool_config_service import ToolConfigService
from src.services.mcp_source_service import MCPSourceService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tools", tags=["tools"])


# ── Helpers ──

def _raise_not_found(entity: str, entity_id: int) -> None:
    raise HTTPException(status_code=404, detail=f"{entity} {entity_id} not found")


# ═══════════════════════════════════════════════════════════════════════════
#  STATIC ROUTES — must be registered BEFORE any `/{param}` routes
# ═══════════════════════════════════════════════════════════════════════════

# ── ToolConfig ──

@router.get("", response_model=list[ToolConfigOut])
async def list_tools(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ToolConfigService(session)
    return await service.list()


@router.post("", response_model=ToolConfigOut, status_code=201)
async def create_tool(
    data: ToolConfigCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ToolConfigService(session)
    return await service.create(data)


# ── Registry (static route must be before /{tool_id}) ──

@router.get("/registry", response_model=list[MCPRegistryItem])
async def list_registry(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Return all active MCP tools across chat and reactive contexts."""
    from src.services.tool_registry_service import ToolRegistryService

    service = ToolRegistryService(session)
    return await service.list_registry()


# ═══════════════════════════════════════════════════════════════════════════
#  DYNAMIC ROUTES — `/{tool_id}` and sub-resources
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/{tool_id}", response_model=ToolConfigOut)
async def get_tool(
    tool_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ToolConfigService(session)
    try:
        return await service.get(tool_id)
    except NotFoundError:
        _raise_not_found("ToolConfig", tool_id)


@router.patch("/{tool_id}", response_model=ToolConfigOut)
async def update_tool(
    tool_id: int,
    data: ToolConfigUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ToolConfigService(session)
    try:
        return await service.update(tool_id, data)
    except NotFoundError:
        _raise_not_found("ToolConfig", tool_id)


@router.delete("/{tool_id}", status_code=204)
async def delete_tool(
    tool_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ToolConfigService(session)
    try:
        await service.delete(tool_id)
    except NotFoundError:
        _raise_not_found("ToolConfig", tool_id)
    return None


# ── MCP Sources ──

@router.get("/sources/", response_model=list[MCPSourceOut])
async def list_sources(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = MCPSourceService(session)
    return await service.list()


@router.post("/sources/", response_model=MCPSourceOut, status_code=201)
async def create_source(
    data: MCPSourceCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = MCPSourceService(session)
    return await service.create(data)


@router.patch("/sources/{source_id}", response_model=MCPSourceOut)
async def update_source(
    source_id: int,
    data: MCPSourceUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = MCPSourceService(session)
    try:
        return await service.update(source_id, data)
    except NotFoundError:
        _raise_not_found("MCPSource", source_id)


@router.delete("/sources/{source_id}", status_code=204)
async def delete_source(
    source_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = MCPSourceService(session)
    try:
        await service.delete(source_id)
    except NotFoundError:
        _raise_not_found("MCPSource", source_id)
    return None
