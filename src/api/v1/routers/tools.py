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
    return await service.list()


@router.get("/{tool_id}", response_model=ToolConfigOut)
async def get_tool(
    tool_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ToolConfigService(session)
    return await service.get(tool_id)


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
    return await service.update(tool_id, data)


@router.delete("/{tool_id}", status_code=204)
async def delete_tool(
    tool_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ToolConfigService(session)
    await service.delete(tool_id)
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
    return await service.update(source_id, data)


@router.delete("/sources/{source_id}", status_code=204)
async def delete_source(
    source_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = MCPSourceService(session)
    await service.delete(source_id)
    return None


# ── Registry (unified view of all MCP tools) ──

@router.get("/registry", response_model=list[MCPRegistryItem])
async def list_registry(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Return all active MCP tools across chat and reactive contexts."""
    from sqlalchemy import select
    from src.persistencia.models.tool_config import ToolConfig, MCPSource
    from src.persistencia.models.reactive_tool_config import ReactiveToolConfig
    from src.persistencia.models.reactive_mcp_source import ReactiveMCPSource
    from src.integrations.models import IntegrationInstance, IntegrationCatalog

    registry: list[dict] = []

    # ── Chat tools (ToolConfig + MCPSource) ──
    chat_stmt = (
        select(ToolConfig, MCPSource)
        .join(MCPSource, ToolConfig.source_id == MCPSource.id)
        .where(ToolConfig.is_enabled == True)
    )
    chat_result = await session.execute(chat_stmt)

    for tool, source in chat_result.all():
        # Determine if this source is tied to an integration instance
        inst_stmt = (
            select(IntegrationInstance, IntegrationCatalog)
            .join(IntegrationCatalog, IntegrationInstance.catalog_id == IntegrationCatalog.id)
            .where(IntegrationInstance.mcp_source_id == source.id)
        )
        inst_result = await session.execute(inst_stmt)
        row = inst_result.first()

        if row:
            instance, catalog = row
            source_type = catalog.source_type
            instance_name = instance.instance_name
            category = catalog.category
        else:
            source_type = "rest_bridge"
            instance_name = None
            category = None

        transport = tool.config.get("transport", source.type) if tool.config else source.type

        registry.append(
            {
                "id": tool.id,
                "name": tool.name,
                "description": tool.description,
                "source_name": source.name,
                "source_type": source_type,
                "context": source.context_mode,
                "transport": transport,
                "is_enabled": tool.is_enabled,
                "category": category,
                "instance_name": instance_name,
                "created_at": tool.created_at,
            }
        )

    # ── Reactive tools (ReactiveToolConfig + ReactiveMCPSource) ──
    reactive_stmt = (
        select(ReactiveToolConfig, ReactiveMCPSource)
        .join(ReactiveMCPSource, ReactiveToolConfig.source_id == ReactiveMCPSource.id)
        .where(ReactiveToolConfig.is_enabled == True)
    )
    reactive_result = await session.execute(reactive_stmt)

    for tool, source in reactive_result.all():
        inst_stmt = (
            select(IntegrationInstance, IntegrationCatalog)
            .join(IntegrationCatalog, IntegrationInstance.catalog_id == IntegrationCatalog.id)
            .where(IntegrationInstance.reactive_mcp_source_id == source.id)
        )
        inst_result = await session.execute(inst_stmt)
        row = inst_result.first()

        if row:
            instance, catalog = row
            source_type = catalog.source_type
            instance_name = instance.instance_name
            category = catalog.category
        else:
            source_type = "rest_bridge"
            instance_name = None
            category = None

        transport = tool.config.get("transport", source.type) if tool.config else source.type

        registry.append(
            {
                "id": tool.id,
                "name": tool.name,
                "description": tool.description,
                "source_name": source.name,
                "source_type": source_type,
                "context": "reactive",
                "transport": transport,
                "is_enabled": tool.is_enabled,
                "category": category,
                "instance_name": instance_name,
                "created_at": tool.created_at,
            }
        )

    return registry


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
    source = await service.get(source_id)
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
