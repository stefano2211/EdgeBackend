"""Reactive event pipeline — Aura AI.

Architecture (2-phase):
  Phase 1 — S2-Triage:      routing decision (fast LLM call, JSON)
  Phase 2 — S2-Autonomous:  autonomous orchestrator delegates to rag-agent, mcp-agent
                             and historical-agent via task() (flat hierarchy)

SOLID:
  - SRP: Each phase is a private method.
  - OCP: New specialists can be added without changing the pipeline.
  - DIP: Depends on ChatOrchestrator and EventBroadcastManager abstractions.
"""

import asyncio
import json
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logging import logging
from backend.ia.llm_client import get_llm_client
from backend.ia.orchestrator_factory import create_reactive_orchestrator
from backend.ia.prompts.reactive import (
    REACTIVE_S2_TRIAGE_PROMPT,
)
from backend.ia.schemas.reactive import ReactiveAnalysisOutput
from backend.persistencia.models.event import Event
from backend.services.event_broadcast import EventBroadcastManager
from backend.services.reactive_config_service import ReactiveConfigService

logger = logging.getLogger(__name__)


class ReactiveOrchestrator:
    """Orchestrates reactive event analysis and execution via 3-phase pipeline."""

    def __init__(
        self,
        broadcaster: EventBroadcastManager,
    ) -> None:
        self._broadcaster = broadcaster

    # ═══════════════════════════════════════════════════════════════════════════
    #  PUBLIC API
    # ═══════════════════════════════════════════════════════════════════════════

    async def analyze(self, event: Event, session: AsyncSession) -> None:
        """Run the 2-phase reactive analysis pipeline.

        Phase 1 — S2 Triage: fast LLM call producing routing hints (JSON).
            Phase 2 — S2 Autonomous: DeepAgents orchestrator with rag-agent, mcp-agent
                  and historical-agent as direct sub-agents. S2 decides which
                  to invoke via task() and synthesizes the results into structured JSON.
        """
        # Transition to analyzing immediately so correlation engine can filter it
        event.status = "analyzing"
        await session.commit()
        await self._refresh_and_broadcast(event, session)

        event_query = self._build_event_query(event)

        # Load user's reactive configuration
        config_service = ReactiveConfigService(session)
        config_res = await config_service.get_enabled_resources(event.triggered_by_user_id)
        enabled_tool_ids = config_res["tool_ids"]
        enabled_kb_ids = config_res["kb_ids"]
        enabled_kb_names = config_res["kb_names"]
        enabled_tool_names = config_res["tool_names"]

        # Resolve dynamic tool schemas for prompt injection
        tool_schemas = await self._resolve_tool_schemas(session, event.triggered_by_user_id)

        if not tool_schemas and not enabled_tool_ids:
            await self._emit_log(
                event.id,
                "WARNING: 0 reactive tools found for this user. "
                "Check that the integration has 'available_in_reactive=true' "
                "AND credentials were submitted while reactive was enabled. "
                "Use POST /integrations/instances/{id}/sync to force re-registration.",
                level="warn",
            )

        await self._emit_log(event.id, "Phase 0: Pipeline started", level="info")
        await self._emit_log(
            event.id,
            f"Config: {len(enabled_tool_ids)} tools, {len(enabled_kb_ids)} KBs enabled, "
            f"{len(tool_schemas)} tool schemas resolved",
            level="info",
        )

        try:
            # ── Phase 1: S2-Triage (fast routing hints) ──
            await self._emit_log(event.id, "Phase 1: S2-Triage starting", level="info")
            triage = await self._run_s2_triage(event_query)
            await self._emit("triage_result", event.id, {"triage": triage})
            await self._emit_log(
                event.id,
                f"Phase 1: Triage → urgency={triage.get('urgency')} "
                f"needs_historical={triage.get('needs_historical')} "
                f"needs_realtime={triage.get('needs_realtime_data')}",
                level="info",
            )

            # ── Phase 2: S2 Autonomous Orchestrator ──
            # S2 receives event + triage hints and autonomously decides which
            # sub-agents to invoke via task(), then synthesizes all results
            # into a structured ReactiveAnalysisOutput JSON object.
            await self._emit_log(event.id, "Phase 2: S2 Autonomous Orchestrator starting", level="info")
            output = await self._run_s2_autonomous(
                event=event,
                event_query=event_query,
                triage=triage,
                enabled_kb_ids=[str(k) for k in enabled_kb_ids],
                enabled_kb_names=enabled_kb_names,
                enabled_tool_names=enabled_tool_names,
                tool_schemas=tool_schemas,
            )

            if output is None:
                raise RuntimeError("El orquestador no pudo generar un plan (posible fallo interno del agente o timeout).")

            # Store structured fields separately
            if output.analysis:
                event.agent_analysis = output.analysis
                await self._emit("system2_result", event.id, {"result": output.analysis})
                await self._emit_log(event.id, "Phase 2: S2 analysis completed", level="info")

            if output.diagnosis:
                event.agent_diagnosis = output.diagnosis
                await self._emit("diagnosis_result", event.id, {"diagnosis": output.diagnosis})
                await self._emit_log(event.id, "Phase 2: Diagnosis generated", level="info")

            if output.plan:
                event.agent_plan = output.plan
                await self._emit("planner_result", event.id, {"plan": output.plan})
                await self._emit_log(event.id, "Phase 2: Remediation plan generated", level="info")


            # Transition directly to completed (no execution phase)
            event.status = "completed"
            event.resolved_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await session.commit()
            await self._refresh_and_broadcast(event, session)
            await self._emit_log(event.id, "Analysis complete — event resolved", level="info")

            # ── Mandatory notification: analysis complete ──
            from backend.services.notification_service import NotificationService
            ns = NotificationService(session)
            try:
                await ns.notify_analysis_complete(event)
                await self._emit_log(event.id, "Notification sent: analysis complete", level="info")
            except Exception as notify_exc:
                logger.warning("Failed to send analysis notification: %s", notify_exc)
                await self._emit_log(event.id, f"Notification failed: {notify_exc}", level="warn")

        except Exception as exc:
            logger.exception("Analysis pipeline failed for event %s", event.id)
            await self._emit_log(event.id, f"Pipeline error: {exc}", level="error")
            event.status = "failed"
            await session.commit()
            await self._refresh_and_broadcast(event, session)

    async def execute(self, event: Event, session: AsyncSession) -> None:
        """Remediation execution phase. Transitions event from executing to completed."""
        await self._emit_log(event.id, "Remediation execution started", level="info")
        event.status = "completed"
        event.resolved_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await session.commit()
        await self._refresh_and_broadcast(event, session)
        await self._emit_log(event.id, "Execution complete — event resolved", level="info")


    # ═══════════════════════════════════════════════════════════════════════════
    #  PHASE 1 — S2 TRIAGE
    # ═══════════════════════════════════════════════════════════════════════════

    async def _run_s2_triage(self, event_query: str) -> dict:
        """Phase 1: fast routing decision via direct LLM call."""
        client = get_llm_client()
        prompt = REACTIVE_S2_TRIAGE_PROMPT + f"\n\n{event_query}"

        response = await client.chat_completion(
            messages=[
                {"role": "system", "content": "You are the Triage Director. Output only JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=300,
            stream=False,
        )

        raw = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        # Extract JSON from possible markdown fences
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("\n", 1)[0]
        cleaned = cleaned.strip()

        try:
            triage = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("Triage JSON parse failed, using defaults. Raw: %s", raw[:200])
            triage = {
                "event_type": "general",
                "urgency": "medium",
                "needs_historical": True,
                "needs_realtime_data": True,
                "needs_visual_verification": False,
                "justification": "Parse error — defaulting to full analysis.",
            }

        # Ensure defaults
        triage.setdefault("needs_historical", True)
        triage.setdefault("needs_realtime_data", True)
        triage.setdefault("needs_visual_verification", False)
        return triage

    # ═══════════════════════════════════════════════════════════════════════════
    #  PHASE 2 — S2 AUTONOMOUS ORCHESTRATOR
    # ═══════════════════════════════════════════════════════════════════════════

    async def _run_s2_autonomous(
        self,
        event: Event,
        event_query: str,
        triage: dict,
        enabled_kb_ids: list[str],
        enabled_kb_names: list[str],
        enabled_tool_names: list[str],
        tool_schemas: list[dict] | None = None,
    ) -> ReactiveAnalysisOutput | None:
        """Phase 2: S2 autonomous orchestrator.

        Returns a parsed ReactiveAnalysisOutput with structured analysis,
        diagnosis, plan and optional execute_instruction.
        """
        orchestrator = create_reactive_orchestrator(
            knowledge_base_ids=enabled_kb_ids or None,
            enable_knowledge=bool(enabled_kb_ids),
            enable_mcp=bool(enabled_tool_names),
            enabled_tool_names=enabled_tool_names,
            domain=event.domain or "generic",
            tool_schemas=tool_schemas,
            kb_names=enabled_kb_names,
            user_id=event.triggered_by_user_id,
        )


        # Pass triage hints + event as the user message so S2 can make
        # an informed delegation decision without being hardcoded to follow it.
        triage_str = json.dumps(triage, ensure_ascii=False, indent=2)
        user_message = (
            f"<triage_hints>\n{triage_str}\n</triage_hints>\n\n"
            f"<event>\n{event_query}\n</event>\n\n"
            "Analiza este evento industrial. "
            "Delega a los sub-agentes necesarios via task() — máximo 2 rondas de delegación en total. "
            "Cada sub-agente debe hacer UNA sola llamada a su herramienta con los parámetros más amplios posibles "
            "(no llames la misma herramienta varias veces variando un solo parámetro). "
            "Cuando hayas recopilado los resultados, sintetiza INMEDIATAMENTE en el JSON requerido. "
            "NO agregues texto fuera del JSON."
        )

        thread_id = f"event-{event.id}-s2"
        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": 40,  # hard cap: prevents infinite tool-call loops
        }
        messages = [{"role": "user", "content": user_message}]

        try:
            result = await orchestrator.ainvoke(
                {"messages": messages},
                config=config,
            )
            msgs = result.get("messages", [])

            # Emit sub-agent results so the frontend panels are populated
            for i, msg in enumerate(msgs):
                if getattr(msg, "type", "") == "tool":
                    agent_name = msg.name
                    # If DeepAgents uses a unified 'task' tool, find the actual agent name from the AIMessage
                    if msg.name == "task":
                        for prev_msg in reversed(msgs[:i]):
                            if getattr(prev_msg, "type", "") == "ai" and hasattr(prev_msg, "tool_calls"):
                                for tc in prev_msg.tool_calls:
                                    if tc.get("id") == msg.tool_call_id:
                                        tc_args = tc.get("args", {})
                                        # Handle string args (JSON) from some providers
                                        if isinstance(tc_args, str):
                                            try:
                                                tc_args = json.loads(tc_args)
                                            except (json.JSONDecodeError, TypeError):
                                                tc_args = {}
                                        agent_name = (
                                            tc_args.get("subagent_type")
                                            or tc_args.get("agent")
                                            or "task"
                                        )
                                        break

                    if agent_name == "rag-agent":
                        await self._emit("rag_result", event.id, {"result": str(msg.content)})
                    elif agent_name == "mcp-agent":
                        await self._emit("mcp_result", event.id, {"result": str(msg.content)})
                    elif agent_name == "historical-agent":
                        await self._emit("historical_result", event.id, {"result": str(msg.content)})
                        await self._emit_log(event.id, "Historical analysis received", level="info")
                        # Note: historical-agent result is internal; we no longer overwrite
                        # the orchestrator's final analysis with it.

            # Parse the final message as structured JSON output
            if not msgs:
                logger.warning("S2 autonomous orchestrator returned no messages")
                return None

            last_content = msgs[-1].content
            if not last_content:
                logger.warning("S2 autonomous orchestrator returned empty final message")
                return None

            # The content may be a string containing JSON, or already parsed (LangChain structured output)
            raw_text = str(last_content).strip()

            # Remove markdown fences if present
            if raw_text.startswith("```"):
                # Strip opening fence line
                lines = raw_text.splitlines()
                if lines[0].strip().startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                raw_text = "\n".join(lines).strip()

            try:
                output = ReactiveAnalysisOutput.model_validate_json(raw_text)
            except Exception as parse_exc:
                logger.error(
                    "Failed to parse S2 structured output: %s. Raw (first 500 chars): %s",
                    parse_exc,
                    raw_text[:500],
                )
                return None

            return output

        except Exception as exc:
            logger.warning("S2 autonomous orchestrator failed: %s", exc)
            return None

    # ═══════════════════════════════════════════════════════════════════════════
    #  PRIVATE HELPERS
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_event_query(self, event: Event) -> str:
        payload_str = ""
        if event.body:
            payload_str = json.dumps(event.body, indent=2)

        return (
            f"Event ID: {event.id}\n"
            f"Event Type: {event.event_type}\n"
            f"Domain: {event.domain or 'generic'}\n"
            f"Source: {event.source}\n"
            f"Severity: {event.severity_text} ({event.severity_number})\n"
            f"Title: {event.title}\n"
            f"Description: {event.description}\n"
            f"Payload:\n{payload_str}\n\n"
            "Analyze this event, identify the root cause, and produce a structured remediation plan."
        )

    async def _resolve_tool_schemas(
        self, session: AsyncSession, user_id: int | None
    ) -> list[dict]:
        """Resolve MCP tool schemas from active integrations dynamically."""
        if user_id is None:
            return []
        try:
            from sqlalchemy import select
            from backend.integrations.models import IntegrationInstance
            from backend.integrations.integration_service import IntegrationService

            stmt = select(IntegrationInstance).where(
                IntegrationInstance.user_id == user_id,
                IntegrationInstance.is_enabled.is_(True),
                IntegrationInstance.available_in_reactive.is_(True),
            )
            result = await session.execute(stmt)
            instances = result.scalars().all()

            integration_service = IntegrationService(session)
            all_tools = []
            for instance in instances:
                tools = await integration_service._discover_tools(instance)
                all_tools.extend(tools)
            return all_tools
        except Exception as e:
            logger.warning("Failed to resolve reactive tool schemas dynamically: %s", e)
            return []

    async def _emit(self, event_type: str, event_id: int, data: dict) -> None:
        payload = {
            "type": event_type,
            "data": {"id": event_id, **data},
        }
        await self._broadcaster.broadcast(payload)

    async def _emit_log(self, event_id: int, message: str, level: str = "info") -> None:
        payload = {
            "type": "log_line",
            "data": {
                "id": event_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": level,
                "message": message,
            },
        }
        await self._broadcaster.broadcast(payload)

    async def _broadcast_event(self, event: Event) -> None:
        payload = {
            "type": "status_update",
            "data": {
                "id": event.id,
                "status": event.status,
                "severity_text": event.severity_text,
                "severity_number": event.severity_number,
                "title": event.title,
                "updated_at": event.updated_at.isoformat() if event.updated_at else None,
            },
        }
        await self._broadcaster.broadcast(payload)

    async def _refresh_and_broadcast(self, event: Event, session: AsyncSession) -> None:
        """Refresh event from DB and broadcast status update."""
        await session.refresh(event)
        await self._broadcast_event(event)
