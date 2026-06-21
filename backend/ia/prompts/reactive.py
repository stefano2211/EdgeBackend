"""Reactive Event Processing Prompts — loaded from Jinja2 templates."""

from backend.ia.prompts.loader import load_prompt


# ═══════════════════════════════════════════════════════════════════════════════
#  DIRECTOR PROMPT — dispatches to sub-agents, collects raw data only
# ═══════════════════════════════════════════════════════════════════════════════

def build_reactive_s2_orchestrator_prompt(
    has_rag: bool = True,
    has_mcp: bool = True,
    domain: str = "generic",
    tool_schemas: list[dict] | None = None,
) -> str:
    """Build the Director agent prompt — collects data from sub-agents only.

    The Director dispatches to db_analyst, rag, and mcp agents in sequence.
    It does NOT synthesize or produce JSON — a separate Analyst agent handles that.
    """
    subagent_lines: list[str] = []

    subagent_lines.append(
        '- task("db_analyst-agent", ...) → Database query specialist. '
        "Queries connected databases for recent records. "
        "Always call this FIRST (Phase 1). "
        "Tools: query_resource_data, execute_data_query."
    )

    if has_rag:
        subagent_lines.append(
            '- task("rag-agent", ...) → Document search specialist. '
            "Searches manuals, procedures, and technical documentation. "
            "Call after Phase 1 (Phase 2)."
        )
    else:
        subagent_lines.append(
            "- rag-agent: DISABLED — no knowledge bases configured. Skip Phase 2."
        )

    if has_mcp:
        tool_hint = ""
        if tool_schemas:
            tool_names = [t.get("name", "?") for t in tool_schemas]
            tool_hint = f" Available tools: {', '.join(tool_names)}."
        subagent_lines.append(
            '- task("mcp-agent", ...) → Integration and action specialist. '
            "Sends emails, messages, executes integrations. "
            f"Call after Phase 2 (Phase 3).{tool_hint}"
        )
    else:
        subagent_lines.append(
            "- mcp-agent: DISABLED — no integration tools configured. Skip Phase 3."
        )

    subagents_section = "\n".join(subagent_lines)

    return load_prompt(
        "reactive_orchestrator",
        subagents_section=subagents_section,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  ANALYST PROMPT — cross-checks sub-agent findings against event claims
# ═══════════════════════════════════════════════════════════════════════════════

def build_synthesis_analyst_prompt(
    event_context: str,
    subagent_findings: str,
) -> str:
    """Build the Synthesis Analyst prompt — cross-checks and produces structured JSON.

    This is called AFTER the Director has collected all sub-agent data.
    The Analyst receives the event context and raw sub-agent findings,
    applies strict cross-check rules, and produces ReactiveAnalysisOutput JSON.
    """
    return load_prompt(
        "synthesis_analyst",
        event_context=event_context,
        subagent_findings=subagent_findings,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  SUB-AGENT PROMPTS — loaded from templates (used by subagents/builders.py)
# ═══════════════════════════════════════════════════════════════════════════════

REACTIVE_RAG_PROMPT = load_prompt("subagent_rag")
REACTIVE_MCP_PROMPT = load_prompt("subagent_mcp")
