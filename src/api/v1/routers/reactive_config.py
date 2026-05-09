"""Reactive configuration endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.reactive_config import (
    ReactiveToolListResponse,
    ReactiveToolToggleRequest,
    ReactiveToolOut,
    ReactiveKbListResponse,
    ReactiveKbToggleRequest,
    ReactiveKbOut,
)
from src.core.deps import get_db, get_current_user
from src.persistencia.models.user import User
from src.services.reactive_config_service import ReactiveConfigService

router = APIRouter(prefix="/reactive", tags=["reactive-config"])


@router.get("/tools", response_model=ReactiveToolListResponse)
async def list_reactive_tools(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ReactiveConfigService(session)
    items = await service.list_tools(current_user.id)
    return ReactiveToolListResponse(items=[ReactiveToolOut(**i) for i in items])


@router.put("/tools/{tool_id}")
async def toggle_reactive_tool(
    tool_id: int,
    payload: ReactiveToolToggleRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ReactiveConfigService(session)
    await service.toggle_tool(current_user.id, tool_id, payload.is_enabled)
    return {"status": "ok"}


@router.get("/knowledge", response_model=ReactiveKbListResponse)
async def list_reactive_knowledge(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ReactiveConfigService(session)
    items = await service.list_knowledge_bases(current_user.id)
    return ReactiveKbListResponse(items=[ReactiveKbOut(**i) for i in items])


@router.put("/knowledge/{kb_id}")
async def toggle_reactive_knowledge(
    kb_id: int,
    payload: ReactiveKbToggleRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    service = ReactiveConfigService(session)
    await service.toggle_knowledge_base(current_user.id, kb_id, payload.is_enabled)
    return {"status": "ok"}
