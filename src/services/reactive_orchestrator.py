"""Reactive event pipeline — Digital Optimus v2.

Architecture (2-phase):
  Phase 1 — S2-Triage:      routing decision (fast LLM call, JSON)
  Phase 2 — S2-Autonomous:  autonomous orchestrator delegates to industrial-agent,
                             historical-agent and vl-agent via task() (flat hierarchy)

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
from src.persistencia.models.event import Event
from src.persistencia.repositories.event_repository import EventRepository
from src.services.browser_manager import BrowserManager
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
        self._browser_manager = BrowserManager.get_instance("reactive")

    # ═══════════════════════════════════════════════════════════════════════════
    #  PUBLIC API
    # ═══════════════════════════════════════════════════════════════════════════

    async def analyze(self, event: Event, session: AsyncSession) -> None:
        """Run the 2-phase reactive analysis pipeline.

        Phase 1 — S2 Triage: fast LLM call producing routing hints (JSON).
        Phase 2 — S2 Autonomous: DeepAgents orchestrator with industrial-agent,
                  historical-agent and vl-agent as direct sub-agents. S2
                  decides which to invoke via task() and synthesizes the results.
        """
        event_query = self._build_event_query(event)

        # Load user's reactive configuration
        config_service = ReactiveConfigService(session)
        config_res = await config_service.get_enabled_resources(event.triggered_by_user_id)
        enabled_tool_ids = config_res["tool_ids"]
        enabled_kb_ids = config_res["kb_ids"]
        enabled_kb_names = config_res["kb_names"]
        enabled_tool_names = config_res["tool_names"]

        await self._emit_log(event.id, "Phase 0: Pipeline started", level="info")
        await self._emit_log(
            event.id,
            f"Config: {len(enabled_tool_ids)} tools, {len(enabled_kb_ids)} KBs enabled",
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
                f"needs_historical={triage.get('needs_s1')} "
                f"needs_industrial={triage.get('needs_industrial')}",
                level="info",
            )

            # ── Phase 2: S2 Autonomous Orchestrator ──
            # S2 receives event + triage hints and autonomously decides which
            # sub-agents (industrial-agent, historical-agent, vl-agent) to
            # invoke via task(), then synthesizes all results.
            await self._emit_log(event.id, "Phase 2: S2 Autonomous Orchestrator starting", level="info")
            synthesis = await self._run_s2_autonomous(
                event=event,
                event_query=event_query,
                triage=triage,
                enabled_kb_ids=[str(k) for k in enabled_kb_ids],
                enabled_kb_names=enabled_kb_names,
                enabled_tool_names=enabled_tool_names,
            )


            analysis_text, plan, execute = self._parse_sections(synthesis)

            if analysis_text:
                event.agent_reasoning = analysis_text
                await self._emit("system2_result", event.id, {"result": analysis_text})
                await self._emit_log(event.id, "Phase 2: S2 reasoning completed", level="info")

            if plan:
                event.agent_plan = plan
                await self._emit("planner_result", event.id, {"plan": plan})
                await self._emit_log(event.id, "Phase 2: Remediation plan generated", level="info")

            if execute:
                await self._emit("execute_instruction", event.id, {"instruction": execute})
                await self._emit_log(event.id, "Phase 2: Execution instruction ready", level="info")

            # Transition
            event.status = "awaiting_approval"
            await session.commit()
            await self._refresh_and_broadcast(event, session)
            await self._emit_log(event.id, "DEV_MODE PAUSED — awaiting approval", level="info")

        except Exception as exc:
            logger.exception("Analysis pipeline failed for event %s", event.id)
            await self._emit_log(event.id, f"Pipeline error: {exc}", level="error")
            event.status = "failed"
            await session.commit()
            await self._broadcast_event(event)

    async def execute(self, event: Event, session: AsyncSession) -> None:
        """Execute approved plan using orchestrator + VL agent for Gmail report."""
        thread_id = f"event-{event.id}"
        base_instruction = self._extract_execute_instruction(event) or event.agent_plan or "Execute the plan."

        # Fetch available credentials so the agent knows what keys exist
        from src.services.credential_service import CredentialService
        cred_service = CredentialService(session)
        user_creds = await cred_service.list_for_user(event.triggered_by_user_id)
        cred_keys = [c.key_identifier for c in user_creds]
        cred_catalog = "\n".join(
            f"  - {c.key_identifier}: {c.name}" + (f" ({c.description})" if c.description else "")
            for c in user_creds
        ) if user_creds else "  (No credentials configured)"

        instruction = (
            f"{base_instruction}\n\n"
            "---\n"
            "MANDATORY FINAL STEP — Gmail Report:\n"
            "After completing all other steps above, you MUST delegate to the "
            "vl-agent (via task()) to send a summary report by email.\n\n"
            "AVAILABLE CREDENTIALS (use get_secret_credential tool to retrieve values):\n"
            f"{cred_catalog}\n\n"
            "The vl-agent must:\n"
            "1. Open a browser and navigate to https://mail.google.com\n"
            "2. Log in using stored credentials:\n"
            "   - Call get_secret_credential(key_identifier='GMAIL_CREDS') (or the relevant key from the catalog above).\n"
            "   - The tool will return a JSON object with fields like 'email' and 'password'.\n"
            "   - Use those fields to type the email, click Next, and type the password.\n"
            "   - NEVER use ask_user for credentials — always use get_secret_credential\n"
            f"3. Compose a new email to erastellius@gmail.com\n"
            f"4. Subject: '[Digital Optimus] Incident Report — {event.title}'\n"
            "5. Body: A professional summary of this event including:\n"
            f"   - Event: {event.title}\n"
            f"   - Severity: {event.severity}\n"
            f"   - Description: {event.description}\n"
            "   - Analysis summary (from the System-2 reasoning above)\n"
            "   - Actions taken / remediation plan\n"
            "   - Timestamp of resolution\n"
            "6. Send the email\n"
            "This step is NON-NEGOTIABLE. Do NOT skip it.\n"
        )

        messages = [{"role": "user", "content": instruction}]

        await self._emit("vlm_prompt", event.id, {"prompt": instruction})
        await self._emit_log(event.id, "Execution pipeline started", level="info")

        # Load user's reactive configuration
        config_service = ReactiveConfigService(session)
        config_res = await config_service.get_enabled_resources(event.triggered_by_user_id)
        enabled_kb_ids = config_res["kb_ids"]
        enabled_tool_names = config_res["tool_names"]

        # Create isolated reactive orchestrator
        orchestrator = create_reactive_orchestrator(
            knowledge_base_ids=[str(k) for k in enabled_kb_ids] or None,
            enable_knowledge=bool(enabled_kb_ids),
            enable_mcp=bool(enabled_tool_names),
            enabled_tool_names=enabled_tool_names,
        )


        # Set up isolated browser emitter for the reactive pipeline
        controller = self._browser_manager.get_controller()

        async def _reactive_emitter(payload: dict) -> None:
            if "screenshot" in payload:
                await self._emit("vl_screenshot", event.id, payload["screenshot"])
            elif "thought" in payload:
                await self._emit("vl_thought", event.id, {"thought": payload["thought"]})
                await self._emit_log(event.id, f"VL thought: {payload['thought'][:120]}", level="debug")

        controller.set_event_emitter(_reactive_emitter)
        controller.set_active_thread_id(thread_id)

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
                        elif pending_task_agent == "vl-agent":
                            await self._emit("vl_result", event.id, {"result": str(result)})
                            await self._emit_log(event.id, "VL agent result received", level="info")
                        elif pending_task_agent == "industrial-agent":
                            await self._emit("industrial_result", event.id, {"result": str(result)})
                            await self._emit_log(event.id, "Industrial result received", level="info")
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
            await self._broadcast_event(event)
            return

        # Success
        event.status = "completed"
        event.resolved_at = datetime.now(timezone.utc).replace(tzinfo=None)
        event.actions_taken = actions
        await session.commit()
        await self._refresh_and_broadcast(event, session)
        await self._emit_log(event.id, "Event completed successfully", level="info")

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
                "needs_s1": True,
                "needs_industrial": True,
                "needs_vl_post_approval": False,
                "justification": "Parse error — defaulting to full analysis.",
            }

        # Ensure defaults
        triage.setdefault("needs_s1", True)
        triage.setdefault("needs_industrial", True)
        triage.setdefault("needs_vl_post_approval", False)
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
    ) -> str:
        """Phase 2: S2 autonomous orchestrator."""
        orchestrator = create_reactive_orchestrator(
            knowledge_base_ids=enabled_kb_ids or None,
            enable_knowledge=bool(enabled_kb_ids),
            enable_mcp=bool(enabled_tool_names),
            enabled_tool_names=enabled_tool_names,
        )


        # Hook up the isolated reactive browser controller for vl-agent screenshots
        controller = self._browser_manager.get_controller()
        async def _vl_emitter(payload: dict) -> None:
            if "screenshot" in payload:
                await self._emit("vl_screenshot", event.id, payload["screenshot"])
            elif "thought" in payload:
                await self._emit("vl_thought", event.id, {"thought": payload["thought"]})
        controller.set_event_emitter(_vl_emitter)

        # Pass triage hints + event as the user message so S2 can make
        # an informed delegation decision without being hardcoded to follow it.
        triage_str = json.dumps(triage, ensure_ascii=False, indent=2)
        user_message = (
            f"<triage_hints>\n{triage_str}\n</triage_hints>\n\n"
            f"<event>\n{event_query}\n</event>\n\n"
            "Analiza este evento industrial. Usa task() para delegar a los "
            "sub-agentes que necesites (puedes invocar varios en paralelo). "
            "Luego sintetiza todos los resultados en el formato requerido."
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

                    if agent_name == "industrial-agent":
                        await self._emit("industrial_result", event.id, {"result": str(msg.content)})
                    elif agent_name == "historical-agent":
                        await self._emit("historical_result", event.id, {"result": str(msg.content)})
                        await self._emit_log(event.id, "Historical analysis received", level="info")
                        event.agent_analysis = str(msg.content)
                    elif agent_name == "vl-agent":
                        await self._emit("vl_result", event.id, {"result": str(msg.content)})
            
            return str(msgs[-1].content).strip() if msgs else ""
        except Exception as exc:
            logger.warning("S2 autonomous orchestrator failed: %s", exc)
            return ""

    # ═══════════════════════════════════════════════════════════════════════════
    #  PRIVATE HELPERS
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_event_query(self, event: Event) -> str:
        payload_str = ""
        if event.raw_payload:
            payload_str = json.dumps(event.raw_payload, indent=2)

        return (
            f"Event ID: {event.id}\n"
            f"Severity: {event.severity}\n"
            f"Title: {event.title}\n"
            f"Description: {event.description}\n"
            f"Payload:\n{payload_str}\n\n"
            "Analyze this industrial event, identify the root cause, and produce a structured remediation plan."
        )

    def _parse_sections(self, content: str) -> tuple[str, str, str]:
        """Parse orchestrator response into (analysis, plan, execute_instruction)."""
        analysis = content.strip()
        plan = ""
        execute = ""

        if "---PLAN---" in content:
            parts = content.split("---PLAN---", 1)
            analysis = parts[0].strip()
            rest = parts[1].strip()

            if "---EXECUTE---" in rest:
                plan_parts = rest.split("---EXECUTE---", 1)
                plan = plan_parts[0].strip()
                execute = plan_parts[1].strip()
            else:
                plan = rest

        return analysis, plan, execute

    def _extract_execute_instruction(self, event: Event) -> str | None:
        """Extract ---EXECUTE--- section from stored plan or reasoning."""
        text = event.agent_plan or event.agent_reasoning or ""
        if "---EXECUTE---" in text:
            return text.split("---EXECUTE---", 1)[1].strip()
        return None

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
                "severity": event.severity,
                "title": event.title,
                "updated_at": event.updated_at.isoformat() if event.updated_at else None,
            },
        }
        await self._broadcaster.broadcast(payload)

    async def _refresh_and_broadcast(self, event: Event, session: AsyncSession) -> None:
        """Refresh event from DB and broadcast status update."""
        await session.refresh(event)
        await self._broadcast_event(event)
