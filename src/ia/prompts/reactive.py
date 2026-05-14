"""Reactive Event Processing Prompts — loaded from Jinja2 templates.

Replaces monolithic strings with renderable .md templates.
"""

from typing import List

from src.core.config import settings
from src.ia.prompts.loader import load_prompt


# ═══════════════════════════════════════════════════════════════════════════════
#  PHASE 1 — S2 TRIAGE PROMPT
# ═══════════════════════════════════════════════════════════════════════════════

REACTIVE_S2_TRIAGE_PROMPT = load_prompt("reactive_triage")


# ═══════════════════════════════════════════════════════════════════════════════
#  PHASE 2 — S1 COORDINATOR PROMPT
# ═══════════════════════════════════════════════════════════════════════════════

def build_s1_coordinator_prompt() -> str:
    return load_prompt(
        "reactive_s1_coordinator",
        notification_email=settings.REACTIVE_NOTIFICATION_EMAIL,
    )


REACTIVE_S1_COORDINATOR_PROMPT = build_s1_coordinator_prompt()


# ═══════════════════════════════════════════════════════════════════════════════
#  PHASE 3 — S2 SYNTHESIS PROMPT
# ═══════════════════════════════════════════════════════════════════════════════

def build_reactive_synthesis_prompt(
    subagent_descriptions: str = "",
    system1_analysis: str = "",
    industrial_data: str = "",
    event_context: str = "",
) -> str:
    """Build the System-2 synthesis prompt dynamically."""
    input_sections = ""
    if system1_analysis:
        input_sections += f"<system1_analysis>\n{system1_analysis}\n</system1_analysis>\n\n"
    if industrial_data:
        input_sections += f"<industrial_data>\n{industrial_data}\n</industrial_data>\n\n"

    return load_prompt(
        "reactive_synthesis",
        input_sections=input_sections,
        event_context=event_context,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  S2 AUTONOMOUS ORCHESTRATOR PROMPT (unified entry point)
# ═══════════════════════════════════════════════════════════════════════════════

def build_reactive_s2_orchestrator_prompt(
    has_industrial: bool = True,
) -> str:
    """Build the S2 autonomous orchestrator prompt — unified entry point."""
    subagent_lines = []
    if has_industrial:
        industrial_delegation_rules = (
            "[DELEGAR a industrial-agent] cuando:\n"
            "  - Se necesitan lecturas actuales de sensores (MCP)\n"
            "  - Se deben referenciar SOPs, procedimientos de emergencia o documentación (RAG)\n"
            "  - El triage indica needs_industrial=true (tratar como pista fuerte)\n"
        )
        subagent_lines.append(
            '- task("industrial-agent", ...) → Especialista en datos industriales en tiempo real. '
            "Usa MCP para lecturas actuales de sensores/KPIs y RAG para SOPs y manuales técnicos. "
            "DEBES INVOCARLO SIEMPRE para obtener la telemetría actual y procedimientos estándar."
        )
    else:
        industrial_delegation_rules = (
            "NOTA CRÍTICA: El sub-agente industrial (sensores/documentación) está DESACTIVADO.\n"
            "No puedes pedir lecturas actuales ni SOPs. Si el usuario las pide o el triage las sugiere,\n"
            "debes informar en tu plan que no tienes acceso a esos datos y proceder con precaución.\n"
        )

    subagent_lines.append(
        '- task("historical-agent", ...) → Especialista en diagnóstico histórico. '
        "Identifica precedentes, patrones de falla recurrentes y correlaciones con incidentes pasados. "
        "Usa pesos fine-tuned (LoRA), no necesita herramientas externas. Siempre es rápido y barato de invocar."
    )

    subagent_lines.append(
        '- task("vl-agent", ...) → Agente autónomo de Computer Use (Observe-Think-Act). '
        "Puede navegar cualquier GUI (navegador web, SCADA HMI, SAP/ERP, email, dashboards), "
        "leer valores, llenar formularios, hacer clicks, enviar emails. "
        "Es el ÚNICO agente que puede interactuar con pantallas y sitios web."
    )

    subagents_section = "\n".join(subagent_lines)

    return load_prompt(
        "reactive_orchestrator",
        subagents_section=subagents_section,
        industrial_delegation_rules=industrial_delegation_rules,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  LEGACY BACKWARD COMPATIBILITY
# ═══════════════════════════════════════════════════════════════════════════════

_REACTIVE_SUBAGENT_DESCRIPTIONS = {
    "industrial-agent": (
        "Real-time SCADA/PLC sensor readings, live equipment KPIs, current status of "
        "machinery and processes, emergency SOPs, maintenance manuals, compliance "
        "documents, and regulatory references (RAG knowledge base)."
    ),
    "historical-agent": (
        "Historical industrial data: past sensor trends, "
        "equipment failure history, incident reports, long-term operational KPIs, "
        "seasonal patterns, and production baselines. "
        "Knowledge baked into fine-tuned weights — does NOT use external tools."
    ),
    "vl-agent": (
        "Autonomous Computer Use agent implementing the Observe-Think-Act loop. "
        "Capabilities: open any GUI application (web browser, SCADA HMI, SAP/ERP, "
        "email client, Excel Online, dashboards), navigate screens step by step, "
        "read values, fill forms, click buttons, send emails, update records. "
        "Pass a single, precise, self-contained instruction. "
        "This is the ONLY agent that can interact with screens and websites."
    ),
}

_UNAVAILABLE_MSG = "(NOT AVAILABLE — do not use)"


def build_reactive_orchestrator_prompt(available_subagents: List[str]) -> str:
    """Build the legacy Reactive Orchestrator system prompt.

    DEPRECATED: Use build_reactive_synthesis_prompt for new reactive pipeline.
    Kept for backward compatibility with existing tests/calls.
    """
    available_set = set(available_subagents)
    lines = []
    for name, desc in _REACTIVE_SUBAGENT_DESCRIPTIONS.items():
        if name in available_set:
            lines.append(f'- subagent_type="{name}" [AVAILABLE] → {desc}')
        else:
            lines.append(f'- subagent_type="{name}" {_UNAVAILABLE_MSG}')

    available_subagents_section = "\n".join(lines) if lines else "None registered."
    return load_prompt(
        "reactive_synthesis",
        input_sections=f"<available_subagents>\n{available_subagents_section}\n</available_subagents>\n\n",
        event_context="Event context provided at runtime.",
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  S1 COORDINATOR DESCRIPTION (for subagent registry)
# ═══════════════════════════════════════════════════════════════════════════════

S1_COORDINATOR_DESCRIPTION = (
    "System-1 Fast Intuition Coordinator. "
    "Delegates in parallel to historical-agent (pattern matching >6 months) "
    "and vl-agent (visual verification + web automation). "
    "This coordinator is RESPONSIBLE for sending anomaly reports via Gmail "
    "and performing visual verification of dashboards. "
    "Use ALWAYS when an alarm or problem is detected to get fast patterns and automated reporting."
)


# ═══════════════════════════════════════════════════════════════════════════════
#  REACTIVE INDUSTRIAL EXPERT — Phase 2b (used by Industrial-Agent directly)
# ═══════════════════════════════════════════════════════════════════════════════

REACTIVE_INDUSTRIAL_PROMPT = load_prompt("subagent_industrial")


# ═══════════════════════════════════════════════════════════════════════════════
#  REACTIVE HISTORICAL EXPERT — used by Historical-Agent (S1 sub-specialist)
# ═══════════════════════════════════════════════════════════════════════════════

REACTIVE_HISTORICAL_PROMPT = load_prompt("subagent_historical")
