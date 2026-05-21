"""Domain configuration router — thin controller that delegates to DomainConfigService."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.deps import get_current_user
from src.core.exceptions import ConflictError, NotFoundError
from src.persistencia.models.user import User
from src.services.domain_config_service import DomainConfigService
from src.services.domain_detector import DomainDetector
from src.api.v1.schemas.domain_config import (
    DomainConfigCreate,
    DomainConfigUpdate,
    DomainConfigOut,
    DomainConfigListResponse,
    DomainDetectTestPayload,
    DomainDetectTestResponse,
)

router = APIRouter(prefix="/domains", tags=["Domains"])


async def _get_service(session: AsyncSession = Depends(get_db)) -> DomainConfigService:
    return DomainConfigService(session)


@router.get("", response_model=DomainConfigListResponse)
async def list_domains(
    user: User = Depends(get_current_user),
    service: DomainConfigService = Depends(_get_service),
) -> DomainConfigListResponse:
    """List all domain configurations for the current user."""
    items = await service.list_for_user(user.id)
    return DomainConfigListResponse(items=items)


@router.post("", response_model=DomainConfigOut, status_code=status.HTTP_201_CREATED)
async def create_domain(
    payload: DomainConfigCreate,
    user: User = Depends(get_current_user),
    service: DomainConfigService = Depends(_get_service),
) -> DomainConfigOut:
    """Create a new domain configuration."""
    try:
        domain = await service.create(
            user_id=user.id,
            name=payload.name,
            display_name=payload.display_name,
            detection_rules=payload.detection_rules.model_dump() if payload.detection_rules else None,
            is_default=payload.is_default,
        )
    except ConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return DomainConfigOut.model_validate(domain)


@router.get("/{domain_id}", response_model=DomainConfigOut)
async def get_domain(
    domain_id: int,
    user: User = Depends(get_current_user),
    service: DomainConfigService = Depends(_get_service),
) -> DomainConfigOut:
    """Get a single domain configuration."""
    try:
        domain = await service.get_for_user(domain_id, user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return DomainConfigOut.model_validate(domain)


@router.put("/{domain_id}", response_model=DomainConfigOut)
async def update_domain(
    domain_id: int,
    payload: DomainConfigUpdate,
    user: User = Depends(get_current_user),
    service: DomainConfigService = Depends(_get_service),
) -> DomainConfigOut:
    """Update a domain configuration."""
    try:
        domain = await service.update(domain_id, user.id, payload)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return DomainConfigOut.model_validate(domain)


@router.delete("/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_domain(
    domain_id: int,
    user: User = Depends(get_current_user),
    service: DomainConfigService = Depends(_get_service),
) -> None:
    """Delete a domain configuration."""
    try:
        await service.delete(domain_id, user.id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ------------------------------------------------------------------
# Detection test
# ------------------------------------------------------------------

@router.post("/detect", response_model=DomainDetectTestResponse)
async def test_detection(
    payload: DomainDetectTestPayload,
    user: User = Depends(get_current_user),
    service: DomainConfigService = Depends(_get_service),
) -> DomainDetectTestResponse:
    """Test domain detection against a sample payload."""
    detector = DomainDetector(service.repo)
    result = await detector.detect(
        payload=payload.payload,
        user_id=user.id,
        source=payload.source,
    )
    return DomainDetectTestResponse(**result)
