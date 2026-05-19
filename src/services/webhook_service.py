"""WebhookService — CRUD, reception, mapping, and event ingestion for webhooks.

Public endpoint /webhooks/{slug}/receive is fully agnostic:
  - Accepts any JSON payload
  - Auto-discovers mapping if missing
  - Normalizes into EventIngestPayload
  - Delegates to EventService for the full pipeline
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.event import EventIngestPayload
from src.api.v1.schemas.webhook import (
    WebhookSourceCreate,
    WebhookSourceUpdate,
    WebhookTestResult,
)
from src.core.database import AsyncSessionLocal
from src.core.rate_limiter import SlidingWindowRateLimiter
from src.persistencia.models.webhook_source import WebhookSource
from src.persistencia.repositories.webhook_source_repository import WebhookSourceRepository
from src.services.webhook_mapping_engine import WebhookMappingEngine
from src.services.event_service import EventService
from src.services._helpers import commit_and_refresh

logger = logging.getLogger(__name__)

# Shared engine instance (stateless)
_engine = WebhookMappingEngine()
_rate_limiter = SlidingWindowRateLimiter()


class WebhookService:
    """Business logic for webhook sources."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = WebhookSourceRepository(session)

    # ═══════════════════════════════════════════════════════════════════════
    #  CRUD
    # ═══════════════════════════════════════════════════════════════════════

    async def create(
        self, user_id: int, data: WebhookSourceCreate
    ) -> WebhookSource:
        existing = await self.repo.get_by_slug(data.slug)
        if existing:
            raise ValueError(f"Webhook slug '{data.slug}' already exists")

        source = WebhookSource(
            user_id=user_id,
            name=data.name,
            slug=data.slug,
            description=data.description,
            is_enabled=data.is_enabled,
            mapping_config=data.mapping_config,
            rate_limit_rpm=data.rate_limit_rpm,
        )
        await self.repo.create(source)
        await commit_and_refresh(self.session, source)
        logger.info("Created webhook source '%s' (id=%d)", data.slug, source.id)
        return source

    async def list_for_user(self, user_id: int) -> list[WebhookSource]:
        return await self.repo.list_by_user(user_id)

    async def get_for_user(self, slug: str, user_id: int) -> WebhookSource | None:
        return await self.repo.get_by_slug_for_user(slug, user_id)

    async def update(
        self, slug: str, user_id: int, data: WebhookSourceUpdate
    ) -> WebhookSource:
        source = await self.repo.get_by_slug_for_user(slug, user_id)
        if not source:
            raise ValueError(f"Webhook '{slug}' not found")

        update_dict = data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(source, field, value)

        await self.repo.update(source)
        logger.info("Updated webhook source '%s'", slug)
        return source

    async def delete(self, slug: str, user_id: int) -> None:
        source = await self.repo.get_by_slug_for_user(slug, user_id)
        if not source:
            raise ValueError(f"Webhook '{slug}' not found")
        await self.repo.delete(source)
        logger.info("Deleted webhook source '%s'", slug)

    # ═══════════════════════════════════════════════════════════════════════
    #  Reception (public endpoint)
    # ═══════════════════════════════════════════════════════════════════════

    async def receive(
        self, slug: str, raw_payload: dict[str, Any],
        raw_body: bytes | None = None,
        signature_header: str | None = None,
    ) -> dict[str, Any]:
        """Receive a payload from an external webhook and create an event.

        This is the PUBLIC entrypoint — no Bearer auth required.
        """
        source = await self.repo.get_by_slug(slug)
        if not source:
            raise ValueError(f"Webhook '{slug}' not found")
        if not source.is_enabled:
            raise ValueError(f"Webhook '{slug}' is disabled")

        # HMAC signature verification (optional — only if webhook has signing_secret)
        signing_secret = getattr(source, "signing_secret", None)
        if signing_secret and raw_body is not None:
            if not signature_header:
                raise PermissionError("Missing webhook signature header")
            expected = "sha256=" + hmac.new(
                signing_secret.encode(),
                raw_body,
                hashlib.sha256,
            ).hexdigest()
            if not hmac.compare_digest(expected, signature_header):
                logger.warning("Webhook '%s': HMAC signature mismatch", slug)
                raise PermissionError("Invalid webhook signature")

        # Rate limiting
        rate_key = f"webhook:rate:{source.id}"
        allowed = await _rate_limiter.is_allowed(
            rate_key, max_requests=source.rate_limit_rpm, window_seconds=60
        )
        if not allowed:
            raise PermissionError("Rate limit exceeded")

        mapping = source.mapping_config
        auto_discovered = False

        # Auto-discover mapping if missing or empty
        if not mapping:
            logger.info(
                "No mapping for webhook '%s' — running auto-discover", slug
            )
            mapping = await _engine.auto_discover(raw_payload, source.name)
            source.mapping_config = mapping
            source.auto_discovered = True
            auto_discovered = True

        # Execute mapping
        try:
            payload = _engine.execute(raw_payload, mapping, webhook_name=source.name)
        except Exception as exc:
            logger.warning(
                "Mapping failed for webhook '%s': %s — attempting auto-discover",
                slug,
                exc,
            )
            mapping = await _engine.auto_discover(raw_payload, source.name)
            source.mapping_config = mapping
            source.auto_discovered = True
            auto_discovered = True
            payload = _engine.execute(raw_payload, mapping, webhook_name=source.name)

        # Force source to match webhook slug
        payload.source = source.slug

        # Persist auto-discovered mapping before creating event
        if auto_discovered:
            await self.session.commit()

        # Create event via EventService (isolated session)
        event = await self._create_event(source.user_id, payload)

        # Update statistics
        source.last_payload_preview = self._truncate_preview(raw_payload)
        source.last_received_at = datetime.now(timezone.utc).replace(tzinfo=None)
        source.total_received += 1
        await self.session.commit()

        return {
            "event_id": event.id if event else None,
            "status": "accepted",
            "auto_discovered": auto_discovered,
        }

    # ═══════════════════════════════════════════════════════════════════════
    #  Test mapping (no event creation)
    # ═══════════════════════════════════════════════════════════════════════

    async def test_mapping(
        self, slug: str, user_id: int, test_payload: dict[str, Any]
    ) -> WebhookTestResult:
        """Test a mapping configuration without creating an event."""
        source = await self.repo.get_by_slug_for_user(slug, user_id)
        if not source:
            raise ValueError(f"Webhook '{slug}' not found")

        mapping = source.mapping_config
        auto_discovered = False

        if not mapping:
            mapping = await _engine.auto_discover(test_payload, source.name)
            auto_discovered = True

        try:
            result = _engine.execute(test_payload, mapping, webhook_name=source.name)
        except Exception as exc:
            # If existing mapping fails, try auto-discover
            if not auto_discovered:
                mapping = await _engine.auto_discover(test_payload, source.name)
                auto_discovered = True
                result = _engine.execute(test_payload, mapping, webhook_name=source.name)
            else:
                raise ValueError(f"Mapping execution failed: {exc}")

        return WebhookTestResult(
            mapping_used=mapping,
            auto_discovered=auto_discovered,
            extracted_fields={
                "title": result.title,
                "description": result.description,
                "severity_text": result.severity_text.value if result.severity_text else None,
                "severity_number": result.severity_number,
                "source": result.source,
                "event_type": result.type,
                "timestamp": result.timestamp.isoformat() if result.timestamp else None,
                "subject": result.subject,
            },
            body_preview=result.data or {},
            would_create_event=True,
        )

    # ═══════════════════════════════════════════════════════════════════════
    #  Private helpers
    # ═══════════════════════════════════════════════════════════════════════

    async def _create_event(
        self, user_id: int, payload: EventIngestPayload
    ) -> Any:
        """Delegate event creation to EventService."""
        service = EventService(self.session)
        return await service.ingest_event(payload, triggered_by_user_id=user_id)

    @staticmethod
    def _truncate_preview(payload: dict[str, Any], max_size: int = 2048) -> dict[str, Any]:
        """Create a small preview of the payload for DB storage."""
        preview = dict(payload)
        # Truncate any large string values
        for key, value in list(preview.items()):
            if isinstance(value, str) and len(value) > 500:
                preview[key] = value[:500] + "..."
            if isinstance(value, dict):
                preview[key] = {k: v for k, v in list(value.items())[:20]}
        return preview
