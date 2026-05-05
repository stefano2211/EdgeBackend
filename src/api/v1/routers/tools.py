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
)
from src.core.deps import get_db, get_current_user
from src.persistencia.models.user import User
from src.services.tool_config_service import ToolConfigService
from src.services.mcp_source_service import MCPSourceService

router = APIRouter(prefix="/tools", tags=["tools"])


# ── ToolConfig ──

@router.get("", response_model=list[ToolConfigOut])
async def list_tools(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ToolConfigService(session)
    return await service.list_tools()


@router.get("/{tool_id}", response_model=ToolConfigOut)
async def get_tool(
    tool_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ToolConfigService(session)
    return await service.get_tool(tool_id)


@router.post("", response_model=ToolConfigOut, status_code=201)
async def create_tool(
    data: ToolConfigCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ToolConfigService(session)
    return await service.create_tool(data)


@router.patch("/{tool_id}", response_model=ToolConfigOut)
async def update_tool(
    tool_id: int,
    data: ToolConfigUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ToolConfigService(session)
    return await service.update_tool(tool_id, data)


@router.delete("/{tool_id}", status_code=204)
async def delete_tool(
    tool_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ToolConfigService(session)
    await service.delete_tool(tool_id)
    return None


# ── MCP Sources ──

@router.get("/sources/", response_model=list[MCPSourceOut])
async def list_sources(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = MCPSourceService(session)
    return await service.list_sources()


@router.post("/sources/", response_model=MCPSourceOut, status_code=201)
async def create_source(
    data: MCPSourceCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = MCPSourceService(session)
    return await service.create_source(data)


@router.patch("/sources/{source_id}", response_model=MCPSourceOut)
async def update_source(
    source_id: int,
    data: MCPSourceUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = MCPSourceService(session)
    return await service.update_source(source_id, data)


@router.delete("/sources/{source_id}", status_code=204)
async def delete_source(
    source_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = MCPSourceService(session)
    await service.delete_source(source_id)
    return None


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
        return await service.discover_tools(url, is_stdio=is_stdio, is_resource=is_resource, method=method)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


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
    source = await service.get_source(source_id)
    mcp_service = MCPService()
    try:
        return await mcp_service.discover_tools(
            source.url, is_stdio=(source.type == "stdio"), method=method
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


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
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
