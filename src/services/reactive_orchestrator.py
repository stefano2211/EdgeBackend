"""Reactive event pipeline — Digital Optimus v2.

Architecture (3-phase):
  Phase 1 — S2-Triage:      routing decision (fast LLM call, JSON)
  Phase 2 — S1-Coordinator: fast intuition (historical + vl in parallel)
  Phase 3 — S2-Synthesis:   deep reasoning + planning (DeepAgents with tools)

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
from src.ia.langchain_models import get_chat_model, get_multimodal_chat_model
from src.ia.orchestrator_factory import create_reactive_orchestrator
from src.ia.prompts.reactive import (
    REACTIVE_S2_TRIAGE_PROMPT,
    REACTIVE_S1_COORDINATOR_PROMPT,
    REACTIVE_HISTORICAL_PROMPT,
    build_reactive_synthesis_prompt,
)
from src.persistencia.models.event import Event
from src.persistencia.repositories.event_repository import EventRepository
from src.services.browser_manager import BrowserManager
from src.services.chat_orchestrator import ChatOrchestrator
from src.services.event_broadcast import EventBroadcastManager
from src.services.reactive_config_service import ReactiveConfigService
from src.services._helpers import commit_and_refresh

logger = logging.getLogger(__name__)


class ReactiveOrchestrator:
    """Orchestrates reactive event analysis and execution via 3-phase pipeline."""

    def __init__(
        self,
        broadcaster: EventBroadcastManager,
        chat_orchestrator: ChatOrchestrator | None = None,
    ) -> None:
        self._broadcaster = broadcaster
        self._chat = chat_orchestrator or ChatOrchestrator()

    # ═══════════════════════════════════════════════════════════════════════════
    #  PUBLIC API
    # ═══════════════════════════════════════════════════════════════════════════

    async def analyze(self, event: Event, session: AsyncSession) -> None:
        """Run the full 3-phase reactive analysis pipeline."""
        thread_id = f"event-{event.id}"
        event_query = self._build_event_query(event)

        # Load user's reactive configuration
        config_service = ReactiveConfigService(session)
        enabled_tool_ids = await config_service.get_enabled_tools(event.triggered_by_user_id)
        enabled_kb_ids = await config_service.get_enabled_knowledge_bases(event.triggered_by_user_id)

        await self._emit_log(event.id, "Phase 0: Pipeline started", level="info")
        await self._emit_log(
            event.id,
            f"Config: {len(enabled_tool_ids)} tools, {len(enabled_kb_ids)} KBs enabled",
            level="info",
        )

        try:
            # ── Phase 1: S2-Triage ──
            await self._emit_log(event.id, "Phase 1: S2-Triage starting", level="info")
            triage = await self._run_s2_triage(event_query)
            await self._emit("triage_result", event.id, {"triage": triage})
            await self._emit_log(
                event.id,
                f"Phase 1: Triage complete → needs_s1={triage.get('needs_s1')} "
                f"needs_industrial={triage.get('needs_industrial')} "
                f"urgency={triage.get('urgency')}",
                level="info",
            )

            # ── Phase 2: S1-Coordinator (parallel specialists) ──
            s1_analysis: str | None = None
            if triage.get("needs_s1"):
                await self._emit_log(event.id, "Phase 2: S1-Coordinator starting", level="info")
                s1_analysis = await self._run_s1_coordinator(event, event_query, triage)
                if s1_analysis:
                    await self._emit("system1_result", event.id, {"result": s1_analysis})
                    await self._emit_log(event.id, "Phase 2: System-1 analysis completed", level="info")
            else:
                await self._emit_log(event.id, "Phase 2: Skipped (triage decided no S1 needed)", level="info")

            # ── Phase 2b: S2-Industrial (live data) ──
            industrial_data: str | None = None
            if triage.get("needs_industrial"):
                await self._emit_log(event.id, "Phase 2b: S2-Industrial data fetch starting", level="info")
                industrial_data = await self._run_s2_industrial(
                    event, event_query, enabled_tool_ids, enabled_kb_ids
                )
                if industrial_data:
                    await self._emit("industrial_result", event.id, {"result": industrial_data})
                    await self._emit_log(event.id, "Phase 2b: Industrial data fetched", level="info")
            else:
                await self._emit_log(event.id, "Phase 2b: Skipped (no industrial data needed)", level="info")

            # ── Phase 3: S2-Synthesis ──
            await self._emit_log(event.id, "Phase 3: S2-Synthesis starting", level="info")
            synthesis = await self._run_s2_synthesis(
                event=event,
                event_query=event_query,
                triage=triage,
                s1_analysis=s1_analysis,
                industrial_data=industrial_data,
                enabled_tool_ids=enabled_tool_ids,
                enabled_kb_ids=enabled_kb_ids,
            )

            analysis_text, plan, execute = self._parse_sections(synthesis)

            # Emit results
            if analysis_text:
                event.agent_reasoning = analysis_text
                await self._emit("system2_result", event.id, {"result": analysis_text})
                await self._emit_log(event.id, "Phase 3: System-2 reasoning completed", level="info")

            if plan:
                event.agent_plan = plan
                await self._emit("planner_result", event.id, {"plan": plan})
                await self._emit_log(event.id, "Phase 3: Planner generated remediation plan", level="info")

            if execute:
                await self._emit("execute_instruction", event.id, {"instruction": execute})
                await self._emit_log(event.id, "Phase 3: Execution instruction ready", level="info")

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
        """Execute approved plan using VLM + browser (streaming)."""
        thread_id = f"event-{event.id}"
        instruction = self._extract_execute_instruction(event) or event.agent_plan or "Execute the plan."

        request = ChatRequest(query=instruction, thread_id=thread_id)
        messages = [{"role": "user", "content": instruction}]

        await self._emit("vlm_prompt", event.id, {"prompt": instruction})
        await self._emit_log(event.id, "VLM execution started", level="info")

        actions: list[dict] = []

        try:
            async for chunk in self._chat.stream(request, messages, thread_id):
                chunk_type = chunk.get("type")

                if chunk_type == "screenshot":
                    await self._emit("screenshot", event.id, chunk.get("data", {}))
                    await self._emit_log(event.id, "Screenshot captured", level="debug")

                elif chunk_type == "thought":
                    thought = chunk.get("content", "")
                    await self._emit("vlm_analysis", event.id, {"analysis": thought})
                    await self._emit_log(event.id, f"VLM thought: {thought[:120]}", level="debug")

                elif chunk_type == "tool_call":
                    action = {
                        "type": chunk.get("name", "tool"),
                        "args": chunk.get("args", ""),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    actions.append(action)
                    await self._emit("action_executed", event.id, {"action": action})
                    await self._emit_log(event.id, f"Action: {action['type']}", level="info")

                elif chunk_type == "tool_result":
                    result = chunk.get("content", "")
                    if actions:
                        actions[-1]["result"] = result
                    await self._emit_log(event.id, f"Result: {result[:120]}", level="debug")

                elif chunk_type == "error":
                    error_msg = chunk.get("detail", "Unknown error")
                    await self._emit_log(event.id, f"Execution error: {error_msg}", level="error")

                elif chunk_type == "done":
                    await self._emit_log(event.id, "Execution stream completed", level="info")

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
    #  PHASE 2 — S1 COORDINATOR
    # ═══════════════════════════════════════════════════════════════════════════

    async def _run_s1_coordinator(
        self,
        event: Event,
        event_query: str,
        triage: dict,
    ) -> str | None:
        """Phase 2: fast intuition via historical + optional vl in parallel."""
        event_id = event.id
        thread_id = f"event-{event.id}-s1"

        # Always run historical
        await self._emit_log(event_id, "S1: Launching historical-agent...", level="info")
        historical_task = asyncio.create_task(self._call_historical_agent(event_query))

        # Conditionally run VL (visual verification via real browser streaming)
        vl_task = None
        if triage.get("needs_vl_post_approval"):
            await self._emit_log(event_id, "S1: Launching vl-agent (visual verification)...", level="info")
            vl_task = asyncio.create_task(self._call_vl_agent(event_query, event_id))

        # Await results
        historical_result = await historical_task
        await self._emit_log(event_id, "S1: historical-agent returned", level="info")

        vl_result = None
        if vl_task:
            vl_result = await vl_task
            await self._emit_log(event_id, "S1: vl-agent returned", level="info")

        # Synthesize S1 output
        s1_prompt = self._build_s1_synthesis_prompt(
            event_query=event_query,
            historical_result=historical_result,
            vl_result=vl_result,
        )

        client = get_llm_client()
        response = await client.chat_completion(
            messages=[
                {"role": "system", "content": REACTIVE_S1_COORDINATOR_PROMPT},
                {"role": "user", "content": s1_prompt},
            ],
            temperature=0.5,
            max_tokens=600,
            stream=False,
        )

        raw = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        return raw.strip() if raw else None

    async def _call_historical_agent(self, event_query: str) -> str | None:
        """Direct LLM call to the historical specialist (no tools, fine-tuned)."""
        try:
            model = get_chat_model(adapter="historical")
            # For simplicity, we use the raw LLM client; historical is a reasoning-only agent
            client = get_llm_client()
            response = await client.chat_completion(
                messages=[
                    {"role": "system", "content": REACTIVE_HISTORICAL_PROMPT},
                    {"role": "user", "content": event_query},
                ],
                temperature=0.4,
                max_tokens=500,
                stream=False,
            )
            return response.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        except Exception as exc:
            logger.warning("Historical agent call failed: %s", exc)
            return None

    async def _call_vl_agent(self, event_query: str, event_id: int) -> str | None:
        """VL visual verification with real browser + SSE streaming.

        Reuses ChatOrchestrator.stream() to get the full VL sub-agent experience
        (browser_navigate, screenshots, thoughts, tool_calls) and re-emits
        events as vl_* so the frontend can show the mini S1 Visual Panel.

        Safety limits: max 5 tool actions or 60 seconds, whichever comes first.
        """
        instruction = (
            f"Event context:\n{event_query}\n\n"
            "Verify the current visual state relevant to this event. "
            "Navigate to the relevant dashboard/URL if needed. "
            "Take screenshots and report what you see concisely. "
            "Maximum 5 browser actions — stop after that."
        )

        request = ChatRequest(
            query=instruction,
            thread_id=f"event-{event_id}-vl",
        )
        messages = [{"role": "user", "content": instruction}]

        # Guard active thread_id so we don't conflict with ongoing chats
        controller = BrowserManager.get_instance().get_controller()
        prev_thread_id = controller.active_thread_id
        controller.set_active_thread_id(request.thread_id)

        full_content = ""
        step_count = 0
        start_time = time.time()
        max_steps = 5
        max_duration = 60.0

        try:
            async for chunk in self._chat.stream(request, messages, request.thread_id):
                # Internal chunk — skip
                if chunk.get("_internal"):
                    full_content = chunk.get("full_content", full_content)
                    continue

                # Safety brake
                if step_count >= max_steps or (time.time() - start_time) > max_duration:
                    await self._emit_log(event_id, "S1-VL: Safety limit reached, stopping.", level="info")
                    break

                chunk_type = chunk.get("type")

                if chunk_type == "screenshot":
                    await self._emit("vl_screenshot", event_id, chunk.get("data", {}))

                elif chunk_type == "thought":
                    thought = chunk.get("content", "")
                    await self._emit("vl_thought", event_id, {"thought": thought})

                elif chunk_type == "tool_call":
                    step_count += 1
                    action = {
                        "type": chunk.get("name", "tool"),
                        "args": chunk.get("args", ""),
                        "step": step_count,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    await self._emit("vl_action_executed", event_id, {"action": action})
                    await self._emit("vl_progress", event_id, {
                        "current_step": step_count,
                        "max_steps": max_steps,
                    })
                    await self._emit_log(
                        event_id,
                        f"S1-VL: Action {step_count}/{max_steps} — {action['type']}",
                        level="info",
                    )

                elif chunk_type == "tool_result":
                    result = chunk.get("content", "")
                    await self._emit("vl_action_result", event_id, {"result": result})

                elif chunk_type == "subagent":
                    name = chunk.get("name", "unknown")
                    status = chunk.get("status", "")
                    await self._emit_log(
                        event_id,
                        f"S1-VL: Sub-agent {name} {status}",
                        level="debug",
                    )

                elif chunk_type == "done":
                    break

                elif chunk_type == "error":
                    await self._emit_log(
                        event_id,
                        f"S1-VL: Stream error — {chunk.get('detail', 'Unknown')}",
                        level="error",
                    )
                    break

        except Exception as exc:
            logger.warning("VL agent streaming failed: %s", exc)
            await self._emit_log(event_id, f"S1-VL error: {exc}", level="error")

        finally:
            controller.set_active_thread_id(prev_thread_id)

        return full_content.strip() if full_content else None

    def _build_s1_synthesis_prompt(
        self,
        event_query: str,
        historical_result: str | None,
        vl_result: str | None,
    ) -> str:
        """Build the input for the S1-Coordinator synthesis call."""
        parts = [f"Original event:\n{event_query}\n"]
        if historical_result:
            parts.append(f"<historical_result>\n{historical_result}\n</historical_result>\n")
        if vl_result:
            parts.append(f"<vl_result>\n{vl_result}\n</vl_result>\n")
        parts.append(
            "Synthesize the above into a concise System-1 Analysis. "
            "Follow the output format in your system prompt."
        )
        return "\n".join(parts)

    # ═══════════════════════════════════════════════════════════════════════════
    #  PHASE 2b — S2 INDUSTRIAL (live data)
    # ═══════════════════════════════════════════════════════════════════════════

    async def _run_s2_industrial(
        self,
        event: Event,
        event_query: str,
        enabled_tool_ids: list[int],
        enabled_kb_ids: list[int],
    ) -> str | None:
        """Fetch live sensor data and SOPs via Industrial-Agent tools.

        Uses the reactive orchestrator directly (MCP + RAG) and returns
        the raw tool results as a formatted string for S2 synthesis.
        """
        try:
            # Create a temporary reactive orchestrator focused on industrial data
            orchestrator = create_reactive_orchestrator(
                knowledge_base_ids=enabled_kb_ids or None,
                enable_knowledge=bool(enabled_kb_ids),
                enable_mcp=bool(enabled_tool_ids),
                enabled_tool_names=enabled_tool_ids,
            )

            thread_id = f"event-{event.id}-industrial"
            config = {"configurable": {"thread_id": thread_id}}
            messages = [{"role": "user", "content": event_query}]

            result = await orchestrator.ainvoke(
                {"messages": messages},
                config=config,
            )
            # DeepAgents returns a dict with "messages" list
            msgs = result.get("messages", [])
            if msgs:
                return str(msgs[-1].content).strip()
            return None
        except Exception as exc:
            logger.warning("Industrial data fetch failed: %s", exc)
            return None

    # ═══════════════════════════════════════════════════════════════════════════
    #  PHASE 3 — S2 SYNTHESIS
    # ═══════════════════════════════════════════════════════════════════════════

    async def _run_s2_synthesis(
        self,
        event: Event,
        event_query: str,
        triage: dict,
        s1_analysis: str | None,
        industrial_data: str | None,
        enabled_tool_ids: list[int],
        enabled_kb_ids: list[int],
    ) -> str:
        """Phase 3: deep reasoning + planning via DeepAgents synthesis."""
        synthesis_prompt = build_reactive_synthesis_prompt(
            system1_analysis=s1_analysis or "No System-1 analysis available.",
            industrial_data=industrial_data or "No live industrial data available.",
            event_context=event_query,
        )

        # Create reactive orchestrator for S2 (has tools + synthesis prompt)
        orchestrator = create_reactive_orchestrator(
            knowledge_base_ids=enabled_kb_ids or None,
            enable_knowledge=bool(enabled_kb_ids),
            enable_mcp=bool(enabled_tool_ids) and triage.get("needs_industrial", True),
            enabled_tool_names=enabled_tool_ids,
            system_prompt_override=synthesis_prompt,
        )

        thread_id = f"event-{event.id}-synthesis"
        config = {"configurable": {"thread_id": thread_id}}
        messages = [{"role": "user", "content": "Produce the final analysis, plan, and execute instruction."}]

        result = await orchestrator.ainvoke(
            {"messages": messages},
            config=config,
        )
        msgs = result.get("messages", [])
        if msgs:
            return str(msgs[-1].content)
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
