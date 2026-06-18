"""Sub-agent prompts: descriptions + system_prompts for the registry.

System prompts are loaded from Jinja2 templates in templates/.
Descriptions are domain-agnostic — no hardcoded tool or integration names.
"""

from backend.ia.prompts.loader import load_prompt

# ── RAG Agent ──
RAG_AGENT_DESCRIPTION = (
    "Document search and knowledge retrieval specialist. "
    "Use ONLY when the user query requires searching manuals, SOPs, regulations, "
    "technical specifications, compliance documents, or any written documentation. "
    "Has access to: rag_retrieve (document/knowledge base search). "
    "ALWAYS delegate here for questions about norms, procedures, documentation, "
    "or safety limits defined in written materials. "
    "Do NOT use for: live data, real-time API calls, historical trends, or web UI automation."
)


def build_rag_system_prompt(kb_catalog: str = "") -> str:
    """Build RAG agent system prompt with dynamic KB catalog."""
    return load_prompt("subagent_rag", kb_catalog=kb_catalog)


RAG_AGENT_SYSTEM_PROMPT = build_rag_system_prompt()


# ── MCP Agent ──
MCP_AGENT_DESCRIPTION = (
    "External integration and live data execution specialist. "
    "Use when the query requires: (1) executing actions via registered integrations "
    "(sending messages, reading data, calling APIs, interacting with external services), "
    "or (2) real-time readings, live KPIs, or current system state from connected tools. "
    "Has access to: mcp_execute (live API/tool execution via registered integrations). "
    "ALWAYS delegate here for live data retrieval or any action on a connected integration. "
    "Do NOT use for: document search (use rag-agent), historical trends (use historical-agent), "
    "or database SQL queries (use db_analyst-agent)."
)


def build_mcp_system_prompt(tool_catalog: str = "") -> str:
    """Build MCP agent system prompt with dynamic tool catalog."""
    return load_prompt("subagent_mcp", tool_catalog=tool_catalog)


MCP_AGENT_SYSTEM_PROMPT = build_mcp_system_prompt()


# ── Historical Agent ──
HISTORICAL_AGENT_DESCRIPTION = (
    "Industrial failure pattern and root cause analysis specialist. "
    "Use when the event requires: identifying known failure patterns, recurring anomaly types, "
    "common root causes for the event domain, or cross-referencing the event against typical "
    "industrial/IT incident patterns from general engineering knowledge. "
    "This agent has NO external tools — it reasons from general domain knowledge. "
    "Do NOT use for: real-time data retrieval (use mcp-agent), document lookups (use rag-agent), "
    "or database queries (use db_analyst-agent). "
    "Do NOT use if the question is purely about current/live values — use mcp-agent for that."
)

HISTORICAL_AGENT_SYSTEM_PROMPT = load_prompt("subagent_historical")


# ── DB Analyst Agent ──
DB_ANALYST_AGENT_DESCRIPTION = (
    "Database query, reporting, and data analysis specialist. "
    "Use ONLY when the user asks to query, analyze, aggregate, explore, or report data from their connected databases (e.g. counting, averaging, listing records, finding top/max values). "
    "Has access to: list_db_connections, retrieve_relevant_schema, db_schema, execute_data_query, db_query, and explain_sql_query. "
    "ALWAYS delegate here for questions about data, tables, metrics, database analytics, or reporting. "
    "Do NOT use for: document search (use rag-agent), live API calls to non-DB services (use mcp-agent)."
)


def build_db_analyst_system_prompt(db_catalog: str = "") -> str:
    return load_prompt("subagent_db_analyst", db_catalog=db_catalog)


DB_ANALYST_AGENT_SYSTEM_PROMPT = build_db_analyst_system_prompt()



