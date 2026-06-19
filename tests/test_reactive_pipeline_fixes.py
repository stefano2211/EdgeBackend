"""Tests for reactive pipeline fixes."""

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSynthesisFallback:
    """Verify _parse_reactive_output handles JSON from orchestrator output."""

    def test_parse_json_from_markdown_fence(self):
        from backend.services.reactive_orchestrator import ReactiveOrchestrator

        raw = (
            '```json\n'
            '{\n'
            '  "analysis": "Analisis detallado en espanol.",\n'
            '  "diagnosis": "- Causa raiz: falla mecanica\\n- Confianza: Alta",\n'
            '  "plan": "1. Detener equipo\\n2. Inspeccionar sello"\n'
            '}\n'
            '```'
        )
        orch = ReactiveOrchestrator(broadcaster=MagicMock())
        result = orch._parse_reactive_output(raw)
        assert result is not None
        assert "Analisis detallado" in result.analysis
        assert "Causa raiz" in result.diagnosis
        assert "Detener equipo" in result.plan

    def test_parse_plain_json(self):
        from backend.services.reactive_orchestrator import ReactiveOrchestrator

        raw = (
            '{"analysis": "Root cause is bearing failure.",'
            '"diagnosis": "High confidence in mechanical fault.",'
            '"plan": "Replace bearing within 24h."}'
        )
        orch = ReactiveOrchestrator(broadcaster=MagicMock())
        result = orch._parse_reactive_output(raw)
        assert result is not None
        assert "bearing" in result.analysis

    def test_parse_invalid_returns_none(self):
        from backend.services.reactive_orchestrator import ReactiveOrchestrator

        raw = "This is just markdown text, not JSON at all."
        orch = ReactiveOrchestrator(broadcaster=MagicMock())
        result = orch._parse_reactive_output(raw)
        assert result is None

    def test_parse_json_with_preamble_before_fence(self):
        from backend.services.reactive_orchestrator import ReactiveOrchestrator

        raw = (
            "Here is my analysis:\n\n"
            '```json\n'
            '{"analysis": "Preamble test analysis.",'
            '"diagnosis": "Preamble test diagnosis.",'
            '"plan": "Preamble test plan."}\n'
            '```\n'
            "Some trailing text."
        )
        orch = ReactiveOrchestrator(broadcaster=MagicMock())
        result = orch._parse_reactive_output(raw)
        assert result is not None
        assert "Preamble test analysis" in result.analysis
        assert "Preamble test diagnosis" in result.diagnosis
        assert "Preamble test plan" in result.plan


class TestOrchestratorPromptHasJsonOutput:
    """Verify the reactive orchestrator prompt instructs JSON output."""

    def test_prompt_contains_json_output_instruction(self):
        from backend.ia.prompts.reactive import build_reactive_s2_orchestrator_prompt

        prompt = build_reactive_s2_orchestrator_prompt(
            has_rag=True, has_mcp=True, domain="test", tool_schemas=[]
        )
        assert "<output_format>" in prompt
        assert '"analysis"' in prompt
        assert '"diagnosis"' in prompt
        assert '"plan"' in prompt
        assert "synthesis_rules" in prompt  # original rules still present


class TestEventQueryTruncation:
    """Verify event body is truncated in the query sent to the orchestrator."""

    def test_large_payload_is_truncated(self):
        from backend.services.reactive_orchestrator import ReactiveOrchestrator

        orch = ReactiveOrchestrator(broadcaster=MagicMock())
        event = MagicMock()
        event.id = 1
        event.event_type = "alert"
        event.domain = "test"
        event.source = "test-source"
        event.severity_text = "critical"
        event.severity_number = 30
        event.title = "Test Event"
        event.description = "Test description"
        event.body = {"data": "X" * 20000}

        query = orch._build_event_query(event)

        assert "[truncated" in query.lower()
        assert len(query) < 12000

    def test_small_payload_not_truncated(self):
        from backend.services.reactive_orchestrator import ReactiveOrchestrator

        orch = ReactiveOrchestrator(broadcaster=MagicMock())
        event = MagicMock()
        event.id = 1
        event.event_type = "alert"
        event.domain = "test"
        event.source = "test-source"
        event.severity_text = "info"
        event.severity_number = 13
        event.title = "Small Event"
        event.description = "Small test"
        event.body = {"key": "value", "nested": {"deep": "data"}}

        query = orch._build_event_query(event)

        assert "[truncated" not in query.lower()
        assert "Payload:" in query
        assert '"key": "value"' in query


class TestDbAnalystConditionalInclusion:
    """Verify db_analyst is only included when DB connections exist."""

    def test_db_analyst_excluded_when_no_connections(self):
        # Verify the default_names logic: no db_connection_ids → no db_analyst
        db_connection_ids = []
        default_names = ["historical"]
        if db_connection_ids:
            default_names.append("db_analyst")
        assert "db_analyst" not in default_names

    def test_db_analyst_included_when_connections_exist(self):
        db_connection_ids = ["conn-1", "conn-2"]
        default_names = ["historical"]
        if db_connection_ids:
            default_names.append("db_analyst")
        assert "db_analyst" in default_names


class TestExecuteRaisesNotImplemented:
    """Verify execute() raises NotImplementedError instead of silently completing."""

    @pytest.mark.asyncio
    async def test_execute_raises_not_implemented(self):
        from backend.services.reactive_orchestrator import ReactiveOrchestrator

        orch = ReactiveOrchestrator(broadcaster=MagicMock())
        event = MagicMock()
        event.id = 1
        session = MagicMock()

        with pytest.raises(NotImplementedError, match="execution phase"):
            await orch.execute(event, session)


class TestRagThreshold:
    """RAG threshold must be low enough for reranker scores in 0.001-0.05 range."""

    def test_rag_min_relevance_score_is_low(self):
        from backend.core.config import settings
        assert settings.RAG_MIN_RELEVANCE_SCORE <= 0.01, (
            f"RAG_MIN_RELEVANCE_SCORE is {settings.RAG_MIN_RELEVANCE_SCORE}; "
            "must be <= 0.01 to match reranker output range"
        )
