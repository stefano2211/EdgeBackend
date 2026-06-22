"""Webhooks router — CRUD + public reception + test mapping.

Public endpoints (no Bearer auth):
  POST /webhooks/{slug}/receive

Authenticated endpoints (Bearer required):
  POST   /api/v1/webhooks
  GET    /api/v1/webhooks
  GET    /api/v1/webhooks/{slug}
  PATCH  /api/v1/webhooks/{slug}
  DELETE /api/v1/webhooks/{slug}
  POST   /api/v1/webhooks/{slug}/test
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.presentation.schemas.webhook import (
    WebhookSourceCreate,
    WebhookSourceOut,
    WebhookSourceUpdate,
    WebhookTestPayload,
    WebhookTestResult,
)
from backend.core.deps import get_db, get_current_user
from backend.domain.models.user import User
from backend.application.events.webhook import WebhookService

logger = logging.getLogger(__name__)

# Authenticated router under /api/v1
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Public router (no prefix — mounted at root)
public_router = APIRouter(tags=["webhooks-public"])


# ═══════════════════════════════════════════════════════════════════════════
#  Authenticated CRUD
# ═══════════════════════════════════════════════════════════════════════════

@router.post("", response_model=WebhookSourceOut, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    data: WebhookSourceCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> WebhookSourceOut:
    """Create a new webhook source."""
    service = WebhookService(session)
    try:
        source = await service.create(current_user.id, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    return WebhookSourceOut.model_validate(source)


@router.get("", response_model=list[WebhookSourceOut])
async def list_webhooks(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[WebhookSourceOut]:
    """List webhook sources for the current user."""
    service = WebhookService(session)
    items = await service.list_for_user(current_user.id)
    return [WebhookSourceOut.model_validate(i) for i in items]


@router.get("/{slug}", response_model=WebhookSourceOut)
async def get_webhook(
    slug: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> WebhookSourceOut:
    """Get a single webhook source."""
    service = WebhookService(session)
    source = await service.get_for_user(slug, current_user.id)
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    return WebhookSourceOut.model_validate(source)


@router.patch("/{slug}", response_model=WebhookSourceOut)
async def update_webhook(
    slug: str,
    data: WebhookSourceUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> WebhookSourceOut:
    """Update a webhook source (mapping config, rate limit, etc.)."""
    service = WebhookService(session)
    try:
        source = await service.update(slug, current_user.id, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return WebhookSourceOut.model_validate(source)


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    slug: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    """Delete a webhook source."""
    service = WebhookService(session)
    try:
        await service.delete(slug, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/{slug}/test", response_model=WebhookTestResult)
async def test_webhook_mapping(
    slug: str,
    data: WebhookTestPayload,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> WebhookTestResult:
    """Test a mapping configuration without creating an event."""
    service = WebhookService(session)
    try:
        return await service.test_mapping(slug, current_user.id, data.payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ═══════════════════════════════════════════════════════════════════════════
#  Public reception endpoint (no auth)
# ═══════════════════════════════════════════════════════════════════════════

@public_router.post(
    "/webhooks/{slug}/receive",
    status_code=status.HTTP_202_ACCEPTED,
)
async def receive_webhook(
    slug: str,
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> dict:
    """Public endpoint for external systems to push events.

    Accepts **any JSON payload**. The engine maps it dynamically.
    If no mapping exists, auto-discovery runs via LLM and persists the result.
    """
    raw_body = await request.body()
    try:
        import json as _json
        payload = _json.loads(raw_body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    signature_header = (
        request.headers.get("X-Hub-Signature-256")
        or request.headers.get("X-Webhook-Signature")
        or request.headers.get("X-Signature")
    )

    service = WebhookService(session)
    try:
        result = await service.receive(slug, payload, raw_body=raw_body, signature_header=signature_header)
    except ValueError as exc:
        detail = str(exc)
        # A disabled webhook is a *state* conflict, not "not found"
        if "disabled" in detail.lower():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    except PermissionError as exc:
        detail = str(exc)
        # Distinguish between auth/signature failures (401/403) and rate-limiting (429)
        if "signature" in detail.lower() or "missing webhook" in detail.lower():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail=detail
            )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail
        )
    except Exception as exc:
        logger.exception("Webhook receive failed for '%s': %s", slug, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process webhook payload",
        )
    return result
