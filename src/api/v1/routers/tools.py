"""Tools router — functional CRUD for ToolConfig and MCPSource."""

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


# ── ToolConfig ──

@router.get("", response_model=list[ToolConfigOut])
async def list_tools(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ToolConfigService(session)
    return await service.list()


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


@router.post("", response_model=ToolConfigOut, status_code=201)
async def create_tool(
    data: ToolConfigCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ToolConfigService(session)
    return await service.create(data)


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


# ── Registry (unified view of all MCP tools) ──

@router.get("/registry", response_model=list[MCPRegistryItem])
async def list_registry(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Return all active MCP tools across chat and reactive contexts."""
    from src.services.tool_registry_service import ToolRegistryService

    service = ToolRegistryService(session)
    return await service.list_registry()


# ── Discovery (real MCP Service) ──

@router.get("/mcp/discover")
async def discover_tools(
    url: str = Query(...),
    is_stdio: bool = Query(False),
    is_resource: bool = Query(False),
    method: str = Query("GET"),
    current_user: User = Depends(get_current_user),
):
    """Dynamically discover tools from an MCP server or REST API endpoint."""
    from src.services.mcp_service import MCPService

    service = MCPService()
    try:
        return await service.discover_tools(
            url, is_stdio=is_stdio, is_resource=is_resource, method=method
        )
    except ValueError as exc:
        logger.warning("Discovery validation error: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid discovery parameters.")
    except RuntimeError as exc:
        logger.error("Discovery runtime error: %s", exc)
        raise HTTPException(status_code=502, detail="Discovery failed. Check server logs.")
    except Exception:
        logger.exception("Discovery unexpected error for url=%s", url)
        raise HTTPException(status_code=500, detail="Discovery failed. Check server logs.")


@router.get("/sources/{source_id}/discover")
async def discover_source_tools(
    source_id: int,
    method: str = Query("GET"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Discover tools from a registered MCP source."""
    from src.services.mcp_service import MCPService

    service = MCPSourceService(session)
    try:
        source = await service.get(source_id)
    except NotFoundError:
        _raise_not_found("MCPSource", source_id)

    mcp_service = MCPService()
    try:
        return await mcp_service.discover_tools(
            source.url,
            is_stdio=(source.type == "stdio"),
            method=method,
            is_resource=False,
        )
    except ValueError as exc:
        logger.warning("Discovery validation error for source_id=%s: %s", source_id, exc)
        raise HTTPException(status_code=400, detail="Invalid discovery parameters.")
    except RuntimeError as exc:
        logger.error("Discovery runtime error for source_id=%s: %s", source_id, exc)
        raise HTTPException(status_code=502, detail="Discovery failed. Check server logs.")
    except Exception:
        logger.exception("Discovery unexpected error for source_id=%s", source_id)
        raise HTTPException(status_code=500, detail="Discovery failed. Check server logs.")


@router.post("/sources/{source_id}/sync")
async def sync_source_tools(
    source_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Connect to an MCP source, discover tools, and auto-register them."""
    service = MCPSourceService(session)
    try:
        return await service.sync_source_tools(source_id)
    except NotFoundError:
        _raise_not_found("MCPSource", source_id)
    except ValueError as exc:
        logger.warning("Sync validation error for source_id=%s: %s", source_id, exc)
        raise HTTPException(status_code=400, detail="Invalid sync parameters.")
    except RuntimeError as exc:
        logger.error("Sync runtime error for source_id=%s: %s", source_id, exc)
        raise HTTPException(status_code=502, detail="Sync failed. Check server logs.")
    except Exception:
        logger.exception("Sync unexpected error for source_id=%s", source_id)
        raise HTTPException(status_code=500, detail="Sync failed. Check server logs.")
