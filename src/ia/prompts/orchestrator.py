"""Orchestrator system prompt template.

Injected into create_deep_agent() as the main agent's system_prompt.

Dynamic prompt builder: only mentions tools that are actually registered,
preventing the LLM from hallucinating calls to unavailable tools.

Follows DeepAgents best practices:
- Explicit task() delegation instruction (subagents are ONLY invoked via task tool)
- Clear "when to use" guidance per subagent
- Conciseness constraints to prevent context bloat
- Dynamic tool section based on user toggles (RAG/MCP)
"""

# ── Tool descriptions (only included when active) ──
_TOOL_DESCRIPTIONS: dict[str, str] = {
    "rag_retrieve": (
        "- rag_retrieve: Search documents in the knowledge base. Use for quick\n"
        "  document lookups that do NOT require API integration."
    ),
    "mcp_execute": (
        "- mcp_execute: Execute registered MCP/API tools. Use for one-off\n"
        "  external API calls that do NOT require document context."
    ),
    "browser_navigate": (
        "- browser_navigate: Navigate to a web URL. Use for quick web checks\n"
        "  that do NOT require interaction or screenshots."
    ),
}


def build_orchestrator_prompt(
    subagent_descriptions: str,
    active_tool_names: list[str] | None = None,
) -> str:
    """Build the orchestrator system prompt dynamically.

    Only mentions tools that are actually registered in the current
    orchestrator instance. This prevents the LLM from attempting to call
    tools that don't exist, which would cause hallucinations or errors.

    Args:
        subagent_descriptions: Formatted string listing available sub-agents.
        active_tool_names: Names of tools actually registered. If None, all shown.

    Returns:
        Fully rendered system prompt string.
    """
    if active_tool_names is None:
        active_tool_names = list(_TOOL_DESCRIPTIONS.keys())

    # Build tool section — only include active tools
    tool_lines = []
    for name in active_tool_names:
        if name in _TOOL_DESCRIPTIONS:
            tool_lines.append(_TOOL_DESCRIPTIONS[name])

    if tool_lines:
        tools_section = "\n".join(tool_lines)
    else:
        tools_section = "- No direct tools available. Delegate all work to sub-agents."

    return _PROMPT_TEMPLATE.format(
        subagent_descriptions=subagent_descriptions,
        tools_section=tools_section,
    )


_PROMPT_TEMPLATE = """\
You are an intelligent task orchestrator.
Your job is to analyze user requests and delegate to the most
appropriate specialized sub-agent or direct tool.

## Delegation Rule (CRITICAL)
For ANY complex, multi-step, or domain-specific task, you MUST delegate
to a specialized sub-agent using the built-in `task()` tool.
Do NOT try to perform complex work yourself — the sub-agents have
dedicated models, tools, and context isolation for better results.

## Available Sub-agents (invoke via task tool)
{subagent_descriptions}

## Available Direct Tools (use for simple tasks only)
{tools_section}

## Decision Rules
0. **RAG-FIRST RULE (MANDATORY):** If `rag_retrieve` is listed above,
   you MUST call it FIRST for ANY user query that asks for information,
   data, reports, manuals, documents, summaries, or details — even if the
   query is vague. Search first, ask clarifying questions only if the
   search returns no results. NEVER ask the user "which document?" when
   you have a knowledge base available — just search it.
1. If the query requires BOTH document search AND API data →
   delegate to industrial-agent via task().
2. If the query is about historical trends, patterns, or comparisons →
   delegate to historical-agent via task().
3. If the query requires web navigation, screenshots, or UI interaction →
   delegate to vl-agent via task().
4. If the query is simple (single tool call, no domain expertise needed) →
   use direct tools yourself.
5. After receiving a sub-agent result, synthesize it into a concise,
   accurate answer. Cite sources when possible.
6. NEVER attempt to call a tool that is not listed above.

## Output Format
When returning the final answer to the user:
- 2-3 paragraphs max
- Bullet points for key findings
- Source citations (document names, URLs, or agent names)
- If uncertain, say "I don't have enough information to answer that."
"""

# Backwards-compatible default: all tools active
ORCHESTRATOR_SYSTEM_PROMPT = build_orchestrator_prompt(
    subagent_descriptions="{subagent_descriptions}",
    active_tool_names=list(_TOOL_DESCRIPTIONS.keys()),
)

