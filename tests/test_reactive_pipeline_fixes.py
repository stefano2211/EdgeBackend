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
