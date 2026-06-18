import json
from typing import Any, Callable, Awaitable
from backend.core.logging import logging
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelRequest, ModelResponse, ExtendedModelResponse
from langchain_core.messages import AIMessage

logger = logging.getLogger(__name__)


class PreventSubagentLoopMiddleware(AgentMiddleware):
    """Middleware to prevent the orchestrator from calling the same subagent multiple times.

    If the orchestrator tries to spawn a subagent that has already been invoked in the
    conversation history, this middleware intercepts the model response, strips the duplicate
    tool call, and stops the tool execution loop if no other tool calls remain.
    """

    def wrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], ModelResponse[Any] | AIMessage | ExtendedModelResponse[Any]],
    ) -> ModelResponse[Any] | AIMessage | ExtendedModelResponse[Any]:
        called = self._find_called_subagents(request.messages)
        response = handler(request)
        self._apply_loop_prevention(response, called)
        return response

    async def awrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], Awaitable[ModelResponse[Any] | AIMessage | ExtendedModelResponse[Any]]],
    ) -> ModelResponse[Any] | AIMessage | ExtendedModelResponse[Any]:
        called = self._find_called_subagents(request.messages)
        response = await handler(request)
        self._apply_loop_prevention(response, called)
        return response

    # ── Shared helpers ──

    @staticmethod
    def _find_called_subagents(messages: list) -> set[str]:
        """Scan message history for all subagent task() calls already made."""
        called: set[str] = set()
        for msg in messages:
            if not hasattr(msg, "tool_calls") or not msg.tool_calls:
                continue
            for tc in msg.tool_calls:
                if tc.get("name") != "task":
                    continue
                args = tc.get("args") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except (json.JSONDecodeError, TypeError):
                        continue
                if isinstance(args, dict):
                    sub_type = args.get("subagent_type")
                    if sub_type:
                        called.add(sub_type)
        return called

    @staticmethod
    def _process_duplicates(ai_msg: AIMessage, called: set[str]) -> None:
        """Strip duplicate tool calls from the AI message in-place."""
        if not getattr(ai_msg, "tool_calls", None):
            return

        new_tool_calls: list[dict] = []
        has_duplicate = False
        for tc in ai_msg.tool_calls:
            if tc.get("name") == "task":
                args = tc.get("args") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except (json.JSONDecodeError, TypeError):
                        pass
                if isinstance(args, dict):
                    sub_type = args.get("subagent_type")
                    if sub_type in called:
                        has_duplicate = True
                        logger.warning(
                            "Loop prevention: intercepted duplicate subagent call to %s", sub_type
                        )
                        continue
            new_tool_calls.append(tc)

        if has_duplicate:
            ai_msg.tool_calls = new_tool_calls
            if "tool_calls" in ai_msg.additional_kwargs:
                raw_tc = ai_msg.additional_kwargs["tool_calls"]
                if isinstance(raw_tc, list):
                    new_ids = {tc.get("id") for tc in new_tool_calls if tc.get("id")}
                    filtered_raw = [
                        rtc for rtc in raw_tc
                        if isinstance(rtc, dict) and rtc.get("id") in new_ids
                    ]
                    if filtered_raw:
                        ai_msg.additional_kwargs["tool_calls"] = filtered_raw
                    else:
                        ai_msg.additional_kwargs.pop("tool_calls", None)

            if not new_tool_calls:
                ai_msg.content = (
                    "El subagente ya ha sido invocado previamente en esta conversacion. "
                    "Para evitar bucles redundantes, finalizo la recopilacion de datos y procedo "
                    "a consolidar el informe final en espanol."
                )

    def _apply_loop_prevention(
        self,
        response: ModelResponse[Any] | AIMessage | ExtendedModelResponse[Any],
        called: set[str],
    ) -> None:
        """Extract the AIMessage from various response types and apply duplicate filtering."""
        if isinstance(response, AIMessage):
            self._process_duplicates(response, called)
        elif isinstance(response, ModelResponse):
            if response.result:
                self._process_duplicates(response.result[0], called)
        elif isinstance(response, ExtendedModelResponse):
            if response.model_response and response.model_response.result:
                self._process_duplicates(response.model_response.result[0], called)
