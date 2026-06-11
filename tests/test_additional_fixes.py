"""Additional regression tests for services cleanups and optimizations."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

# Ensure project root is on path for backend.* imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.data_analyst_service import DataAnalystService
from backend.services.event_metric_service import EventMetricService


class TestDataAnalystSQLFallback:
    """Tests the improved _extract_sql_fallback method in DataAnalystService."""

    def test_extract_sql_with_semicolon(self):
        text = "Here is the query: SELECT * FROM users WHERE active = 1; Hope this helps."
        extracted = DataAnalystService._extract_sql_fallback(text)
        assert extracted == "SELECT * FROM users WHERE active = 1;"

    def test_extract_sql_without_semicolon(self):
        text = "Here is the query: SELECT * FROM users WHERE active = 1"
        extracted = DataAnalystService._extract_sql_fallback(text)
        # Semicolon-free regex matching extracts the SELECT portion to the end
        assert extracted == "SELECT * FROM users WHERE active = 1"

    def test_extract_sql_with_markdown_fences(self):
        text = "```sql\nSELECT name, email FROM clients;\n```"
        extracted = DataAnalystService._extract_sql_fallback(text)
        assert extracted == "SELECT name, email FROM clients;"

    def test_extract_sql_with_markdown_fences_no_semicolon(self):
        text = "```sql\nSELECT name, email FROM clients\n```"
        extracted = DataAnalystService._extract_sql_fallback(text)
        assert extracted == "SELECT name, email FROM clients"

    def test_extract_sql_with_with_clause(self):
        text = "```\nWITH active_users AS (SELECT id FROM users) SELECT count(*) FROM active_users\n```"
        extracted = DataAnalystService._extract_sql_fallback(text)
        assert extracted == "WITH active_users AS (SELECT id FROM users) SELECT count(*) FROM active_users"

    def test_extract_sql_no_select(self):
        text = "No query was generated because of a database connection error."
        extracted = DataAnalystService._extract_sql_fallback(text)
        assert extracted is None


class TestEventMetricServiceRollingAverage:
    """Tests that rolling averages use actually resolved events rather than events_analyzed."""

    @pytest.mark.asyncio
    async def test_record_event_resolved_rolling_average(self):
        session = AsyncMock()
        service = EventMetricService(session)

        # Mock event and metric
        now = datetime.now()
        event = MagicMock()
        event.domain = "manufacturing"
        event.event_type = "anomaly"
        event.created_at = now
        event.timestamp = now - timedelta(seconds=120)  # TTD = 120s
        event.resolved_at = now + timedelta(seconds=300)  # TTR = 300s
        event.status = "completed"

        metric = MagicMock()
        metric.events_analyzed = 10  # 10 events analyzed overall
        metric.events_auto_resolved = 1  # 1 auto-resolved so far
        metric.events_failed = 1  # 1 failed so far
        # Total resolved before this one: 2.
        # This event will make it 3 resolved events.
        metric.avg_ttd = 90.0  # Previous average TTD was 90s
        metric.avg_ttr = 200.0  # Previous average TTR was 200s

        # Mock _get_or_create_bucket to return our pre-configured metric
        service._get_or_create_bucket = AsyncMock(return_value=metric)

        await service.record_event_resolved(event)

        # Check that average is computed using resolved_count = 3 (since metric.events_auto_resolved + metric.events_failed + 1 = 3)
        # Formula: (previous_avg * (count - 1) + new_val) / count
        # For TTD: (90.0 * 2 + 120.0) / 3 = (180 + 120) / 3 = 100.0
        # For TTR: (200.0 * 2 + 300.0) / 3 = (400 + 300) / 3 = 700 / 3 = 233.333...
        assert metric.avg_ttd == pytest.approx(100.0)
        assert metric.avg_ttr == pytest.approx(233.33333333333334)


class TestPromptSubagentNaming:
    """Verify that no prompt templates or builder functions use incorrect db-agent naming."""

    def test_orchestrator_prompt_names(self):
        from backend.ia.prompts.orchestrator import build_orchestrator_prompt

        prompt = build_orchestrator_prompt(subagent_descriptions="test")
        
        # Should not refer to the old names in delegating instruction rules or examples
        assert "db-agent" not in prompt
        assert "data-analyst-agent" not in prompt
        # Should refer to db_analyst-agent
        assert "db_analyst-agent" in prompt

    def test_reactive_prompt_names(self):
        from backend.ia.prompts.reactive import build_reactive_s2_orchestrator_prompt

        prompt = build_reactive_s2_orchestrator_prompt(has_rag=True, has_mcp=True)

        assert "db-agent" not in prompt
        assert "db_analyst-agent" in prompt

