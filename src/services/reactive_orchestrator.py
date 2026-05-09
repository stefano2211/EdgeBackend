"""Reactive event pipeline using the same DeepAgents infrastructure as chat.

Architecture:
- Analysis phase: ChatOrchestrator.non_stream() with reactive prompt.
- Execution phase: ChatOrchestrator.stream() with VLM + browser.

All prompts and logs are ephemeral (emitted via SSE, not persisted in DB).
Only analysis results, reasoning, plans, and actions are persisted.
"""

import asyncio
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.v1.schemas.chat import ChatRequest
from src.core.logging import logging
from src.persistencia.models.event import Event
from src.persistencia.repositories.event_repository import EventRepository
from src.services.chat_orchestrator import ChatOrchestrator
from src.services.event_broadcast import EventBroadcastManager

logger = logging.getLogger(__name__)


class ReactiveOrchestrator:
    """Orchestrates reactive event analysis and execution via DeepAgents."""

    def __init__(
        self,
        broadcaster: EventBroadcastManager,
        chat_orchestrator: ChatOrchestrator | None = None,
    ) -> None:
        self._broadcaster = broadcaster
        self._chat = chat_orchestrator or ChatOrchestrator()

    async def analyze(self, event: Event, session: AsyncSession) -> None:
        """Run System 1 + System 2 + Planner (non-streaming)."""
        thread_id = f"event-{event.id}"

        query = self._build_event_query(event)
        request = ChatRequest(query=query, thread_id=thread_id)
        messages = [{"role": "user", "content": query}]

        await self._emit_log(event.id, "Analysis pipeline started", level="info")

        try:
            result = await self._chat.non_stream(request, messages, thread_id)
        except Exception as exc:
            logger.exception("Analysis failed for event %s", event.id)
            await self._emit_log(event.id, f"Analysis error: {exc}", level="error")
            event.status = "failed"
            await session.commit()
            await self._broadcast_event(event)
            return

        content = result.get("content", "")

        # Parse structured response
        analysis, plan, execute_instruction = self._parse_sections(content)

        # Emit System-1 (analysis section)
        if analysis:
            event.agent_analysis = analysis
            await self._emit("system1_result", event.id, {"result": analysis})
            await self._emit_log(event.id, "System-1 analysis completed", level="info")

        # Emit System-2 (full reasoning)
        if content:
            event.agent_reasoning = content
            await self._emit("system2_result", event.id, {"result": content})
            await self._emit_log(event.id, "System-2 reasoning completed", level="info")

        # Emit Planner
        if plan:
            event.agent_plan = plan
            await self._emit("planner_result", event.id, {"plan": plan})
            await self._emit_log(event.id, "Planner generated remediation plan", level="info")

        # Emit execute instruction
        if execute_instruction:
            await self._emit("execute_instruction", event.id, {"instruction": execute_instruction})
            await self._emit_log(event.id, "Execution instruction ready", level="info")

        # Transition
        event.status = "awaiting_approval"
        await session.commit()
        await self._refresh_and_broadcast(event, session)
        await self._emit_log(event.id, "DEV_MODE PAUSED — awaiting approval", level="info")

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

    # --- Private helpers ---

    def _build_event_query(self, event: Event) -> str:
        import json

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
