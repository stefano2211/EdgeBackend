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
import time
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.chat import ChatRequest
from src.core.config import settings
from src.core.logging import logging
from src.ia.llm_client import get_llm_client
from src.ia.langchain_models import get_chat_model
from src.ia.orchestrator_factory import create_reactive_orchestrator
from src.ia.prompts.reactive import (
    REACTIVE_S2_TRIAGE_PROMPT,
    build_reactive_s2_orchestrator_prompt,
)
from src.ia.schemas.reactive import ReactiveAnalysisOutput
from src.persistencia.models.event import Event
from src.persistencia.repositories.event_repository import EventRepository
from src.services.event_broadcast import EventBroadcastManager
from src.services.reactive_config_service import ReactiveConfigService
from src.services._helpers import commit_and_refresh
from src.services.chat_orchestrator import _extract_chunk_payload

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

            if output.execute_instruction:
                await self._emit("execute_instruction", event.id, {"instruction": output.execute_instruction})
                await self._emit_log(event.id, "Phase 2: Execution instruction ready", level="info")

            # Transition
            event.status = "awaiting_approval"
            await session.commit()
            await self._refresh_and_broadcast(event, session)
            await self._emit_log(event.id, "DEV_MODE PAUSED — awaiting approval", level="info")

            # ── Mandatory notification: analysis complete ──
            from src.services.notification_service import NotificationService
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
        """Execute approved plan using the reactive orchestrator."""
        thread_id = f"event-{event.id}"
        base_instruction = event.agent_plan or "Execute the plan."

        messages = [{"role": "user", "content": base_instruction}]

        await self._emit("vlm_prompt", event.id, {"prompt": base_instruction})
        await self._emit_log(event.id, "Execution pipeline started", level="info")

        # Load user's reactive configuration
        config_service = ReactiveConfigService(session)
        config_res = await config_service.get_enabled_resources(event.triggered_by_user_id)
        enabled_kb_ids = config_res["kb_ids"]
        enabled_kb_names = config_res["kb_names"]
        enabled_tool_names = config_res["tool_names"]

        # Resolve dynamic tool schemas for prompt injection
        tool_schemas = await self._resolve_tool_schemas(session, event.triggered_by_user_id)

        # Create isolated reactive orchestrator
        orchestrator = create_reactive_orchestrator(
            knowledge_base_ids=[str(k) for k in enabled_kb_ids] or None,
            enable_knowledge=bool(enabled_kb_ids),
            enable_mcp=bool(enabled_tool_names),
            enabled_tool_names=enabled_tool_names,
            tool_schemas=tool_schemas,
            kb_names=enabled_kb_names,
        )


        config = {"configurable": {"thread_id": thread_id}}
        actions: list[dict] = []
        full_content = ""
        current_agent = "orchestrator"
        agents_used: set[str] = set()
        # Track which sub-agent is currently being delegated to via task()
        pending_task_agent: str | None = None

        try:
            async for chunk in orchestrator.astream(
                {"messages": messages},
                config=config,
                stream_mode="messages",
                subgraphs=True,
                version="v2",
            ):
                agent_name, text, reasoning, agents_used, events = _extract_chunk_payload(
                    chunk, current_agent=current_agent, agents_used=agents_used
                )
                current_agent = agent_name

                if text:
                    full_content += text

                for ev in events:
                    ev_type = ev.get("type")
                    if ev_type == "tool_call":
                        tool_name = ev.get("name", "tool")
                        tool_args = ev.get("args", "")
                        action = {
                            "type": tool_name,
                            "args": tool_args,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                        actions.append(action)
                        await self._emit("action_executed", event.id, {"action": action})
                        await self._emit_log(event.id, f"Action: {tool_name}", level="info")

                        # Detect task() delegation to sub-agents
                        if tool_name == "task":
                            # Args may be a dict or a JSON string during streaming
                            parsed_args = tool_args
                            if isinstance(tool_args, str):
                                try:
                                    parsed_args = json.loads(tool_args)
                                except (json.JSONDecodeError, TypeError):
                                    parsed_args = {}
                            if isinstance(parsed_args, dict):
                                # DeepAgents uses 'subagent_type' but some versions use 'agent'
                                pending_task_agent = (
                                    parsed_args.get("subagent_type")
                                    or parsed_args.get("agent")
                                )
                                if pending_task_agent:
                                    await self._emit_log(
                                        event.id,
                                        f"Delegating to {pending_task_agent}",
                                        level="info",
                                    )
                    elif ev_type == "tool_result":
                        result = ev.get("content", "")
                        if actions:
                            actions[-1]["result"] = result
                        await self._emit_log(event.id, f"Result: {str(result)[:120]}", level="debug")

                        # Emit sub-agent results to the appropriate frontend panel
                        if pending_task_agent == "historical-agent":
                            await self._emit("historical_result", event.id, {"result": str(result)})
                            await self._emit_log(event.id, "Historical analysis received", level="info")
                        elif pending_task_agent == "rag-agent":
                            await self._emit("rag_result", event.id, {"result": str(result)})
                            await self._emit_log(event.id, "RAG result received", level="info")
                        elif pending_task_agent == "mcp-agent":
                            await self._emit("mcp_result", event.id, {"result": str(result)})
                            await self._emit_log(event.id, "MCP result received", level="info")
                        pending_task_agent = None
                    elif ev_type == "subagent":
                        await self._emit_log(
                            event.id,
                            f"Sub-agent {ev.get('name')} {ev.get('status')}",
                            level="debug",
                        )

        except Exception as exc:
            logger.exception("Execution failed for event %s", event.id)
            await self._emit_log(event.id, f"Execution error: {exc}", level="error")
            event.status = "failed"
            event.actions_taken = actions
            await session.commit()
            await self._refresh_and_broadcast(event, session)

            # ── Mandatory notification: execution failed ──
            from src.services.notification_service import NotificationService
            ns = NotificationService(session)
            try:
                await ns.notify_execution_failed(event, exc)
            except Exception as notify_exc:
                logger.warning("Failed to send failure notification: %s", notify_exc)
            return

        # Success
        event.status = "completed"
        event.resolved_at = datetime.now(timezone.utc).replace(tzinfo=None)
        event.actions_taken = actions
        await session.commit()
        await self._refresh_and_broadcast(event, session)
        await self._emit_log(event.id, "Event completed successfully", level="info")

        # ── Mandatory notification: execution complete ──
        from src.services.notification_service import NotificationService
        ns = NotificationService(session)
        try:
            await ns.notify_execution_complete(event)
            await self._emit_log(event.id, "Notification sent: execution complete", level="info")
        except Exception as notify_exc:
            logger.warning("Failed to send execution notification: %s", notify_exc)
            await self._emit_log(event.id, f"Notification failed: {notify_exc}", level="warn")

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
        )


        # Pass triage hints + event as the user message so S2 can make
        # an informed delegation decision without being hardcoded to follow it.
        triage_str = json.dumps(triage, ensure_ascii=False, indent=2)
        user_message = (
            f"<triage_hints>\n{triage_str}\n</triage_hints>\n\n"
            f"<event>\n{event_query}\n</event>\n\n"
            "Analiza este evento industrial. Usa task() para delegar a los "
            "sub-agentes que necesites (puedes invocar varios en paralelo). "
            "Luego sintetiza todos los resultados en un JSON que cumpla EXACTAMENTE "
            "el schema proporcionado en tu system prompt. NO agregues texto fuera del JSON."
        )

        thread_id = f"event-{event.id}-s2"
        config = {"configurable": {"thread_id": thread_id}}
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
        """Resolve MCP tool schemas from DB for dynamic prompt injection."""
        try:
            from src.persistencia.repositories.reactive_tool_repository import (
                ReactiveToolRepository,
            )
            repo = ReactiveToolRepository(session)
            if user_id is not None:
                tools = await repo.list_enabled_by_user(user_id)
            else:
                tools = await repo.list()
                tools = [t for t in tools if t.is_enabled]

            return [
                {
                    "name": t.name,
                    "description": t.description,
                    "parameter_schema": t.parameter_schema,
                }
                for t in tools
            ]
        except Exception as e:
            logger.warning("Failed to resolve tool schemas: %s", e)
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
