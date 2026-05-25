"""Pydantic schemas for structured reactive analysis output.

Defines the JSON schema that the LLM must follow when generating
reactive event analysis results. Used with LangChain .with_structured_output()
or injected into prompts as JSON schema hints.
"""

from pydantic import BaseModel, Field


class ReactiveAnalysisOutput(BaseModel):
    """Structured output for the S2 autonomous reactive orchestrator.

    CRITICAL: All fields except execute_instruction are REQUIRED strings.
    Do NOT nest objects inside any field. Each field must be a single
    string value containing markdown-formatted text.
    """

    analysis: str = Field(
        ...,
        description=(
            "A SINGLE STRING containing the detailed root cause analysis. "
            "Write this as plain text / markdown, NOT as a JSON object. "
            "Cite evidence from sub-agents, separate facts from inferences, "
            "evaluate confidence level, and include data limitations. "
            "Example: 'He analizado el evento de pérdida de presión en BombaA...' "
            "Write in Spanish unless the event payload clearly indicates another language."
        ),
    )

    diagnosis: str = Field(
        ...,
        description=(
            "A SINGLE STRING containing the structured diagnosis. "
            "Write this as plain text / markdown with bullet points, NOT as a JSON object. "
            "Format:\n"
            "- **Causa raíz identificada:** [description]\n"
            "- **Evidencia:** [data, historical patterns, document references]\n"
            "- **Nivel de confianza:** [Alto / Medio / Bajo]\n"
            "- **Riesgo inmediato:** [Sí / No + brief description]\n"
            "- **Detección de falso positivo:** [Descartado / Sospechoso + justification]\n"
            "Example: '- **Causa raíz identificada:** Falla mecánica en sello...' "
            "Write in Spanish unless the event payload clearly indicates another language."
        ),
    )

    plan: str = Field(
        ...,
        description=(
            "A SINGLE STRING containing the step-by-step remediation plan. "
            "Write this as plain text / markdown with numbered list, NOT as a JSON object. "
            "Format:\n"
            "1. **[Immediate action]:** [description] — Prioridad: Alta\n"
            "2. **[Follow-up action]:** [description] — Prioridad: Media\n"
            "3. **[Verification]:** [how to confirm success] — Prioridad: Alta\n"
            "Include responsible role/agent and estimated time. "
            "Example: '1. **[Acción inmediata]:** Detener Motor1...' "
            "Write in Spanish unless the event payload clearly indicates another language."
        ),
    )

    execute_instruction: str | None = Field(
        default=None,
        description=(
            "A SINGLE STRING containing ONE precise paragraph for autonomous execution. "
            "Write this as plain text, NOT as a JSON object. "
            "ONLY include when confidence is >= MEDIUM AND the plan requires external action. "
            "Specify starting point, sequence of actions, and success criteria. "
            "Write in Spanish unless the event payload clearly indicates another language."
        ),
    )
