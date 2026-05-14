"""Orchestrator system prompt — loaded from Jinja2 template.

Replaces the monolithic string with a renderable .md template.
"""

from src.ia.prompts.loader import load_prompt


def build_orchestrator_prompt(
    subagent_descriptions: str,
    has_rag: bool = True,
    has_mcp: bool = True,
) -> str:
    """Build the orchestrator system prompt from template."""
    # Build routing rules based on available data agents
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
            '<user_query>Dame la información de los manuales técnicos sobre calderas</user_query>\n'
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
        routing_examples += (
            '<example>\n'
            '<user_query>¿Qué dice el manual sobre calderas?</user_query>\n'
            '<reasoning>Needs document search, but rag-agent is disabled.</reasoning>\n'
            '<correct_action>Direct answer: El módulo de búsqueda documental está desactivado. No puedo consultar manuales ni SOPs.</correct_action>\n'
            '</example>\n\n'
        )

    if has_mcp:
        routing_rules += (
            "[IF] Query needs live sensor data, real-time readings, API data, or equipment status\n"
            "     → [DELEGATE] to mcp-agent via task()\n"
            "     → The mcp-agent executes live API calls for sensor values.\n\n"
        )
        routing_examples += (
            '<example>\n'
            '<user_query>¿Cuál es la presión actual de la caldera 3?</user_query>\n'
            '<reasoning>Needs live sensor reading → delegate to mcp-agent.</reasoning>\n'
            '<correct_action>task() → mcp-agent</correct_action>\n'
            '</example>\n\n'
        )
    else:
        routing_rules += (
            "[IF] Query requires live sensor data, real-time readings, or API calls\n"
            "     → [ANSWER DIRECTLY] Explain that the Live Data module is currently DISABLED.\n"
            "     → Do NOT attempt to guess, hallucinate or use any tools for this.\n\n"
        )
        routing_examples += (
            '<example>\n'
            '<user_query>¿Cuál es la presión actual de la caldera 3?</user_query>\n'
            '<reasoning>Needs live sensor data, but mcp-agent is disabled.</reasoning>\n'
            '<correct_action>Direct answer: El módulo de datos en tiempo real está desactivado. No puedo proveer lecturas actuales.</correct_action>\n'
            '</example>\n\n'
        )

    # RAG + MCP parallel example
    if has_rag and has_mcp:
        routing_examples += (
            '<example>\n'
            '<user_query>¿Cuál es la presión actual de la caldera 3 y qué dice el manual sobre límites seguros?</user_query>\n'
            '<reasoning>Needs BOTH live sensor data AND document lookup → delegate to mcp-agent AND rag-agent in parallel.</reasoning>\n'
            '<correct_action>task() → mcp-agent (for pressure reading) + task() → rag-agent (for manual limits)</correct_action>\n'
            '</example>\n\n'
        )

    routing_rules += (
        "[IF] Query is about historical trends, past performance, time-series, comparisons\n"
        "     → [DELEGATE] to historical-agent via task()\n"
        "     → historical-agent reasons from fine-tuned weights, no tools needed\n\n"
        "[IF] Query requires web navigation, screenshots, UI interaction, form filling\n"
        "     → [DELEGATE] to vl-agent via task()\n"
        "     → vl-agent has browser tools\n\n"
        "[IF] Query is pure reasoning (math, unit conversions, general explanations)\n"
        "     → [ANSWER] directly without any tools or delegation\n\n"
        "[IF] Query spans multiple domains (historical + live + documents)\n"
        "     → [DELEGATE] to MULTIPLE sub-agents in parallel, then synthesize"
    )

    routing_examples += (
        '<example>\n'
        '<user_query>¿Cuál fue el promedio de eficiencia en Q2 2023 comparado con Q2 2024?</user_query>\n'
        '<reasoning>Historical time-series comparison → delegate to historical-agent.</reasoning>\n'
        '<correct_action>task() → historical-agent</correct_action>\n'
        '</example>\n\n'
        '<example>\n'
        '<user_query>Navigate to the SCADA dashboard and take a screenshot</user_query>\n'
        '<reasoning>Requires browser navigation and screenshots → delegate to vl-agent.</reasoning>\n'
        '<correct_action>task() → vl-agent</correct_action>\n'
        '</example>\n\n'
        '<example>\n'
        '<user_query>Convert 327 PSI to bar</user_query>\n'
        '<reasoning>Simple math, no external data → answer directly.</reasoning>\n'
        '<correct_action>Direct answer: 327 PSI ≈ 22.5 bar</correct_action>\n'
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
