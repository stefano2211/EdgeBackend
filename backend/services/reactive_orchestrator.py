"""Reactive event pipeline — sequential 4-phase analysis with Director-Analyst split.

Architecture:
  1. Event arrives → status "analyzing"
  2. Director (DeepAgent) collects data from sub-agents in sequence:
     Phase 1: db_analyst-agent queries last N hours of data
     Phase 2: rag-agent searches docs using event + DB context
     Phase 3: mcp-agent sends quick alerts and collects integration data
  3. Analyst (separate LLM call) cross-checks findings → structured JSON
  4. Fields saved to event → email sent with real analysis → status "completed"
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
                session=session,
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

            # ── Send analysis email with the REAL Analyst output ──
            await self._send_analysis_result(event, output, session)

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

    # ═══════════════════════════════════════════════════════════════════════════
    #  ORCHESTRATOR PHASE
    # ═══════════════════════════════════════════════════════════════════════════

    async def _run_orchestrator(
        self,
        event: Event,
        session: AsyncSession,
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
            "Execute the sequential pipeline in your system prompt. "
            "Start with Phase 1 (database query), then Phase 2 (document search), "
            "then Phase 3 (external actions if tools are available). "
            "After all phases, report what data was collected from each phase. "
            "Execute each phase in strict order — do NOT call multiple agents at the same time."
        )

        thread_id = f"event-{event.id}-s2"
        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": 20,  # margin for 3 sub-agents + synthesis + MCP actions
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
                    elif agent_name == "db_analyst-agent":
                        await self._emit("db_analyst_result", event.id, {"result": str(msg.content)})
                        await self._emit_log(event.id, "DB analysis received", level="info")

            if not msgs:
                logger.warning("Orchestrator returned no messages")
                return None

            # ── Stage 2: Synthesis Analyst (cross-check + structured JSON) ──
            await self._emit_log(event.id, "Director complete — running Synthesis Analyst...", level="info")
            return await self._run_analyst(event, event_query, msgs)

        except Exception as exc:
            logger.warning("Orchestrator failed: %s", exc)
            return None

    async def _run_analyst(
        self,
        event: Event,
        event_query: str,
        director_messages: list,
    ) -> ReactiveAnalysisOutput | None:
        """Run the Synthesis Analyst to cross-check findings and produce structured JSON."""
        try:
            from langchain_core.messages import SystemMessage, HumanMessage
            from backend.ia.langchain_models import get_chat_model
            from backend.ia.prompts.reactive import build_synthesis_analyst_prompt

            # Extract sub-agent findings from Director conversation
            subagent_findings = self._extract_subagent_findings(director_messages)

            # Build the Analyst system prompt with cross-check rules
            analyst_system = build_synthesis_analyst_prompt(
                event_context=event_query,
                subagent_findings=subagent_findings,
            )

            base_model = get_chat_model()
            structured_model = base_model.with_structured_output(ReactiveAnalysisOutput)

            # Filter to human + AI messages for context (exclude large tool outputs)
            context_msgs = [
                msg for msg in director_messages
                if getattr(msg, "type", "") in ("human", "ai")
            ]

            analyst_messages = [
                SystemMessage(content=analyst_system),
                HumanMessage(content=(
                    "Cross-check the event claims against sub-agent findings below. "
                    "Produce the structured JSON using your cross-check rules."
                )),
            ]

            output = await structured_model.ainvoke(context_msgs + analyst_messages)
            return output

        except Exception as e:
            logger.exception("Synthesis Analyst failed: %s", e)
            # Fallback: try parsing from Director's final message
            raw_content = ""
            for msg in reversed(director_messages):
                msg_type = getattr(msg, "type", type(msg).__name__)
                if msg_type in ("ai", "assistant"):
                    raw_content = getattr(msg, "content", "") or ""
                    break
            if not raw_content:
                return None
            return self._parse_reactive_output(raw_content)

    def _extract_subagent_findings(self, messages: list) -> str:
        """Extract a comprehensive summary of what each sub-agent returned.

        Includes: Director's final summary + structured data from each sub-agent.
        Preserves full data content — no arbitrary character truncation.
        """
        parts: list[str] = []

        # 1. Director's final summary (last AI message — has interpreted context)
        for msg in reversed(messages):
            msg_type = getattr(msg, "type", "")
            if msg_type in ("ai", "assistant"):
                content = str(getattr(msg, "content", "")).strip()
                if content:
                    parts.insert(0, f"=== DIRECTOR SUMMARY ===\n{content}")
                    break

        # 2. Tool outputs from sub-agents — extract structured data
        for msg in messages:
            msg_type = getattr(msg, "type", "")
            if msg_type != "tool":
                continue

            agent_name = getattr(msg, "name", "") or "unknown"
            content = str(getattr(msg, "content", "") or "")
            if not content.strip():
                continue

            header = f"=== {agent_name} ==="

            # Try to parse JSON and extract key structured fields
            try:
                import json as _json
                data = _json.loads(content)
                if isinstance(data, dict):
                    summary = data.get("executive_summary", "")
                    status = data.get("task_status", "")
                    header = f"=== {agent_name} (status: {status}) ==="

                    # For RAG agent: extract citations with extracted_text
                    if "rag_data" in data:
                        rag_parts = [header]
                        if summary:
                            rag_parts.append(f"Summary: {summary}")
                        citations = data.get("rag_data", [])
                        for c in citations[:5]:  # max 5 queries
                            query = c.get("query", "")
                            rag_parts.append(f"\nQuery: {query}")
                            for cit in c.get("citations", [])[:5]:
                                src = cit.get("source", "?")
                                relevance = cit.get("relevance", "?")
                                text = cit.get("extracted_text", "")[:500]
                                rag_parts.append(
                                    f"  [{src} relevance={relevance}]\n  {text}"
                                )
                        parts.append("\n".join(rag_parts))

                    # For MCP agent: extract action results
                    elif "data" in data and isinstance(data["data"], dict):
                        inner = data["data"]
                        result = inner.get("result", {})
                        parts.append(
                            f"{header}\n"
                            f"Action: {inner.get('source', '?')}\n"
                            f"Result: {_json.dumps(result, ensure_ascii=False)[:1000]}\n"
                            f"Summary: {summary}"
                        )

                    # For DB analyst or plain JSON
                    else:
                        inner_data = data.get("data", {})
                        if isinstance(inner_data, dict):
                            results = inner_data.get("results", {})
                            sql = inner_data.get("sql", "")
                            insights = inner_data.get("insights", "")
                            row_count = results.get("row_count", 0) if isinstance(results, dict) else 0
                            parts.append(
                                f"{header}\n"
                                f"Summary: {summary}\n"
                                f"SQL: {sql}\n"
                                f"Rows: {row_count}\n"
                                f"Insights: {insights}"
                            )
                        else:
                            parts.append(f"{header}\n{_json.dumps(data, ensure_ascii=False)[:3000]}")
                else:
                    parts.append(f"{header}\n{content[:3000]}")

            except (ValueError, TypeError):
                # Not JSON — keep as plain text (e.g., markdown tables from query_resource_data)
                # No truncation: the Analyst needs the full data
                parts.append(f"{header}\n{content}")

        if not parts:
            return "No sub-agent data was collected."

        return "\n\n".join(parts)

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

    async def _send_analysis_result(
        self, event: Event, output: ReactiveAnalysisOutput, session: AsyncSession
    ) -> None:
        """Send the Analyst's real analysis/diagnosis/plan via email — same content as frontend."""
        if not event.triggered_by_user_id:
            return

        try:
            from sqlalchemy import select
            from backend.integrations.models import IntegrationInstance
            from backend.integrations.integration_service import IntegrationService
            from backend.services.mcp_service import MCPService
            from backend.integrations.credentials import CredentialManager
            from backend.integrations.repositories.integration_repository import IntegrationInstanceRepository

            stmt = select(IntegrationInstance).where(
                IntegrationInstance.user_id == event.triggered_by_user_id,
                IntegrationInstance.is_enabled.is_(True),
            )
            result = await session.execute(stmt)
            instances = result.scalars().all()

            integration_service = IntegrationService(session)
            gmail_instance = None
            send_email_tool = None

            for instance in instances:
                if instance.catalog and instance.catalog.slug in ("gmail", "google", "google-mail"):
                    discovered = await integration_service._discover_tools(instance)
                    send_email_tool = next(
                        (t for t in discovered if t.get("name") == "send_email"), None
                    )
                    if send_email_tool:
                        gmail_instance = instance
                        break

            if not gmail_instance or not send_email_tool:
                logger.info("No Gmail integration with send_email tool found — skipping email")
                return

            body = (
                f"Aura AI — Event Analysis Complete\n"
                f"=====================================\n\n"
                f"Event: {event.title}\n"
                f"Severity: {event.severity_text}\n"
                f"Domain: {event.domain or 'generic'}\n\n"
                f"── ANALYSIS ──\n"
                f"{output.analysis}\n\n"
                f"── DIAGNOSIS ──\n"
                f"{output.diagnosis}\n\n"
                f"── REMEDIATION PLAN ──\n"
                f"{output.plan}\n\n"
                f"---\n"
                f"Aura AI Operations Center"
            )

            from backend.persistencia.models.user import User
            user = await session.get(User, event.triggered_by_user_id)
            recipient = (
                user.notification_email if user and user.notification_email
                else user.email if user
                else None
            )
            if not recipient:
                logger.warning("No recipient found for event %s", event.id)
                return

            cred_manager = CredentialManager(IntegrationInstanceRepository(session))
            credentials = await cred_manager.get_credentials(gmail_instance)
            stdio_env = cred_manager.inject_for_stdio(
                credentials,
                gmail_instance.catalog.env_prefix if gmail_instance.catalog else "",
                base_env=dict(os.environ),
                auth_env_var_mapping=(
                    gmail_instance.catalog.auth_env_var_mapping
                    if gmail_instance.catalog else None
                ),
            )

            mcp_service = MCPService()
            response = await mcp_service.execute_tool(
                base_url=send_email_tool.get("config", {}).get("url", ""),
                tool_name="send_email",
                arguments={
                    "to": recipient,
                    "subject": f"[Aura AI] {event.title}",
                    "body": body,
                },
                is_stdio=True,
                stdio_command=gmail_instance.catalog.command if gmail_instance.catalog else None,
                stdio_args=gmail_instance.catalog.args if gmail_instance.catalog else None,
                stdio_env=stdio_env,
                transport_type="stdio",
            )

            if response.error:
                logger.warning("Email send failed for event %s: %s", event.id, response.error)
                await self._emit_log(event.id, f"Email send failed: {response.error}", level="warn")
            else:
                logger.info("Analysis email sent for event %s to %s", event.id, recipient)
                await self._emit_log(event.id, f"Analysis email sent to {recipient}", level="info")

        except Exception as exc:
            logger.warning("Failed to send analysis email for event %s: %s", event.id, exc)

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
