"""Tools router — functional CRUD for ToolConfig and MCPSource."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.tool import ToolConfigCreate, ToolConfigOut, MCPSourceCreate, MCPSourceOut
from src.core.deps import get_db, get_current_user_id
from src.services.tool_service import ToolService

router = APIRouter(prefix="/tools", tags=["tools"])


# ── ToolConfig ──

@router.get("", response_model=list[ToolConfigOut])
async def list_tools(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = ToolService(session)
    tools = await service.list_tools()
    return tools


@router.get("/{tool_id}", response_model=ToolConfigOut)
async def get_tool(
    tool_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = ToolService(session)
    return await service.get_tool(tool_id)


@router.post("", response_model=ToolConfigOut, status_code=201)
async def create_tool(
    data: ToolConfigCreate,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = ToolService(session)
    return await service.create_tool(data)


@router.put("/{tool_id}", response_model=ToolConfigOut)
async def update_tool(
    tool_id: int,
    data: ToolConfigCreate,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = ToolService(session)
    return await service.update_tool(tool_id, data)


@router.delete("/{tool_id}", status_code=204)
async def delete_tool(
    tool_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = ToolService(session)
    await service.delete_tool(tool_id)
    return None


# ── MCP Sources ──

@router.get("/sources/", response_model=list[MCPSourceOut])
async def list_sources(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = ToolService(session)
    sources = await service.list_sources()
    return sources


@router.post("/sources/", response_model=MCPSourceOut, status_code=201)
async def create_source(
    data: MCPSourceCreate,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = ToolService(session)
    return await service.create_source(data)


@router.put("/sources/{source_id}", response_model=MCPSourceOut)
async def update_source(
    source_id: int,
    data: MCPSourceCreate,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = ToolService(session)
    return await service.update_source(source_id, data)


@router.delete("/sources/{source_id}", status_code=204)
async def delete_source(
    source_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    service = ToolService(session)
    await service.delete_source(source_id)
    return None


# ── Discovery (stubs) ──

@router.get("/mcp/discover")
async def discover_tools(
    url: str = Query(...),
    is_stdio: bool = Query(False),
    is_resource: bool = Query(False),
    method: str = Query("GET"),
    user_id: int = Depends(get_current_user_id),
):
    """Stub: discover available tools from an MCP endpoint."""
    return [
        {
            "name": "get_items",
            "description": f"Retrieve items from {url}",
            "inputSchema": {"type": "object", "properties": {}},
        }
    ]


@router.get("/sources/{source_id}/discover")
async def discover_source_tools(
    source_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    """Stub: discover tools from a registered MCP source."""
    service = ToolService(session)
    source = await service.get_source(source_id)
    return [
        {
            "name": f"tool_from_{source.name}",
            "description": f"Auto-discovered tool from {source.url}",
            "inputSchema": {"type": "object", "properties": {}},
        }
    ]
