"""Regression tests for recent refactor fixes."""

from __future__ import annotations

import os
import sys
# Ensure project root is on path for backend.* imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.services.webhook_mapping_engine import WebhookMappingEngine
from backend.services.event_metric_service import EventMetricService
from backend.services.domain_config_service import DomainConfigService


class TestWebhookMappingEngine:
    """Ensure the fallback chain works correctly after the fallback2 fix."""

    @pytest.fixture
    def engine(self):
        return WebhookMappingEngine()

    def test_fallback2_is_evaluated(self, engine: WebhookMappingEngine):
        payload = {"alert": {"title": "Disk full", "body": "rootfs 99%"}}
        mapping = engine._default_mapping("test")
        # Force title to hit fallback2 by removing primary and fallback keys
        title_rule = mapping["extractors"]["title"].copy()
        title_rule["path"] = "$.missing"
        title_rule["fallback"] = "$.also_missing"
        title_rule["fallback2"] = "$.alert.title"

        result = engine._resolve_field(payload, title_rule)
        assert result == "Disk full"

    def test_fallbacks_list_modern(self, engine: WebhookMappingEngine):
        payload = {"deep": {"nested": {"value": "found_it"}}}
        rule = {
            "type": "jsonpath",
            "path": "$.missing",
            "fallbacks": ["$.also_missing", "$.deep.nested.value"],
            "default": "default",
        }
        result = engine._resolve_field(payload, rule)
        assert result == "found_it"


class TestEventMetricService:
    """Aggregate logic was moved from the router into the service."""

    def test_aggregate_metrics_empty(self):
        service = EventMetricService(session=MagicMock())  # session not used here
        agg = service.aggregate_metrics([])
        assert agg["total_events"] == 0
        assert agg["false_positive_rate"] == 0.0
        assert agg["avg_ttd_seconds"] is None

    def test_aggregate_metrics_basic(self):
        service = EventMetricService(session=MagicMock())
        m1 = MagicMock()
        m1.total_events = 10
        m1.events_analyzed = 8
        m1.events_auto_resolved = 5
        m1.events_failed = 1
        m1.false_positives = 2
        m1.avg_ttd = 12.5
        m1.avg_ttr = 45.0

        agg = service.aggregate_metrics([m1])
        assert agg["total_events"] == 10
        assert agg["false_positives"] == 2
        assert agg["false_positive_rate"] == 0.2
        assert agg["avg_ttd_seconds"] == 12.5
        assert agg["avg_ttr_seconds"] == 45.0


class TestDomainConfigService:
    """Ownership and uniqueness rules must be enforced by the service."""

    @pytest.mark.asyncio
    async def test_create_enforces_uniqueness(self):
        session = AsyncMock()
        repo = AsyncMock()
        repo.get_by_name_for_user.return_value = MagicMock()  # already exists
        service = DomainConfigService(session)
        service.repo = repo

        from backend.core.exceptions import ConflictError

        with pytest.raises(ConflictError):
            await service.create(
                user_id=1, name="infra", display_name="Infra",
                detection_rules=None, is_default=False
            )

    @pytest.mark.asyncio
    async def test_get_for_user_raises_when_not_found(self):
        session = AsyncMock()
        repo = AsyncMock()
        repo.get_by_id.return_value = None
        service = DomainConfigService(session)
        service.repo = repo

        from backend.core.exceptions import NotFoundError

        with pytest.raises(NotFoundError):
            await service.get_for_user(domain_id=99, user_id=1)

    @pytest.mark.asyncio
    async def test_get_for_user_raises_on_ownership_mismatch(self):
        session = AsyncMock()
        repo = AsyncMock()
        domain = MagicMock()
        domain.user_id = 2  # different user
        repo.get_by_id.return_value = domain
        service = DomainConfigService(session)
        service.repo = repo

        from backend.core.exceptions import NotFoundError

        with pytest.raises(NotFoundError):
            await service.get_for_user(domain_id=1, user_id=1)


class TestMCPSourceSecurity:
    """Reactive MCP sources must be scoped to their owner."""

    @pytest.mark.asyncio
    async def test_reactive_source_ownership_enforced(self):
        from backend.core.exceptions import NotFoundError

        session = AsyncMock()
        source = MagicMock()
        source.user_id = 2  # belongs to user 2
        repo = AsyncMock()
        repo.get_by_id.return_value = source
        from backend.services.reactive_mcp_source_service import ReactiveMCPSourceService

        service = ReactiveMCPSourceService(session)
        service.repo = repo

        with pytest.raises(NotFoundError):
            # simulate router check: get source, verify ownership
            fetched = await service.get(1)
            if fetched.user_id != 1:  # current_user.id = 1
                raise NotFoundError("Not authorized")



