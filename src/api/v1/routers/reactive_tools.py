"""Reactive Tools router — functional CRUD for ReactiveToolConfig and ReactiveMCPSource."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.reactive_tool import (
    ReactiveToolConfigCreate,
    ReactiveToolConfigUpdate,
    ReactiveToolConfigOut,
    ReactiveMCPSourceCreate,
    ReactiveMCPSourceUpdate,
    ReactiveMCPSourceOut,
)
from src.core.deps import get_db, get_current_user
from src.core.exceptions import NotFoundError
from src.core.logging import logging
from src.persistencia.models.user import User
from src.services.reactive_tool_config_service import ReactiveToolConfigService
from src.services.reactive_mcp_source_service import ReactiveMCPSourceService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reactive/tools", tags=["reactive-tools"])


# ── Helpers ──

def _raise_not_found(entity: str, entity_id: int) -> None:
    raise HTTPException(status_code=404, detail=f"{entity} {entity_id} not found")


def _raise_forbidden(detail: str = "Not authorized") -> None:
    raise HTTPException(status_code=403, detail=detail)


# ── Reactive ToolConfig ──

@router.get("", response_model=list[ReactiveToolConfigOut])
async def list_reactive_tools(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ReactiveToolConfigService(session)
    return await service.repo.list_by_user(current_user.id)


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


@router.post("", response_model=ReactiveToolConfigOut, status_code=201)
async def create_reactive_tool(
    data: ReactiveToolConfigCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ReactiveToolConfigService(session)
    return await service.create_for_user(data, current_user.id)


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


# ── Discovery ──

@router.get("/mcp/discover")
async def discover_reactive_tools(
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
        return await service.discover_tools(url, is_stdio=is_stdio, is_resource=is_resource, method=method)
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
async def discover_reactive_source_tools(
    source_id: int,
    method: str = Query("GET"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Discover tools from a registered reactive MCP source."""
    from src.services.mcp_service import MCPService

    service = ReactiveMCPSourceService(session)
    try:
        source = await service.get(source_id)
    except NotFoundError:
        _raise_not_found("ReactiveMCPSource", source_id)
    if source.user_id != current_user.id:
        _raise_forbidden("Not authorized to access this source")

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
async def sync_reactive_source_tools(
    source_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Connect to a reactive MCP source, discover tools, and auto-register them."""
    service = ReactiveMCPSourceService(session)
    try:
        source = await service.get(source_id)
    except NotFoundError:
        _raise_not_found("ReactiveMCPSource", source_id)
    if source.user_id != current_user.id:
        _raise_forbidden("Not authorized to sync this source")

    try:
        return await service.sync_source_tools(source_id)
    except ValueError as exc:
        logger.warning("Sync validation error for source_id=%s: %s", source_id, exc)
        raise HTTPException(status_code=400, detail="Invalid sync parameters.")
    except RuntimeError as exc:
        logger.error("Sync runtime error for source_id=%s: %s", source_id, exc)
        raise HTTPException(status_code=502, detail="Sync failed. Check server logs.")
    except Exception:
        logger.exception("Sync unexpected error for source_id=%s", source_id)
        raise HTTPException(status_code=500, detail="Sync failed. Check server logs.")
