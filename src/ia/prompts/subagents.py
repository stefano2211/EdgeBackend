"""Sub-agent prompts: descriptions + system_prompts for the registry.

System prompts are loaded from Jinja2 templates in templates/.
"""

from src.ia.prompts.loader import load_prompt

# ── RAG Agent ──
RAG_AGENT_DESCRIPTION = (
    "Document search and knowledge retrieval specialist. "
    "Use ONLY when the user query requires searching manuals, SOPs, regulations, "
    "technical specifications, compliance documents, or any written documentation. "
    "Has access to: rag_retrieve (document/knowledge base search). "
    "ALWAYS delegate here for questions about 'what does the manual say', norms, procedures, "
    "or safety limits defined in documentation. "
    "Do NOT use for: live sensor data, real-time API calls, historical trends, or web UI automation."
)

RAG_AGENT_SYSTEM_PROMPT = load_prompt("subagent_rag")


# ── MCP Agent ──
MCP_AGENT_DESCRIPTION = (
    "External integration and live data execution specialist. "
    "Use when the user query requires: (1) executing actions via registered integrations "
    "(send email, read inbox, manage calendar, call APIs, interact with external services like Gmail, Slack, GitHub, Notion, AWS), "
    "or (2) real-time sensor/equipment readings, live KPIs, SCADA data. "
    "Has access to: mcp_execute (live API/tool execution). "
    "ALWAYS delegate here for: sending emails, reading emails, replying, creating drafts, listing labels, "
    "querying live sensors, checking equipment status, or any action on a connected integration. "
    "Do NOT use for: document search (use rag-agent), historical trends (use historical-agent), "
    "or navigating websites visually (use vl-agent)."
)

MCP_AGENT_SYSTEM_PROMPT = load_prompt("subagent_mcp")


# ── Historical Agent ──
HISTORICAL_AGENT_DESCRIPTION = (
    "Historical plant data analysis specialist. "
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
    "Can handle ANY website or web application: Excel Online, Google Sheets, Salesforce, "
    "SAP web portals, SCADA HMI dashboards, ERP systems, social media, or any custom web app. "
    "Do NOT use for sending/reading emails if a Gmail integration (MCP) is available — use mcp-agent instead. "
    "Has access to: browser_navigate, browser_dom, computer. "
    "Do NOT use for: document search (use rag-agent), live sensor API queries (use mcp-agent), "
    "or historical data analysis (use historical-agent). "
    "Do NOT use just because the user mentions a URL — only delegate if UI interaction is needed."
)

VL_AGENT_SYSTEM_PROMPT = load_prompt("subagent_vl")
