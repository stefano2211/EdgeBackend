"""Orchestrator system prompt — loaded from Jinja2 template.

Replaces the monolithic string with a renderable .md template.
"""

from src.ia.prompts.loader import load_prompt


def build_orchestrator_prompt(
    subagent_descriptions: str,
    has_industrial: bool = True,
) -> str:
    """Build the orchestrator system prompt from template."""
    if has_industrial:
        routing_rules = (
            "[IF] Query needs document search, live API data, sensor values, or BOTH\n"
            "     → [DELEGATE] to industrial-agent via task()\n"
            "     → The industrial-agent has the tools to search manuals and APIs.\n\n"
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
        routing_examples = (
            '<example>\n'
            '<user_query>Dame la información de los manuales técnicos sobre calderas</user_query>\n'
            '<reasoning>Asks for document content → delegate to industrial-agent.</reasoning>\n'
            '<correct_action>task() → industrial-agent</correct_action>\n'
            '</example>\n\n'
            '<example>\n'
            '<user_query>¿Cuál es la presión actual de la caldera 3 y qué dice el manual sobre límites seguros?</user_query>\n'
            '<reasoning>Needs BOTH live sensor data AND document lookup → delegate to industrial-agent.</reasoning>\n'
            '<correct_action>task() → industrial-agent</correct_action>\n'
            '</example>'
        )
    else:
        routing_rules = (
            "[IF] Query requires live data, sensors, or document search\n"
            "     → [ANSWER DIRECTLY] Explain that the Industrial Knowledge module is currently DISABLED.\n"
            "     → Do NOT attempt to guess, hallucinate or use any tools for this.\n\n"
            "[IF] Query is about historical trends, past performance, time-series, comparisons\n"
            "     → [DELEGATE] to historical-agent via task()\n\n"
            "[IF] Query requires web navigation, screenshots, UI interaction, form filling\n"
            "     → [DELEGATE] to vl-agent via task()\n\n"
            "[IF] Query is pure reasoning (math, unit conversions, general explanations)\n"
            "     → [ANSWER] directly without any tools or delegation"
        )
        routing_examples = (
            '<example>\n'
            '<user_query>¿Cuál es la presión actual de la caldera 3?</user_query>\n'
            '<reasoning>Needs live sensor data, but industrial-agent is disabled.</reasoning>\n'
            '<correct_action>Direct answer: El módulo de conocimiento industrial y acceso a sensores en tiempo real está desactivado. No puedo proveer lecturas actuales.</correct_action>\n'
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
