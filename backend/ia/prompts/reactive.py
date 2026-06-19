"""Reactive Event Processing Prompts — loaded from Jinja2 templates."""

from backend.ia.prompts.loader import load_prompt


# ═══════════════════════════════════════════════════════════════════════════════
#  S2 AUTONOMOUS ORCHESTRATOR PROMPT (unified entry point)
# ═══════════════════════════════════════════════════════════════════════════════

def build_reactive_s2_orchestrator_prompt(
    has_rag: bool = True,
    has_mcp: bool = True,
    domain: str = "generic",
    tool_schemas: list[dict] | None = None,
) -> str:
    """Build the S2 autonomous orchestrator prompt for reactive event analysis.

    Describes available sub-agents for the sequential 4-phase pipeline.
    Phase order (DB → RAG → MCP → synthesis) is encoded in the template.

    Args:
        has_rag: Whether a RAG knowledge base is enabled.
        has_mcp: Whether MCP integration tools are enabled.
        domain: Domain hint (kept for context, not used in routing logic).
        tool_schemas: Optional list of {name, description} dicts for MCP tool docs.
    """
    subagent_lines: list[str] = []

    # db_analyst is always first — it is Phase 1 of the sequential pipeline
    subagent_lines.append(
        '- task("db_analyst-agent", ...) → Database query specialist. '
        "Queries connected databases for recent machine/equipment records. "
        "Always call this FIRST (Phase 1). "
        "Tools: list_db_connections, retrieve_relevant_schema, execute_data_query."
    )

    if has_rag:
        subagent_lines.append(
            '- task("rag-agent", ...) → Document search specialist. '
            "Searches manuals, procedures, and technical documentation. "
            "Call after Phase 1 (Phase 2), enriching the query with DB findings."
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
            "Sends emails, Slack messages, and executes registered integrations. "
            f"Call after Phase 2 (Phase 3) for external notifications.{tool_hint}"
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
#  SUB-AGENT PROMPTS — loaded from templates (used by subagents/builders.py)
# ═══════════════════════════════════════════════════════════════════════════════

REACTIVE_RAG_PROMPT = load_prompt("subagent_rag")
REACTIVE_MCP_PROMPT = load_prompt("subagent_mcp")
