"""Reactive Event Processing Prompts — loaded from Jinja2 templates.

Replaces monolithic strings with renderable .md templates.
All prompts are now domain-agnostic.
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
    domain_data: str = "",
    event_context: str = "",
) -> str:
    """Build the System-2 synthesis prompt dynamically."""
    input_sections = ""
    if system1_analysis:
        input_sections += f"<system1_analysis>\n{system1_analysis}\n</system1_analysis>\n\n"
    if domain_data:
        input_sections += f"<domain_data>\n{domain_data}\n</domain_data>\n\n"

    return load_prompt(
        "reactive_synthesis",
        input_sections=input_sections,
        event_context=event_context,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  S2 AUTONOMOUS ORCHESTRATOR PROMPT (unified entry point)
# ═══════════════════════════════════════════════════════════════════════════════

def build_reactive_s2_orchestrator_prompt(
    has_rag: bool = True,
    has_mcp: bool = True,
    domain: str = "generic",
) -> str:
    """Build the S2 autonomous orchestrator prompt — unified entry point."""
    subagent_lines = []
    delegation_rules = []

    if has_rag:
        delegation_rules.append(
            "[DELEGAR a rag-agent] cuando:\n"
            "  - Se necesitan procedimientos, manuales, documentación o normativas.\n"
            "  - El evento menciona políticas, regulaciones o límites de seguridad.\n"
            "  - El triage indica que se necesita contexto documental.\n"
        )
        subagent_lines.append(
            '- task("rag-agent", ...) → Especialista en búsqueda documental. '
            "Busca en manuales, procedimientos, normas y documentación técnica usando RAG. "
            "Usa filtros precisos y devuelve citas completas con texto extraído."
        )
    else:
        delegation_rules.append(
            "NOTA CRÍTICA: El sub-agente rag-agent (búsqueda documental) está DESACTIVADO.\n"
            "No puedes consultar manuales ni procedimientos. Si el evento lo requiere, indica la limitación.\n"
        )

    if has_mcp:
        delegation_rules.append(
            "[DELEGAR a mcp-agent] cuando:\n"
            "  - Se necesitan lecturas actuales de métricas, estado de recursos, o datos en tiempo real.\n"
            "  - Se requiere el estado en tiempo real de sistemas o servicios.\n"
            "  - El triage indica needs_realtime_data=true (tratar como pista fuerte).\n"
        )
        subagent_lines.append(
            '- task("mcp-agent", ...) → Especialista en datos en tiempo real. '
            "Ejecuta APIs y consulta sistemas externos usando MCP. "
            "Usa filtros específicos por recurso y métrica. Devuelve TODOS los registros."
        )
    else:
        delegation_rules.append(
            "NOTA CRÍTICA: El sub-agente mcp-agent (datos en tiempo real) está DESACTIVADO.\n"
            "No puedes obtener lecturas de métricas ni estados de sistemas. Si el evento lo requiere, indica la limitación.\n"
        )

    subagent_lines.append(
        '- task("historical-agent", ...) → Especialista en diagnóstico histórico. '
        "Identifica precedentes, patrones de falla recurrentes y correlaciones con incidentes pasados. "
        "Usa pesos fine-tuned (LoRA), no necesita herramientas externas. Siempre es rápido y barato de invocar."
    )

    subagent_lines.append(
        '- task("vl-agent", ...) → Agente autónomo de Computer Use (Observe-Think-Act). '
        "Puede navegar cualquier GUI (navegador web, dashboards, SAP/ERP, email, interfaces de monitoreo), "
        "leer valores, llenar formularios, hacer clicks. "
        "Es el ÚNICO agente que puede interactuar con pantallas y sitios web."
    )

    subagents_section = "\n".join(subagent_lines)
    data_delegation_rules = "\n".join(delegation_rules)

    return load_prompt(
        "reactive_orchestrator",
        subagents_section=subagents_section,
        domain_delegation_rules=data_delegation_rules,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  LEGACY BACKWARD COMPATIBILITY
# ═══════════════════════════════════════════════════════════════════════════════

_LEGACY_SUBAGENT_DESCRIPTIONS = {
    "rag-agent": (
        "Document search and knowledge retrieval specialist. "
        "Searches manuals, procedures, regulations, technical specs, and compliance documents. "
        "Has access to rag_retrieve for RAG knowledge base queries."
    ),
    "mcp-agent": (
        "Live data and API execution specialist. "
        "Fetches real-time metrics, resource status, and system state. "
        "Has access to mcp_execute for live API/tool calls."
    ),
    "historical-agent": (
        "Historical data pattern matcher. "
        "Identifies precedents, recurring failure patterns, and correlations with past incidents. "
        "Knowledge baked into fine-tuned weights — does NOT use external tools."
    ),
    "vl-agent": (
        "Autonomous Computer Use agent implementing the Observe-Think-Act loop. "
        "Capabilities: open any GUI application (web browser, dashboards, SAP/ERP, "
        "email client, Excel Online), navigate screens step by step, "
        "read values, fill forms, click buttons. "
        "Pass a single, precise, self-contained instruction. "
        "This is the ONLY agent that can interact with screens and websites."
    ),
}

_UNAVAILABLE_MSG = "(NOT AVAILABLE — do not use)"


def build_reactive_orchestrator_prompt(available_subagents: List[str]) -> str:
    """Build the legacy Reactive Orchestrator system prompt.

    DEPRECATED: Use build_reactive_s2_orchestrator_prompt for new reactive pipeline.
    Kept for backward compatibility with existing tests/calls.
    """
    available_set = set(available_subagents)
    lines = []
    for name, desc in _LEGACY_SUBAGENT_DESCRIPTIONS.items():
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
    "Performs visual verification of dashboards and web interfaces when required. "
    "Use ALWAYS when an alarm or problem is detected to get fast patterns and visual confirmation."
)


# ═══════════════════════════════════════════════════════════════════════════════
#  REACTIVE RAG / MCP PROMPTS — loaded from templates
# ═══════════════════════════════════════════════════════════════════════════════

REACTIVE_RAG_PROMPT = load_prompt("subagent_rag")
REACTIVE_MCP_PROMPT = load_prompt("subagent_mcp")
REACTIVE_HISTORICAL_PROMPT = load_prompt("subagent_historical")
