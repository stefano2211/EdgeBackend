"""Additional regression tests for services cleanups and optimizations."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

# Ensure project root is on path for backend.* imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.application.data_analysis.service import DataAnalystService
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


class TestDBQueryToolExceptionHandling:
    """Verify that the db_query tool handles database exceptions gracefully."""

    @pytest.mark.asyncio
    async def test_db_query_exception_returns_error_string(self):
        from backend.ia.tools.db import create_db_query_tool
        from unittest.mock import patch

        # Mock DatabaseConnectionService and the get_session contexts
        mock_conn = MagicMock()
        mock_conn.name = "test_db"
        mock_conn.id = "conn_123"

        mock_service = MagicMock()
        mock_service.list_connections = AsyncMock(return_value=[mock_conn])
        mock_service.execute_query = AsyncMock(side_effect=Exception("Database error details"))

        # Mock the get_session context manager in backend.ia.tools._session
        mock_session_context = AsyncMock()

        with patch("backend.ia.tools.db.get_session", return_value=mock_session_context), \
             patch("backend.ia.tools.db.DatabaseConnectionService", return_value=mock_service):
            tool = create_db_query_tool(user_id=1, context="chat")
            result = await tool.ainvoke({"connection_name": "test_db", "sql_query": "SELECT * FROM invalid_table;"})

            assert "Error executing query: Database error details" in result


class TestDataAnalystExecuteWithRetry:
    """Verify that DataAnalystService._execute_with_retry passes the correct user_id."""

    @pytest.mark.asyncio
    async def test_execute_with_retry_passes_user_id(self):
        from unittest.mock import patch, AsyncMock
        from backend.application.data_analysis.service import DataAnalystService

        session = AsyncMock()
        mock_db_service = MagicMock()
        mock_db_service.execute_query = AsyncMock()

        service = DataAnalystService(session, db_service=mock_db_service)
        
        with patch.object(service, '_is_safe_sql', return_value=True):
            await service._execute_with_retry(
                sql="SELECT 1;",
                connection_id="conn_123",
                connection_name="test_conn",
                user_id=42
            )
        
        mock_db_service.execute_query.assert_called_once_with(
            connection_id="conn_123",
            user_id=42,
            sql="SELECT 1;"
        )


class TestSubagentTokenFiltering:
    """Verify that _extract_chunk_payload filters out subagent tokens and routes them as thoughts."""

    def test_extract_chunk_payload_orchestrator_token(self):
        from backend.application.chat.orchestrator import _extract_chunk_payload
        from langchain_core.messages import AIMessageChunk

        token = AIMessageChunk(content="Hello from orchestrator")
        chunk = {
            "type": "messages",
            "data": (token, {"lc_agent_name": "orchestrator"})
        }

        agent, text, reasoning, agents_used, events = _extract_chunk_payload(
            chunk, current_agent="orchestrator", agents_used=set()
        )

        assert agent == "orchestrator"
        assert text == "Hello from orchestrator"
        assert not reasoning
        assert not events

    def test_extract_chunk_payload_subagent_token(self):
        from backend.application.chat.orchestrator import _extract_chunk_payload
        from backend.core.config import settings
        from langchain_core.messages import AIMessageChunk

        settings.SHOW_REASONING_IN_CHAT = True

        token = AIMessageChunk(content="Thinking by subagent")
        chunk = {
            "type": "messages",
            "data": (token, {"lc_agent_name": "db_analyst-agent"})
        }

        agent, text, reasoning, agents_used, events = _extract_chunk_payload(
            chunk, current_agent="orchestrator", agents_used=set()
        )

        assert agent == "db_analyst-agent"
        # Subagent tokens should be hidden from main text/reasoning output
        assert not text
        assert not reasoning
        # Instead, they should be routed as a thought event
        assert len(events) == 3  # subagent status complete, running, and thought events
        thought_event = next(e for e in events if e.get("type") == "thought")
        assert thought_event["agent"] == "db_analyst-agent"
        assert thought_event["content"] == "Thinking by subagent"


class TestRAGToolRetrieval:
    """Verify that RAG tool retrieve calls use context_tag instead of context parameter."""

    @pytest.mark.asyncio
    async def test_rag_tool_retrieve_calls_pipeline_retrieve(self):
        from unittest.mock import patch, AsyncMock
        from backend.ia.tools.rag import _rag_retrieve_impl

        # Mock the RetrievalPipeline
        mock_pipeline_instance = MagicMock()
        mock_pipeline_instance.retrieve = AsyncMock()

        with patch("backend.application.knowledge.rag.RetrievalPipeline", return_value=mock_pipeline_instance):
            await _rag_retrieve_impl(
                knowledge_base_ids=["kb_1"],
                query="test query",
                top_k=5,
                prefix="kb_",
                context="chat"
            )

        mock_pipeline_instance.retrieve.assert_called_once_with(
            knowledge_base_id="kb_1",
            query="test query",
            top_k=5,
            prefix="kb_",
            context_tag="chat"
        )





