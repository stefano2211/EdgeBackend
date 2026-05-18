"""Domain configuration router.

CRUD for user-defined domains and a test endpoint for detection rules.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.deps import get_current_user
from src.persistencia.models.user import User
from src.persistencia.repositories.domain_config_repository import DomainConfigRepository
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


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

async def _get_repo(session: AsyncSession = Depends(get_db)) -> DomainConfigRepository:
    return DomainConfigRepository(session)


# ------------------------------------------------------------------
# CRUD
# ------------------------------------------------------------------

@router.get("", response_model=DomainConfigListResponse)
async def list_domains(
    user: User = Depends(get_current_user),
    repo: DomainConfigRepository = Depends(_get_repo),
) -> DomainConfigListResponse:
    """List all domain configurations for the current user."""
    items = await repo.list_for_user(user.id)
    return DomainConfigListResponse(items=items)


@router.post("", response_model=DomainConfigOut, status_code=status.HTTP_201_CREATED)
async def create_domain(
    payload: DomainConfigCreate,
    user: User = Depends(get_current_user),
    repo: DomainConfigRepository = Depends(_get_repo),
) -> DomainConfigOut:
    """Create a new domain configuration."""
    from src.persistencia.models.domain_config import DomainConfig

    # Ensure uniqueness per user
    existing = await repo.get_by_name_for_user(user.id, payload.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Domain '{payload.name}' already exists",
        )

    domain = DomainConfig(
        user_id=user.id,
        name=payload.name,
        display_name=payload.display_name,
        detection_rules=payload.detection_rules.model_dump() if payload.detection_rules else None,
        is_default=payload.is_default,
    )
    await repo.create(domain)
    return DomainConfigOut.model_validate(domain)


@router.get("/{domain_id}", response_model=DomainConfigOut)
async def get_domain(
    domain_id: int,
    user: User = Depends(get_current_user),
    repo: DomainConfigRepository = Depends(_get_repo),
) -> DomainConfigOut:
    """Get a single domain configuration."""
    domain = await repo.get_by_id(domain_id)
    if not domain or domain.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")
    return DomainConfigOut.model_validate(domain)


@router.put("/{domain_id}", response_model=DomainConfigOut)
async def update_domain(
    domain_id: int,
    payload: DomainConfigUpdate,
    user: User = Depends(get_current_user),
    repo: DomainConfigRepository = Depends(_get_repo),
) -> DomainConfigOut:
    """Update a domain configuration."""
    domain = await repo.get_by_id(domain_id)
    if not domain or domain.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")

    if payload.display_name is not None:
        domain.display_name = payload.display_name
    if payload.detection_rules is not None:
        domain.detection_rules = payload.detection_rules.model_dump()
    if payload.is_default is not None:
        domain.is_default = payload.is_default
    if payload.is_enabled is not None:
        domain.is_enabled = payload.is_enabled

    await repo.update(domain)
    return DomainConfigOut.model_validate(domain)


@router.delete("/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_domain(
    domain_id: int,
    user: User = Depends(get_current_user),
    repo: DomainConfigRepository = Depends(_get_repo),
) -> None:
    """Delete a domain configuration."""
    domain = await repo.get_by_id(domain_id)
    if not domain or domain.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")
    await repo.delete(domain)


# ------------------------------------------------------------------
# Detection test
# ------------------------------------------------------------------

@router.post("/detect", response_model=DomainDetectTestResponse)
async def test_detection(
    payload: DomainDetectTestPayload,
    user: User = Depends(get_current_user),
    repo: DomainConfigRepository = Depends(_get_repo),
) -> DomainDetectTestResponse:
    """Test domain detection against a sample payload."""
    detector = DomainDetector(repo)
    result = await detector.detect(
        payload=payload.payload,
        user_id=user.id,
        source=payload.source,
    )
    return DomainDetectTestResponse(**result)
