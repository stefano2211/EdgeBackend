"""Reactive event pipeline — simplified single-phase analysis.

Architecture:
  1. Event arrives → status "analyzing"
  2. DeepAgents orchestrator delegates to sub-agents (rag, mcp, historical, db_analyst)
  3. Orchestrator's final message is parsed as ReactiveAnalysisOutput JSON
  4. Fields saved to event → status "completed"
  5. Email sent automatically via MCP (send_email) with the 3 outputs
"""

import json
import os
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.logging import logging
from backend.ia.orchestrator_factory import create_reactive_orchestrator
from backend.ia.schemas.reactive import ReactiveAnalysisOutput
from backend.persistencia.models.event import Event
from backend.services.event_broadcast import EventBroadcastManager
from backend.services.reactive_config_service import ReactiveConfigService

logger = logging.getLogger(__name__)


class ReactiveOrchestrator:
    """Orchestrates reactive event analysis via single-phase DeepAgents pipeline."""

    def __init__(
        self,
        broadcaster: EventBroadcastManager,
    ) -> None:
        self._broadcaster = broadcaster

    # ═══════════════════════════════════════════════════════════════════════════
    #  PUBLIC API
    # ═══════════════════════════════════════════════════════════════════════════

    async def analyze(self, event: Event, session: AsyncSession) -> None:
        """Run the simplified reactive analysis pipeline."""
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

        await self._emit_log(event.id, "Analysis started", level="info")
        await self._emit_log(
            event.id,
            f"Config: {len(enabled_tool_ids)} tools, {len(enabled_kb_ids)} KBs enabled, "
            f"{len(tool_schemas)} tool schemas resolved",
            level="info",
        )

        try:
            # ── Single Phase: DeepAgents Orchestrator ──
            output = await self._run_orchestrator(
                event=event,
                event_query=event_query,
                enabled_kb_ids=[str(k) for k in enabled_kb_ids],
                enabled_kb_names=enabled_kb_names,
                enabled_tool_names=enabled_tool_names,
                tool_schemas=tool_schemas,
            )

            if output is None:
                raise RuntimeError(
                    "The orchestrator could not generate a structured output "
                    "(possible internal agent failure or timeout)."
                )

            # Store structured fields
            if output.analysis:
                event.agent_analysis = output.analysis
                await self._emit("analysis_result", event.id, {"result": output.analysis})
                await self._emit_log(event.id, "Analysis generated", level="info")

            if output.diagnosis:
                event.agent_diagnosis = output.diagnosis
                await self._emit("diagnosis_result", event.id, {"diagnosis": output.diagnosis})
                await self._emit_log(event.id, "Diagnosis generated", level="info")

            if output.plan:
                event.agent_plan = output.plan
                await self._emit("planner_result", event.id, {"plan": output.plan})
                await self._emit_log(event.id, "Remediation plan generated", level="info")

            # ── Send email automatically via MCP ──
            await self._send_analysis_email(event, session)

            # Transition to completed
            event.status = "completed"
            event.resolved_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await session.commit()
            await self._refresh_and_broadcast(event, session)
            await self._emit_log(event.id, "Analysis complete — event resolved", level="info")

        except Exception as exc:
            logger.exception("Analysis pipeline failed for event %s", event.id)
            await self._emit_log(event.id, f"Pipeline error: {exc}", level="error")
            event.status = "failed"
            await session.commit()
            await self._refresh_and_broadcast(event, session)

    async def execute(self, event: Event, session: AsyncSession) -> None:
        """Remediation execution phase — no longer used in automatic flow.

        Raises NotImplementedError because the reactive pipeline completes
        in a single phase (analysis). The two-phase approach has been removed.
        """
        raise NotImplementedError(
            "The reactive pipeline no longer has a separate execution phase. "
            "The analysis phase produces analysis, diagnosis, and remediation plan "
            "in a single step. Event execution must be handled externally."
        )

    # ═══════════════════════════════════════════════════════════════════════════
    #  ORCHESTRATOR PHASE
    # ═══════════════════════════════════════════════════════════════════════════

    async def _run_orchestrator(
        self,
        event: Event,
        event_query: str,
        enabled_kb_ids: list[str],
        enabled_kb_names: list[str],
        enabled_tool_names: list[str],
        tool_schemas: list[dict] | None = None,
    ) -> ReactiveAnalysisOutput | None:
        """Run the DeepAgents orchestrator and parse the final message as structured JSON."""
        db_connection_ids = await self._resolve_db_connection_ids(session, event.triggered_by_user_id)

        orchestrator = create_reactive_orchestrator(
            knowledge_base_ids=enabled_kb_ids or None,
            enable_knowledge=bool(enabled_kb_ids),
            enable_mcp=bool(enabled_tool_names),
            enabled_tool_names=enabled_tool_names,
            domain=event.domain or "generic",
            tool_schemas=tool_schemas,
            kb_names=enabled_kb_names,
            user_id=event.triggered_by_user_id,
            db_connection_ids=db_connection_ids,
        )

        user_message = (
            f"<event>\n{event_query}\n</event>\n\n"
            "Analyze this event following the decision tree in your system prompt. "
            "Call ALL necessary sub-agents in PARALLEL in a single turn using task(). "
            "Do NOT call the same sub-agent more than once. "
            "When all results are collected, write a comprehensive report in Spanish covering "
            "analysis, diagnosis, and remediation plan."
        )

        thread_id = f"event-{event.id}-s2"
        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": 40,
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
                    if msg.name == "task":
                        for prev_msg in reversed(msgs[:i]):
                            if (
                                getattr(prev_msg, "type", "") == "ai"
                                and hasattr(prev_msg, "tool_calls")
                            ):
                                for tc in prev_msg.tool_calls:
                                    if tc.get("id") == msg.tool_call_id:
                                        tc_args = tc.get("args", {})
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
                    elif agent_name == "db_analyst-agent":
                        await self._emit("db_analyst_result", event.id, {"result": str(msg.content)})
                        await self._emit_log(event.id, "DB analysis received", level="info")

            if not msgs:
                logger.warning("Orchestrator returned no messages")
                return None

            # ── Phase 2: Synthesis into Structured Output ──
            await self._emit_log(event.id, "Synthesizing structured analysis...", level="info")
            try:
                from langchain_core.messages import HumanMessage
                synthesis_msg = HumanMessage(
                    content=(
                        "You are the Aura AI Synthesis Layer. Read the above conversation history "
                        "which contains an analysis of a system/industrial event along with sub-agent findings. "
                        "Synthesize this information into a structured response containing: "
                        "1. analysis: A detailed root cause analysis in Spanish. "
                        "2. diagnosis: A bulleted diagnosis in Spanish including identified root cause, evidence, confidence level (Alto/Medio/Bajo), false positive detection and immediate risk. "
                        "3. plan: A step-by-step numbered remediation plan in Spanish with priorities and assigned roles. "
                        "Ensure all fields are fully filled out in Spanish and accurately reflect the conversation."
                    )
                )
                from backend.ia.langchain_models import get_chat_model
                base_model = get_chat_model()
                structured_model = base_model.with_structured_output(ReactiveAnalysisOutput)
                
                # Build synthesis context: filter to human + AI messages only,
                # excluding large tool outputs to save tokens.
                synthesis_msgs = [
                    msg for msg in msgs
                    if getattr(msg, "type", "") in ("human", "ai")
                ]
                output = await structured_model.ainvoke(synthesis_msgs + [synthesis_msg])
                return output
            except Exception as e:
                logger.exception("Failed structured output synthesis, falling back to text parsing: %s", e)
                # Find the LAST AI/assistant message (not a tool message)
                raw_content = ""
                for msg in reversed(msgs):
                    msg_type = getattr(msg, "type", type(msg).__name__)
                    if msg_type in ("ai", "assistant"):
                        raw_content = getattr(msg, "content", "") or ""
                        break

                if not raw_content:
                    logger.warning("No AI message found in orchestrator response")
                    return None

                return self._parse_reactive_output(raw_content)

        except Exception as exc:
            logger.warning("Orchestrator failed: %s", exc)
            return None

    def _parse_reactive_output(self, raw: str) -> ReactiveAnalysisOutput | None:
        """Extract and validate ReactiveAnalysisOutput from raw text."""
        import re
        cleaned = raw.strip()

        # Try to extract JSON from markdown fences (anywhere in text)
        fence_match = re.search(
            r'```(?:json)?\s*\n(.*?)\n\s*```', cleaned, re.DOTALL
        )
        if fence_match:
            cleaned = fence_match.group(1).strip()
        elif cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines[0].strip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        try:
            return ReactiveAnalysisOutput.model_validate_json(cleaned)
        except Exception as exc:
            logger.warning("Failed to parse orchestrator output as ReactiveAnalysisOutput: %s. Raw: %s", exc, raw[:500])
            return None

    # ═══════════════════════════════════════════════════════════════════════════
    #  EMAIL NOTIFICATION (via MCP)
    # ═══════════════════════════════════════════════════════════════════════════

    async def _send_analysis_email(self, event: Event, session: AsyncSession) -> None:
        """Send the analysis results via Gmail MCP integration."""
        if not event.triggered_by_user_id:
            await self._emit_log(event.id, "No user_id for event; skipping email", level="warn")
            return

        try:
            from backend.integrations.models import IntegrationInstance
            from backend.integrations.integration_service import IntegrationService
            from backend.services.mcp_service import MCPService
            from sqlalchemy import select

            # Find user's Gmail integration
            stmt = select(IntegrationInstance).where(
                IntegrationInstance.user_id == event.triggered_by_user_id,
                IntegrationInstance.is_enabled.is_(True),
                IntegrationInstance.available_in_reactive.is_(True),
                IntegrationInstance.catalog_slug.in_(["gmail", "google", "google-mail"]),
            )
            result = await session.execute(stmt)
            instance = result.scalar_one_or_none()

            if not instance:
                await self._emit_log(event.id, "No Gmail integration found; skipping email", level="warn")
                return

            integration_service = IntegrationService(session)
            discovered = await integration_service._discover_tools(instance)
            send_email_tool = next(
                (t for t in discovered if t.get("name") == "send_email"), None
            )

            if not send_email_tool:
                await self._emit_log(event.id, "send_email tool not found in Gmail integration", level="warn")
                return

            # Build email body with the 3 outputs
            body = self._format_email_body(event)

            # Resolve recipient
            from backend.persistencia.models.user import User
            user = await session.get(User, event.triggered_by_user_id)
            recipient = user.notification_email if user and user.notification_email else user.email if user else None
            if not recipient:
                from backend.core.config import settings
                recipient = settings.REACTIVE_NOTIFICATION_EMAIL

            # Resolve OAuth credentials for stdio environment
            from backend.integrations.credentials import CredentialManager
            from backend.integrations.repositories.integration_repository import IntegrationInstanceRepository
            cred_manager = CredentialManager(IntegrationInstanceRepository(session))
            credentials = await cred_manager.get_credentials(instance)
            stdio_env = cred_manager.inject_for_stdio(
                credentials,
                instance.catalog.env_prefix if instance.catalog else "",
                base_env=dict(os.environ),
                auth_env_var_mapping=instance.catalog.auth_env_var_mapping if instance.catalog else None,
            )

            mcp_service = MCPService()
            response = await mcp_service.execute_tool(
                base_url=send_email_tool.get("config", {}).get("url", ""),
                tool_name="send_email",
                arguments={
                    "to": recipient,
                    "subject": f"[Aura AI] Event Analysis — {event.title}",
                    "body": body,
                },
                is_stdio=True,
                stdio_command=instance.catalog.command if instance.catalog else None,
                stdio_args=instance.catalog.args if instance.catalog else None,
                stdio_env=stdio_env,
                transport_type="stdio",
            )

            if response.error:
                await self._emit_log(event.id, f"Email send failed: {response.error}", level="error")
                logger.error("Email send failed for event %s: %s", event.id, response.error)
            else:
                await self._emit_log(event.id, f"Analysis email sent to {recipient}", level="info")
                logger.info("Analysis email sent for event %s to %s", event.id, recipient)

        except Exception as exc:
            logger.warning("Failed to send analysis email for event %s: %s", event.id, exc)
            await self._emit_log(event.id, f"Email send error: {exc}", level="warn")

    def _format_email_body(self, event: Event) -> str:
        """Format the analysis results into a plain-text email body."""
        return f"""Aura AI — Event Analysis Complete
=====================================

Event: {event.title}
Domain: {event.domain or 'generic'}
Severity: {event.severity_text}

── ANALYSIS ──
{event.agent_analysis or 'No analysis available.'}

── DIAGNOSIS ──
{event.agent_diagnosis or 'No diagnosis available.'}

── REMEDIATION PLAN ──
{event.agent_plan or 'No plan available.'}

---
Aura AI Operations Center
"""

    # ═══════════════════════════════════════════════════════════════════════════
    #  PRIVATE HELPERS
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_event_query(self, event: Event) -> str:
        payload_str = ""
        if event.body:
            payload_str = json.dumps(event.body, indent=2)
            MAX_PAYLOAD_CHARS = 8000
            if len(payload_str) > MAX_PAYLOAD_CHARS:
                payload_str = payload_str[:MAX_PAYLOAD_CHARS] + "\n... [truncated]"

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

    async def _resolve_db_connection_ids(
        self, session: AsyncSession, user_id: int | None
    ) -> list[str]:
        """Resolve active database connection IDs for the user in reactive context."""
        if user_id is None:
            return []
        try:
            from backend.database_connector.repository import DatabaseConnectionRepository

            repo = DatabaseConnectionRepository(session)
            connections = await repo.list_by_user(user_id, context="reactive")
            return [c.id for c in connections]
        except Exception as e:
            logger.warning("Failed to resolve DB connection IDs: %s", e)
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
