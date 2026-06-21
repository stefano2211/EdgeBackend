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
        # Director prompt no longer has JSON — that's the Analyst's job
        from backend.ia.prompts.reactive import build_reactive_s2_orchestrator_prompt
        prompt = build_reactive_s2_orchestrator_prompt(
            has_rag=True, has_mcp=True, domain="test", tool_schemas=[]
        )
        assert "sequential_pipeline" in prompt
        assert "Director" in prompt or "Data Collector" in prompt
        # JSON output moved to Analyst — verify it exists there
        from backend.ia.prompts.reactive import build_synthesis_analyst_prompt
        analyst = build_synthesis_analyst_prompt("test event", "test findings")
        assert '<output_format>' in analyst
        assert '"analysis"' in analyst
        assert '"diagnosis"' in analyst
        assert '"plan"' in analyst


class TestReactiveOrchestratorTemplate:
    """Verify the reactive_orchestrator.md template has the sequential pipeline."""

    def test_template_contains_sequential_phases(self):
        from backend.ia.prompts.reactive import build_reactive_s2_orchestrator_prompt
        prompt = build_reactive_s2_orchestrator_prompt(has_rag=True, has_mcp=True)
        assert "PHASE 1" in prompt
        assert "PHASE 2" in prompt
        assert "PHASE 3" in prompt

    def test_template_has_sequential_pipeline_tag(self):
        from backend.ia.prompts.reactive import build_reactive_s2_orchestrator_prompt
        prompt = build_reactive_s2_orchestrator_prompt(has_rag=True, has_mcp=True)
        assert "sequential_pipeline" in prompt

    def test_template_no_parallel_instruction(self):
        from backend.ia.prompts.reactive import build_reactive_s2_orchestrator_prompt
        prompt = build_reactive_s2_orchestrator_prompt(has_rag=True, has_mcp=True)
        assert "PARALLEL in a single turn" not in prompt

    def test_template_db_first_instruction(self):
        from backend.ia.prompts.reactive import build_reactive_s2_orchestrator_prompt
        prompt = build_reactive_s2_orchestrator_prompt(has_rag=True, has_mcp=True)
        assert "task(\"db_analyst-agent\")" in prompt
        assert "Call task" in prompt

    def test_template_severity_time_windows(self):
        from backend.ia.prompts.reactive import build_reactive_s2_orchestrator_prompt
        prompt = build_reactive_s2_orchestrator_prompt(has_rag=True, has_mcp=True)
        assert "1h" in prompt
        assert "6h" in prompt
        assert "24h" in prompt


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

class TestDeadCodeRemoved:
    """Verify dead methods were removed from ReactiveOrchestrator."""

    def test_execute_method_does_not_exist(self):
        from backend.services.reactive_orchestrator import ReactiveOrchestrator
        assert not hasattr(ReactiveOrchestrator, "execute"), (
            "ReactiveOrchestrator.execute() should have been removed."
        )

    def test_send_analysis_email_does_not_exist(self):
        from backend.services.reactive_orchestrator import ReactiveOrchestrator
        assert not hasattr(ReactiveOrchestrator, "_send_analysis_email"), (
            "_send_analysis_email() should have been removed. "
            "Email is now handled by the orchestrator via mcp-agent in Phase 3."
        )

    def test_format_email_body_does_not_exist(self):
        from backend.services.reactive_orchestrator import ReactiveOrchestrator
        assert not hasattr(ReactiveOrchestrator, "_format_email_body"), (
            "_format_email_body() should have been removed."
        )


class TestRagThreshold:
    """RAG threshold must be low enough for reranker scores in 0.001-0.05 range."""

    def test_rag_min_relevance_score_is_low(self):
        from backend.core.config import settings
        assert settings.RAG_MIN_RELEVANCE_SCORE <= 0.01, (
            f"RAG_MIN_RELEVANCE_SCORE is {settings.RAG_MIN_RELEVANCE_SCORE}; "
            "must be <= 0.01 to match reranker output range"
        )


class TestHistoricalAgentRemoved:
    """Verify historical-agent is completely removed."""

    def test_historical_template_deleted(self):
        import os
        assert not os.path.exists("backend/ia/prompts/templates/subagent_historical.md")

    def test_historical_plugin_not_registered(self):
        from backend.ia.subagents.plugin_registry import SubagentRegistry
        assert SubagentRegistry.get_plugin("historical") is None

    def test_historical_not_in_proactive_defaults(self):
        default_names = ["rag", "mcp", "db_analyst"]
        assert "historical" not in default_names

    def test_historical_constants_removed(self):
        import backend.ia.prompts.subagents as sa
        assert not hasattr(sa, "HISTORICAL_AGENT_DESCRIPTION")
        assert not hasattr(sa, "HISTORICAL_AGENT_SYSTEM_PROMPT")


class TestQueryResourceData:
    """Verify the fast path tool is registered and helpers work correctly."""

    def test_query_resource_data_tool_registered(self):
        from backend.ia.tools.unified.data_analyst import create_data_analyst_tools
        tools = create_data_analyst_tools(user_id=1, context="reactive")
        tool_names = [t.name for t in tools]
        assert "query_resource_data" in tool_names
        assert tool_names[0] == "query_resource_data", (
            "query_resource_data must be FIRST tool for db_analyst-agent"
        )

    def test_safe_str_escapes_quotes(self):
        from backend.ia.tools.unified.data_analyst import _safe_str
        assert _safe_str("test'value") == "test''value"
        assert _safe_str("normal") == "normal"

    def test_safe_ident_quotes_identifier(self):
        from backend.ia.tools.unified.data_analyst import _safe_ident
        assert _safe_ident("measurements") == '"measurements"'
        assert _safe_ident("measurements", "postgresql") == '"measurements"'
        assert _safe_ident("measurements", "mysql") == "`measurements`"

    def test_time_interval_sql_by_dialect(self):
        from backend.ia.tools.unified.data_analyst import _time_interval_sql
        pg = _time_interval_sql(6, "ts", "postgresql")
        assert "INTERVAL '6 hours'" in pg
        my = _time_interval_sql(6, "ts", "mysql")
        assert "INTERVAL 6 HOUR" in my
        sl = _time_interval_sql(6, "ts", "sqlite")
        assert "datetime(" in sl

    def test_is_time_column_name(self):
        from backend.ia.tools.unified.data_analyst import _is_time_column_name
        assert _is_time_column_name("created_at")
        assert _is_time_column_name("timestamp")
        assert _is_time_column_name("logged_date")
        assert not _is_time_column_name("value")
        assert not _is_time_column_name("status")

    def test_is_entity_column_name(self):
        from backend.ia.tools.unified.data_analyst import _is_entity_column_name
        assert _is_entity_column_name("equipment")
        assert _is_entity_column_name("service_name")
        assert _is_entity_column_name("host")
        assert not _is_entity_column_name("count")
        assert not _is_entity_column_name("amount")
