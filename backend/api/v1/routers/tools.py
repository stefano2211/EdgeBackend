"""Tools router — emulates ToolConfig and MCPSource endpoints dynamically."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from backend.api.v1.schemas.tool import (
    ToolConfigOut,
    MCPSourceOut,
    MCPRegistryItem,
)
from backend.core.deps import get_db, get_current_user
from backend.persistencia.models.user import User
from backend.integrations.models import IntegrationInstance
from backend.integrations.integration_service import IntegrationService

router = APIRouter(prefix="/tools", tags=["tools"])


# ═══════════════════════════════════════════════════════════════════════════
#  STATIC ROUTES
# ═══════════════════════════════════════════════════════════════════════════

@router.get("", response_model=list[ToolConfigOut])
async def list_tools(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    stmt = select(IntegrationInstance).where(
        IntegrationInstance.user_id == current_user.id,
        IntegrationInstance.is_enabled.is_(True),
        IntegrationInstance.available_in_chat.is_(True),
    )
    result = await session.execute(stmt)
    instances = result.scalars().all()

    integration_service = IntegrationService(session)
    tools_out = []
    for instance in instances:
        discovered = await integration_service._discover_tools(instance)
        for t in discovered:
            tool_name = t["name"]
            tool_id = abs(hash(f"{instance.id}:{tool_name}")) % 1000000 + 1
            tools_out.append(
                ToolConfigOut(
                    id=tool_id,
                    name=tool_name,
                    description=t.get("description") or "",
                    is_enabled=True,
                    config=t.get("config") or {"transport": "stdio"},
                    parameter_schema=t.get("parameter_schema") or {},
                    source_id=instance.id,
                    created_at=instance.created_at,
                    updated_at=instance.updated_at,
                )
            )
    return tools_out


@router.get("/registry", response_model=list[MCPRegistryItem])
async def list_registry(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Return all active MCP tools across chat and reactive contexts."""
    from backend.services.tool_registry_service import ToolRegistryService

    service = ToolRegistryService(session)
    return await service.list_registry(user_id=current_user.id)


# ═══════════════════════════════════════════════════════════════════════════
#  DYNAMIC ROUTES
# ═══════════════════════════════════════════════════════════════════════════

@router.get("/{tool_id}", response_model=ToolConfigOut)
async def get_tool(
    tool_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    tools = await list_tools(current_user=current_user, session=session)
    for t in tools:
        if t.id == tool_id:
            return t
    raise HTTPException(status_code=404, detail=f"ToolConfig {tool_id} not found")


@router.patch("/{tool_id}", response_model=dict)
async def update_tool(
    tool_id: int,
    current_user: User = Depends(get_current_user),
):
    return {"status": "ok", "message": "Managed dynamically via Integrations page"}


@router.delete("/{tool_id}", status_code=204)
async def delete_tool(
    tool_id: int,
    current_user: User = Depends(get_current_user),
):
    return None


# ── MCP Sources ──

@router.get("/sources/", response_model=list[MCPSourceOut])
async def list_sources(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    stmt = select(IntegrationInstance).where(
        IntegrationInstance.user_id == current_user.id,
        IntegrationInstance.is_enabled.is_(True),
        IntegrationInstance.available_in_chat.is_(True),
    )
    result = await session.execute(stmt)
    instances = result.scalars().all()

    sources_out = []
    for inst in instances:
        sources_out.append(
            MCPSourceOut(
                id=inst.id,
                name=inst.instance_name,
                description=(inst.catalog.description if inst.catalog else None) or f"Dynamic integration for {inst.instance_name}",
                url="stdio",
                type="stdio",
                is_enabled=inst.is_enabled,
                context_mode="chat",
                created_at=inst.created_at,
                updated_at=inst.updated_at,
            )
        )
    return sources_out


@router.post("/sources/", response_model=dict, status_code=201)
async def create_source(
    current_user: User = Depends(get_current_user),
):
    return {"status": "ok", "message": "Managed dynamically via Integrations page"}


@router.patch("/sources/{source_id}", response_model=dict)
async def update_source(
    source_id: int,
    current_user: User = Depends(get_current_user),
):
    return {"status": "ok", "message": "Managed dynamically via Integrations page"}


@router.delete("/sources/{source_id}", status_code=204)
async def delete_source(
    source_id: int,
    current_user: User = Depends(get_current_user),
):
    return None
