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
    "Use when the user query requires: (1) executing actions via registered integrations "
    "(e.g., sending messages, reading data, managing resources, calling APIs, interacting with external services), "
    "or (2) real-time readings, live KPIs, or current system state. "
    "Has access to: mcp_execute (live API/tool execution via registered integrations). "
    "ALWAYS delegate here for any action on a connected integration or live data retrieval. "
    "Do NOT use for: document search (use rag-agent), historical trends (use historical-agent), "

)


def build_mcp_system_prompt(tool_catalog: str = "", has_rest_tools: bool = False) -> str:
    """Build MCP agent system prompt with dynamic tool catalog."""
    return load_prompt("subagent_mcp", tool_catalog=tool_catalog, has_rest_tools=has_rest_tools)


MCP_AGENT_SYSTEM_PROMPT = build_mcp_system_prompt()


# ── Historical Agent ──
HISTORICAL_AGENT_DESCRIPTION = (
    "Historical data analysis specialist. "
    "Use ONLY when the user asks about trends, patterns, time-series comparisons, "
    "quarter-over-quarter or year-over-year analysis, past failure patterns, "
    "or historical performance KPIs from more than 6 months ago. "
    "This agent reasons purely from fine-tuned training weights — it has NO external tools. "
    "Do NOT use for: real-time data retrieval (use mcp-agent), document lookups (use rag-agent), "

    "Do NOT use if the question is about current/live values — use mcp-agent for that."
)

HISTORICAL_AGENT_SYSTEM_PROMPT = load_prompt("subagent_historical")


# ── DB Agent ──
DB_AGENT_DESCRIPTION = (
    "Database query and structured data retrieval specialist. "
    "Use ONLY when the user asks to query, analyze, or explore data from their connected databases. "
    "Has access to: db_schema (discover tables/columns) and db_query (execute read-only SQL). "
    "ALWAYS delegate here for questions about data, tables, metrics, analytics, or reporting. "
    "Do NOT use for: document search (rag-agent), live API calls (mcp-agent), or historical reasoning (historical-agent)."
)


def build_db_system_prompt(db_catalog: str = "") -> str:
    return load_prompt("subagent_db", db_catalog=db_catalog)


DB_AGENT_SYSTEM_PROMPT = build_db_system_prompt()


# ── Data Analyst Agent ──
DATA_ANALYST_AGENT_DESCRIPTION = (
    "Natural-language data analyst specialist. "
    "Use when the user asks questions about their connected databases in plain language. "
    "Converts natural-language questions into SQL, executes them with auto-correction, "
    "and returns interpreted insights in Spanish. "
    "Has access to: list_db_connections, retrieve_relevant_schema, execute_data_query, explain_sql_query. "
    "ALWAYS delegate here for: data exploration, business questions about DB contents, "
    "metrics, reporting, aggregations, filtering, or any question that starts with 'how many', 'top', 'average', 'list', etc. "
    "Do NOT use for: document search (rag-agent), live API calls (mcp-agent), historical reasoning without DB (historical-agent)."
)


def build_data_analyst_system_prompt() -> str:
    return load_prompt("subagent_data_analyst")


DATA_ANALYST_AGENT_SYSTEM_PROMPT = build_data_analyst_system_prompt()



