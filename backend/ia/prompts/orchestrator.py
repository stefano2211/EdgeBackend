"""Orchestrator system prompt — loaded from Jinja2 template.

Replaces the monolithic string with a renderable .md template.
All routing rules and examples are domain-agnostic.
"""

from backend.ia.prompts.loader import load_prompt


def build_orchestrator_prompt(
    subagent_descriptions: str,
    has_rag: bool = True,
    has_mcp: bool = True,
    tool_catalog_hint: str = "",
) -> str:
    """Build the orchestrator system prompt from template.

    Args:
        subagent_descriptions: Formatted string of available sub-agents.
        has_rag: Whether the RAG sub-agent is available.
        has_mcp: Whether the MCP sub-agent is available.
        tool_catalog_hint: Optional summary of registered MCP tools for routing hints.
    """
    routing_rules = ""
    routing_examples = ""

    if has_rag:
        routing_rules += (
            "[IF] Query needs document search, manuals, SOPs, regulations, or technical specs\n"
            "     → [DELEGATE] to rag-agent via task()\n"
            "     → The rag-agent searches the knowledge base for relevant documents.\n\n"
        )
        routing_examples += (
            '<example>\n'
            '<user_query>Find the documentation about operational limits</user_query>\n'
            '<reasoning>Asks for document content → delegate to rag-agent.</reasoning>\n'
            '<correct_action>task() → rag-agent</correct_action>\n'
            '</example>\n\n'
        )
    else:
        routing_rules += (
            "[IF] Query requires document search, manuals, or regulations\n"
            "     → [ANSWER DIRECTLY] Explain that the Document Knowledge module is currently DISABLED.\n"
            "     → Do NOT attempt to guess, hallucinate or use any tools for this.\n\n"
        )

    if has_mcp:
        mcp_capability_hint = ""
        if tool_catalog_hint:
            mcp_capability_hint = f"\n     → Available integrations: {tool_catalog_hint}\n"

        routing_rules += (
            "[IF] Query needs live data, real-time readings, API calls, external system actions,\n"
            "     OR requires actions on registered integrations (messaging, data queries, etc.)\n"
            "     → [DELEGATE] to mcp-agent via task()\n"
            "     → The mcp-agent executes live API calls and integration actions.\n"
            f"{mcp_capability_hint}"

        )
        routing_examples += (
            '<example>\n'
            '<user_query>Get the current status from the system</user_query>\n'
            '<reasoning>Needs live data reading → delegate to mcp-agent.</reasoning>\n'
            '<correct_action>task() → mcp-agent</correct_action>\n'
            '</example>\n\n'
            '<example>\n'
            '<user_query>Send a message to the team about the update</user_query>\n'
            '<reasoning>Requires action via registered integration → delegate to mcp-agent.</reasoning>\n'
            '<correct_action>task() → mcp-agent</correct_action>\n'
            '</example>\n\n'
        )
    else:
        routing_rules += (
            "[IF] Query requires live data, real-time readings, or API calls\n"
            "     → [ANSWER DIRECTLY] Explain that the Live Data module is currently DISABLED.\n"
            "     → Do NOT attempt to guess, hallucinate or use any tools for this.\n\n"
        )

    # Parallel example when both available
    if has_rag and has_mcp:
        routing_examples += (
            '<example>\n'
            '<user_query>What is the current value and what does the documentation say about its limits?</user_query>\n'
            '<reasoning>Needs BOTH live data AND document lookup → delegate to mcp-agent AND rag-agent in parallel.</reasoning>\n'
            '<correct_action>task() → mcp-agent (for live reading) + task() → rag-agent (for documentation)</correct_action>\n'
            '</example>\n\n'
        )

    routing_rules += (
        "[MANDATORY] If the user asks about data, tables, metrics, measurements, readings,\n"
        "     analytics, or anything related to their connected databases\n"
        "     (e.g., 'how many', 'top 5', 'average', 'compare', 'trends', 'show me',\n"
        "     'what is the value', 'temperature', 'vibration', 'pressure', 'records')\n"
        "     → You MUST delegate to db_analyst-agent via task() as your FIRST action.\n"
        "     → You CANNOT answer data questions from memory — you have NO tools to query data.\n"
        "     → The db_analyst-agent will query the real database and return actual results.\n\n"

        "[IF] Query is pure reasoning (math, unit conversions, general explanations)\n"
        "     → [ANSWER] directly without any tools or delegation\n\n"

        "[MANDATORY] If query spans multiple domains (DB + documents, DB + live data,\n"
        "     documents + live data, or all three)\n"
        "     → dispatch ALL needed sub-agents in a SINGLE response using PARALLEL task() calls.\n"
        "     → NEVER call them sequentially (one, wait, then another).\n"
        "     → After receiving ALL results, synthesize a single coherent answer."
    )

    routing_examples += (
        '<example>\n'
        '<user_query>Cuales son los 5 productos mas vendidos?</user_query>\n'
        '<reasoning>Requires querying the database for sales data → delegate to db_analyst-agent.</reasoning>\n'
        '<correct_action>task() → db_analyst-agent</correct_action>\n'
        '</example>\n\n'

        '<example>\n'
        '<user_query>How many users registered yesterday and what is the trend?</user_query>\n'
        '<reasoning>Natural-language business question about database contents → delegate to db_analyst-agent.</reasoning>\n'
        '<correct_action>task() → db_analyst-agent</correct_action>\n'
        '</example>\n\n'

        '<example>\n'
        '<user_query>Convert 100 km/h to mph</user_query>\n'
        '<reasoning>Simple math, no external data → answer directly.</reasoning>\n'
        '<correct_action>Direct answer: 100 km/h ≈ 62.14 mph</correct_action>\n'
        '</example>'
    )

    return load_prompt(
        "orchestrator",
        subagent_descriptions=subagent_descriptions,
        routing_rules=routing_rules,
        routing_examples=routing_examples,
    )


# Backwards-compatible default
ORCHESTRATOR_SYSTEM_PROMPT = build_orchestrator_prompt(
    subagent_descriptions="{subagent_descriptions}",
)
