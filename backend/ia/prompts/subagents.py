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
    "or navigating websites visually (use vl-agent)."
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
    "or web automation (use vl-agent). "
    "Do NOT use if the question is about current/live values — use mcp-agent for that."
)

HISTORICAL_AGENT_SYSTEM_PROMPT = load_prompt("subagent_historical")


# ── VL Agent ──
VL_AGENT_DESCRIPTION = (
    "Vision-language web automation and browser interaction specialist. "
    "Use ONLY when the task requires navigating websites, interacting with web UIs, "
    "taking screenshots, filling forms, clicking buttons, visual verification, or reading web page content. "
    "Can handle ANY website or web application. "
    "Do NOT use for data retrieval if an integration (MCP) is available — use mcp-agent instead. "
    "Has access to: browser_navigate, browser_dom, computer. "
    "Do NOT use for: document search (use rag-agent), live data API queries (use mcp-agent), "
    "or historical data analysis (use historical-agent). "
    "Do NOT use just because the user mentions a URL — only delegate if UI interaction is needed."
)

VL_AGENT_SYSTEM_PROMPT = load_prompt("subagent_vl")
