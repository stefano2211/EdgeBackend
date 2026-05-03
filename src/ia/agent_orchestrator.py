"""System 2 — Deep reasoning orchestrator.

When System 1 routes a request as 'complex', the orchestrator:
1. Uses LLM to generate an execution plan (JSON)
2. Dispatches subagents (RAG, MCP tools)
3. Synthesizes results into final streaming response
"""

import json
from typing import Any

from src.core.logging import logging
from src.ia.llm_client import get_llm_client
from src.ia.rag_tool import rag_retrieve

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Orchestrates complex multi-step reasoning tasks using LLM planning."""

    async def analyze(
        self,
        query: str,
        history: list[Any],
        available_tools: list[dict[str, Any]] | None = None,
        available_knowledge: list[str] | None = None,
    ) -> dict[str, Any]:
        """Ask LLM to generate a plan for handling a complex query."""
        try:
            llm = get_llm_client()
        except RuntimeError:
            logger.warning("LLM unavailable — falling back to simple plan")
            return self._fallback_plan(query, available_knowledge)

        tool_list = "\n".join(
            f"- {t.get('name', 'unknown')}: {t.get('description', '')}"
            for t in (available_tools or [])
        )
        kb_list = ", ".join(str(k) for k in (available_knowledge or []))

        plan_prompt = (
            "You are a planning agent. Given the user query and available resources, "
            "generate a JSON plan with the exact structure below. "
            "Do NOT include markdown formatting, only raw JSON.\n\n"
            f"Available tools:\n{tool_list or 'None'}\n\n"
            f"Available knowledge bases: {kb_list or 'None'}\n\n"
            f"User query: {query}\n\n"
            'Respond with JSON exactly in this format:\n'
            '{\n'
            '  "steps": [\n'
            '    {"action": "rag", "knowledge_base_id": "42", "description": "..."},\n'
            '    {"action": "tool", "tool_name": "...", "parameters": {...}},\n'
            '    {"action": "synthesize", "description": "..."}\n'
            '  ],\n'
            '  "requires_approval": false\n'
            '}\n'
            "Steps can include 'rag' (retrieve from knowledge base), "
            "'tool' (call an MCP tool), and 'synthesize' (generate final answer)."
        )

        try:
            resp = await llm.chat_completion(
                messages=[{"role": "system", "content": plan_prompt}],
                temperature=0.2,
                stream=False,
            )
            content = resp["choices"][0]["message"]["content"]
            # Strip possible markdown fences
            content = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            plan = json.loads(content)
            logger.info("Generated plan: %s", plan)
            return {
                "plan": plan,
                "subagents": [s["action"] for s in plan.get("steps", [])],
                "tools": available_tools or [],
                "requires_approval": plan.get("requires_approval", False),
            }
        except Exception as e:
            logger.exception("LLM plan generation failed: %s", e)
            return self._fallback_plan(query, available_knowledge)

    def _fallback_plan(self, query: str, available_knowledge: list[str] | None) -> dict:
        """Default plan when LLM is unavailable."""
        steps = []
        if available_knowledge:
            steps.append({
                "action": "rag",
                "knowledge_base_id": available_knowledge[0],
                "description": "Retrieve relevant documents",
            })
        steps.append({"action": "synthesize", "description": "Generate final response"})
        return {
            "plan": {"steps": steps, "requires_approval": False},
            "subagents": [s["action"] for s in steps],
            "tools": [],
            "requires_approval": False,
        }

    async def execute_plan(
        self,
        plan: dict[str, Any],
        messages: list[dict[str, str]],
        llm_stream_callback: Any | None = None,
    ) -> str:
        """
        Execute plan steps and return synthesized response.

        Currently supports: rag → synthesize.
        Tool dispatch (MCP) is stubbed for future phases.
        """
        steps = plan.get("plan", {}).get("steps", plan.get("steps", []))
        context_parts = []

        for step in steps:
            action = step.get("action")
            if action == "rag":
                kb_id = step.get("knowledge_base_id")
                query = messages[-1].get("content", "") if messages else ""
                rag_ctx = await rag_retrieve(kb_id, query, top_k=5)
                if rag_ctx:
                    context_parts.append(rag_ctx)
            elif action == "tool":
                # TODO: Dispatch MCP tool call
                logger.info("Tool dispatch stubbed: %s", step.get("tool_name"))
                context_parts.append(f"[Tool result for {step.get('tool_name')}: stub]")
            elif action == "synthesize":
                break  # Handled below

        # Build augmented messages for final LLM call
        augmented = messages.copy()
        if context_parts:
            ctx = "\n\n---\n\n".join(context_parts)
            user_msg = augmented[-1] if augmented and augmented[-1]["role"] == "user" else None
            if user_msg:
                user_msg["content"] = (
                    f"{ctx}\n\n---\n\n"
                    f"Answer the question using the context above.\n\n"
                    f"Question: {user_msg['content']}"
                )

        try:
            llm = get_llm_client()
            if llm_stream_callback:
                # Stream mode
                stream = await llm.chat_completion(
                    messages=augmented,
                    temperature=0.7,
                    stream=True,
                )
                full = ""
                async for chunk in stream:
                    choices = chunk.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    if "content" in delta and delta["content"]:
                        token = delta["content"]
                        full += token
                        await llm_stream_callback(token)
                return full
            else:
                # Non-stream
                resp = await llm.chat_completion(
                    messages=augmented,
                    temperature=0.7,
                    stream=False,
                )
                return resp["choices"][0]["message"]["content"]
        except Exception as e:
            logger.exception("Orchestrator execution failed: %s", e)
            return "[System 2 processing failed — falling back to simple response]"
