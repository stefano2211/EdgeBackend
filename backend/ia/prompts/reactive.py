"""Reactive Event Processing Prompts — loaded from Jinja2 templates.

Replaces monolithic strings with renderable .md templates.
All prompts are domain-agnostic — no hardcoded industry references.
"""

import json
from typing import List

from backend.core.config import settings
from backend.ia.prompts.loader import load_prompt
from backend.ia.schemas.reactive import ReactiveAnalysisOutput


# ═══════════════════════════════════════════════════════════════════════════════
#  PHASE 1 — S2 TRIAGE PROMPT
# ═══════════════════════════════════════════════════════════════════════════════

REACTIVE_S2_TRIAGE_PROMPT = load_prompt("reactive_triage")


# ═══════════════════════════════════════════════════════════════════════════════
#  PHASE 3 — S2 SYNTHESIS PROMPT
# ═══════════════════════════════════════════════════════════════════════════════

def build_reactive_synthesis_prompt(
    subagent_descriptions: str = "",
    system1_analysis: str = "",
    domain_data: str = "",
    event_context: str = "",
) -> str:
    """Build the System-2 synthesis prompt dynamically."""
    input_sections = ""
    if system1_analysis:
        input_sections += f"<system1_analysis>\n{system1_analysis}\n</system1_analysis>\n\n"
    if domain_data:
        input_sections += f"<domain_data>\n{domain_data}\n</domain_data>\n\n"

    return load_prompt(
        "reactive_synthesis",
        input_sections=input_sections,
        event_context=event_context,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  S2 AUTONOMOUS ORCHESTRATOR PROMPT (unified entry point)
# ═══════════════════════════════════════════════════════════════════════════════

def build_reactive_s2_orchestrator_prompt(
    has_rag: bool = True,
    has_mcp: bool = True,
    domain: str = "generic",
    tool_schemas: list[dict] | None = None,
) -> str:
    """Build the S2 autonomous orchestrator prompt — unified entry point.

    Args:
        has_rag: Whether RAG sub-agent is available.
        has_mcp: Whether MCP sub-agent is available.
        domain: Domain hint (unused in agnostic prompts, kept for context).
        tool_schemas: Optional list of {name, description, parameter_schema} dicts
                      for dynamic MCP tool documentation.
    """
    subagent_lines = []
    delegation_rules = []

    if has_rag:
        delegation_rules.append(
            "[DELEGATE to rag-agent] when:\n"
            "  - Procedures, manuals, documentation, or regulatory information is needed.\n"
            "  - The event references policies, standards, or operational limits defined in documents.\n"
            "  - The triage indicates needs_document_lookup=true.\n"
        )
        subagent_lines.append(
            '- task("rag-agent", ...) → Document search specialist. '
            "Searches manuals, procedures, standards, and technical documentation using RAG. "
            "Uses precise filters and returns complete citations with extracted text."
        )
    else:
        delegation_rules.append(
            "NOTE: The rag-agent (document search) is DISABLED.\n"
            "You cannot consult manuals or procedures. If the event requires it, note this limitation.\n"
        )

    if has_mcp:
        # Build dynamic tool hint from schemas if available
        tool_hint = ""
        if tool_schemas:
            tool_names = [t.get("name", "?") for t in tool_schemas]
            tool_hint = f" Available tools: {', '.join(tool_names)}."

        delegation_rules.append(
            "[DELEGATE to mcp-agent] when:\n"
            "  - Current metrics, resource status, or real-time data is needed.\n"
            "  - Actions on external systems or registered integrations are required.\n"
            "  - The triage indicates needs_realtime_data=true (treat as a strong hint).\n"
            f"{f'  - {tool_hint}' if tool_hint else ''}\n"
        )
        subagent_lines.append(
            '- task("mcp-agent", ...) → Live data and integration specialist. '
            "Executes APIs and queries external systems via registered integrations. "
            f"Uses specific filters per resource and metric. Returns ALL records.{tool_hint}"
        )
    else:
        delegation_rules.append(
            "NOTE: The mcp-agent (live data & integrations) is DISABLED.\n"
            "You cannot obtain live metrics or interact with external systems. "
            "If the event requires it, note this limitation.\n"
        )

    subagent_lines.append(
        '- task("historical-agent", ...) → Historical diagnosis specialist. '
        "Identifies precedents, recurring failure patterns, and correlations with past incidents. "
        "Uses fine-tuned weights, no external tools. Always fast and cheap to invoke."
    )

    subagents_section = "\n".join(subagent_lines)
    data_delegation_rules = "\n".join(delegation_rules)

    schema_json = json.dumps(
        ReactiveAnalysisOutput.model_json_schema(),
        ensure_ascii=False,
        indent=2,
    )

    return load_prompt(
        "reactive_orchestrator",
        subagents_section=subagents_section,
        domain_delegation_rules=data_delegation_rules,
        schema_json=schema_json,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  LEGACY BACKWARD COMPATIBILITY
# ═══════════════════════════════════════════════════════════════════════════════

_LEGACY_SUBAGENT_DESCRIPTIONS = {
    "rag-agent": (
        "Document search and knowledge retrieval specialist. "
        "Searches manuals, procedures, regulations, technical specs, and compliance documents. "
        "Has access to rag_retrieve for RAG knowledge base queries."
    ),
    "mcp-agent": (
        "Live data and API execution specialist. "
        "Fetches real-time metrics, resource status, and system state. "
        "Has access to mcp_execute for live API/tool calls."
    ),
    "historical-agent": (
        "Historical data pattern matcher. "
        "Identifies precedents, recurring failure patterns, and correlations with past incidents. "
        "Knowledge baked into fine-tuned weights — does NOT use external tools."
    ),

}

_UNAVAILABLE_MSG = "(NOT AVAILABLE — do not use)"


def build_reactive_orchestrator_prompt(available_subagents: List[str]) -> str:
    """Build the legacy Reactive Orchestrator system prompt.

    DEPRECATED: Use build_reactive_s2_orchestrator_prompt for new reactive pipeline.
    Kept for backward compatibility with existing tests/calls.
    """
    available_set = set(available_subagents)
    lines = []
    for name, desc in _LEGACY_SUBAGENT_DESCRIPTIONS.items():
        if name in available_set:
            lines.append(f'- subagent_type="{name}" [AVAILABLE] → {desc}')
        else:
            lines.append(f'- subagent_type="{name}" {_UNAVAILABLE_MSG}')

    available_subagents_section = "\n".join(lines) if lines else "None registered."
    return load_prompt(
        "reactive_synthesis",
        input_sections=f"<available_subagents>\n{available_subagents_section}\n</available_subagents>\n\n",
        event_context="Event context provided at runtime.",
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  S1 COORDINATOR DESCRIPTION (for subagent registry)
# ═══════════════════════════════════════════════════════════════════════════════

S1_COORDINATOR_DESCRIPTION = (
    "System-1 Fast Intuition Coordinator. "
    "Delegates in parallel to historical-agent (pattern matching >6 months) "

    "Performs visual verification of dashboards and web interfaces when required. "
    "Use ALWAYS when an alarm or problem is detected to get fast patterns and visual confirmation."
)


# ═══════════════════════════════════════════════════════════════════════════════
#  REACTIVE RAG / MCP PROMPTS — loaded from templates
# ═══════════════════════════════════════════════════════════════════════════════

REACTIVE_RAG_PROMPT = load_prompt("subagent_rag")
REACTIVE_MCP_PROMPT = load_prompt("subagent_mcp")
REACTIVE_HISTORICAL_PROMPT = load_prompt("subagent_historical")
