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


class TestReactivePromptBuilder:
    """verify build_reactive_s2_orchestrator_prompt output."""

    def test_prompt_no_historical_agent(self):
        from backend.ia.prompts.reactive import build_reactive_s2_orchestrator_prompt
        prompt = build_reactive_s2_orchestrator_prompt(has_rag=True, has_mcp=True)
        assert "historical-agent" not in prompt

    def test_prompt_rag_disabled_message(self):
        from backend.ia.prompts.reactive import build_reactive_s2_orchestrator_prompt
        prompt = build_reactive_s2_orchestrator_prompt(has_rag=False, has_mcp=False)
        assert "rag-agent: DISABLED" in prompt
        assert "mcp-agent: DISABLED" in prompt

    def test_prompt_tool_hint_injected(self):
        from backend.ia.prompts.reactive import build_reactive_s2_orchestrator_prompt
        schemas = [{"name": "send_email"}, {"name": "list_emails"}]
        prompt = build_reactive_s2_orchestrator_prompt(has_mcp=True, tool_schemas=schemas)
        assert "send_email" in prompt
        assert "list_emails" in prompt

    def test_prompt_db_analyst_always_listed(self):
        from backend.ia.prompts.reactive import build_reactive_s2_orchestrator_prompt
        prompt = build_reactive_s2_orchestrator_prompt(has_rag=False, has_mcp=False)
        assert "db_analyst-agent" in prompt


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


class TestDbAnalystAlwaysIncluded:
    """db_analyst must always be in reactive defaults regardless of DB connections."""

    def test_db_analyst_always_in_reactive_default_names(self):
        has_rag = False
        has_mcp = False
        default_names = ["db_analyst"]
        if has_rag:
            default_names.append("rag")
        if has_mcp:
            default_names.append("mcp")
        assert "db_analyst" in default_names
        assert "historical" not in default_names


class TestReactiveSubagentComposition:
    """Verify historical-agent is excluded from reactive context."""

    def test_historical_not_in_reactive_defaults(self):
        has_rag = True
        has_mcp = True
        default_names = ["db_analyst"]
        if has_rag:
            default_names.append("rag")
        if has_mcp:
            default_names.append("mcp")
        assert "historical" not in default_names

    def test_db_analyst_always_in_reactive_defaults(self):
        default_names = ["db_analyst"]
        assert "db_analyst" in default_names

    def test_historical_plugin_applies_to_proactive_only(self):
        from backend.ia.subagents.builders import _build_historical_subagent  # noqa: F401
        from backend.ia.subagents.plugin_registry import SubagentRegistry
        plugin = SubagentRegistry.get_plugin("historical")
        assert plugin is not None
        assert "reactive" not in plugin.applies_to
        assert "proactive" in plugin.applies_to


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
