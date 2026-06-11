"""MCP Service — execution for registered MCP tools.

Replicated from IndustrialBackend with EdgeBackend adaptations:
- Uses src.core.logging instead of loguru
- Uses src.services.mcp_schemas for response models

NOTE: Auto-discovery (AI REST Bridge, LLM-powered endpoint analysis,
filterable schema extraction) has been removed. Tools must be registered
manually via the API or database.
"""

from __future__ import annotations

import asyncio
import json
import random
import re
import time as _time
from typing import Any, Dict, List, Optional

import httpx

from backend.core.logging import logging
from backend.services.mcp_schemas import MCPResponse, KeyFigure, KeyValue

logger = logging.getLogger(__name__)

# Lazy imports for optional MCP SDK (will fail gracefully if not installed)
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.client.sse import sse_client

    _MCP_SDK_AVAILABLE = True
except Exception:
    _MCP_SDK_AVAILABLE = False
    logger.warning("mcp SDK not installed. stdio/sse transport will not be available.")


class MCPService:
    """
    Service for MCP tool execution.
    Supports stdio, SSE, and REST transports with retry logic.
    """

    # Cache for stdio sessions: key -> {session, client_ctx, session_ctx, last_used}
    _stdio_cache: dict = {}
    _stdio_cache_lock = asyncio.Lock()
    _STDIO_TTL = 300  # 5 minutes

    def __init__(self) -> None:
        pass

    @classmethod
    def _stdio_cache_key(cls, server_params: StdioServerParameters) -> tuple:
        env_hash = None
        if server_params.env:
            env_hash = hash(frozenset(server_params.env.items()))
        return (server_params.command, tuple(server_params.args or []), env_hash)

    @classmethod
    async def _get_stdio_session(cls, server_params: StdioServerParameters):
        """Get or create a cached stdio session."""
        if not _MCP_SDK_AVAILABLE:
            raise RuntimeError("mcp SDK not installed")

        cache_key = cls._stdio_cache_key(server_params)
        async with cls._stdio_cache_lock:
            now = _time.time()

            # Remove expired entries
            expired = [
                k for k, v in list(cls._stdio_cache.items())
                if now - v["last_used"] > cls._STDIO_TTL
            ]
            for k in expired:
                entry = cls._stdio_cache.pop(k)
                try:
                    await entry["session_ctx"].__aexit__(None, None, None)
                except Exception:
                    pass
                try:
                    await entry["client_ctx"].__aexit__(None, None, None)
                except Exception:
                    pass
                logger.info("[MCP Service] Expired stdio session removed: %s", k)

            if cache_key in cls._stdio_cache:
                entry = cls._stdio_cache[cache_key]
                entry["last_used"] = now
                logger.debug("[MCP Service] Reusing cached stdio session: %s", cache_key)
                return entry["session"]

            # Create new session
            client_ctx = stdio_client(server_params)
            read, write = await client_ctx.__aenter__()
            session_ctx = ClientSession(read, write)
            session = await session_ctx.__aenter__()
            await session.initialize()

            cls._stdio_cache[cache_key] = {
                "client_ctx": client_ctx,
                "session_ctx": session_ctx,
                "session": session,
                "last_used": now,
            }
            logger.info("[MCP Service] New stdio session created and cached: %s", cache_key)
            return session

    # ------------------------------------------------------------------
    # Filter application: pure Python, no LLM, applied before mapping
    # ------------------------------------------------------------------

    def _get_nested_value(self, record: dict, key: str) -> Any:
        """Retrieve a value from a dot-notated nested path case-insensitively."""
        keys = key.replace("[]", "").split(".")
        current = record
        for k in keys:
            if isinstance(current, list):
                current = current[0] if current else None
            if isinstance(current, dict):
                res = current.get(k)
                if res is not None:
                    current = res
                    continue
                # Fallback: case-insensitive match
                k_lower = k.lower()
                matched = False
                for dict_k, dict_v in current.items():
                    if str(dict_k).lower() == k_lower:
                        current = dict_v
                        matched = True
                        break
                if not matched:
                    return None
            else:
                return None
        return current

    def _apply_filters(
        self,
        data: list,
        key_values_filter: Optional[Dict[str, List[str]]] = None,
        key_figures_filter: Optional[List[Dict]] = None,
    ) -> list:
        """Applies categorical and numeric range filters BEFORE mapping."""
        if not data:
            return data

        kv_filters = {k: [str(v).lower() for v in vs] for k, vs in (key_values_filter or {}).items() if vs}
        kf_filters = [f for f in (key_figures_filter or []) if f.get("field")]

        if not kv_filters and not kf_filters:
            return data

        # Validation: check requested fields exist
        all_sample_keys = set()
        for r in data[:5]:
            if isinstance(r, dict):
                all_sample_keys.update(r.keys())

        missing_fields = []
        for f in kv_filters.keys():
            if not any(str(k).lower() == f.lower() for k in all_sample_keys):
                missing_fields.append(f)
        for flt in kf_filters:
            f = flt["field"]
            if not any(str(k).lower() == f.lower() for k in all_sample_keys):
                missing_fields.append(f)

        if missing_fields:
            available = sorted(list(all_sample_keys))
            raise ValueError(
                f"Filter error: Field(s) {missing_fields} not found in dataset. "
                f"Available fields for filtering are: {available}. "
                f"Please update your tool call arguments using these exact names."
            )

        filtered = []
        for record in data:
            match = True

            # Categorical filters
            for field, allowed_values in kv_filters.items():
                val = self._get_nested_value(record, field)
                if val is None:
                    match = False
                    break
                val_str = str(val).lower()
                if val_str not in allowed_values:
                    match = False
                    break

            if not match:
                continue

            # Numeric range filters
            for flt in kf_filters:
                field = flt["field"]
                val = self._get_nested_value(record, field)
                if val is None or not isinstance(val, (int, float)):
                    match = False
                    break
                min_val = flt.get("min")
                max_val = flt.get("max")
                if min_val is not None and val < min_val:
                    match = False
                    break
                if max_val is not None and val > max_val:
                    match = False
                    break

            if match:
                filtered.append(record)

        logger.info(
            "[MCP Service] Filters applied: %d -> %d records (kv=%s, kf=%s)",
            len(data),
            len(filtered),
            list(kv_filters.keys()),
            [f["field"] for f in kf_filters],
        )
        return filtered

    # ------------------------------------------------------------------
    # Response mapping
    # ------------------------------------------------------------------

    async def _auto_map_response(
        self, source: str, data: Any, schema_hints: Optional[dict] = None
    ) -> MCPResponse:
        """Maps a JSON payload to KeyFigures and KeyValues."""
        response = MCPResponse(source=source)

        if isinstance(data, list):
            if not data:
                response.key_values.append(KeyValue(name="raw_data", value="[]"))
                return response

            if all(isinstance(item, dict) for item in data):
                subset = data[:50]
                json_str = json.dumps(subset, separators=(",", ":"), ensure_ascii=False)
                response.key_values.append(KeyValue(name="json_records", value=json_str))
                return response
            else:
                response.key_values.append(
                    KeyValue(name="items", value=", ".join(str(v) for v in data[:20]))
                )
                return response

        if not isinstance(data, dict):
            response.key_values.append(KeyValue(name="raw_data", value=str(data)))
            return response

        def process_dict(d: dict, prefix: str = "", depth: int = 0) -> None:
            for key, val in d.items():
                name = f"{prefix}{key}" if prefix else key
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    response.key_figures.append(KeyFigure(name=name, value=float(val)))
                elif isinstance(val, dict) and depth < 3:
                    process_dict(val, f"{name}.", depth + 1)
                elif isinstance(val, list):
                    if len(val) > 0:
                        if isinstance(val[0], (str, int, float)):
                            response.key_values.append(
                                KeyValue(name=name, value=", ".join(map(str, val[:15])))
                            )
                        elif isinstance(val[0], dict) and depth < 2:
                            flat = []
                            for item in val[:15]:
                                if not isinstance(item, dict):
                                    continue
                                candidate = item.get("name")
                                if candidate is None:
                                    for v in item.values():
                                        if isinstance(v, (str, int, float)) and v is not None:
                                            candidate = v
                                            break
                                if candidate is not None:
                                    flat.append(str(candidate))
                            if flat:
                                response.key_values.append(KeyValue(name=name, value=", ".join(flat)))
                elif val is not None and not isinstance(val, bool):
                    response.key_values.append(KeyValue(name=name, value=str(val)))

        process_dict(data)

        if schema_hints:
            response = self._filter_response(response, schema_hints)

        return response

    def _filter_response(self, response: MCPResponse, schema_hints: dict) -> MCPResponse:
        """Filters MCPResponse using response schema hints."""
        if not schema_hints:
            return response

        hint_keys = {k.lower().replace("_", "").replace(" ", "") for k in schema_hints.keys()}

        def _matches_hint(name: str) -> bool:
            parts = name.lower().replace(" ", "").replace("_", "").split(".")
            return any(p in hint_keys or any(h in p for h in hint_keys) for p in parts)

        filtered = MCPResponse(source=response.source)
        filtered.key_figures = [kf for kf in response.key_figures if _matches_hint(kf.name)]
        filtered.key_values = [kv for kv in response.key_values if _matches_hint(kv.name)]

        if not filtered.key_figures and not filtered.key_values:
            logger.info(
                "[MCP Service] Schema filter removed everything for %s, using top-20 unfiltered.",
                response.source,
            )
            filtered.key_figures = response.key_figures[:10]
            filtered.key_values = response.key_values[:10]

        return filtered

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    @staticmethod
    def _is_transient_error(exc: Exception) -> bool:
        """Classify whether an error is transient (retryable)."""
        if isinstance(exc, (ConnectionError, TimeoutError, asyncio.TimeoutError)):
            return True
        if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code >= 500:
            return True
        if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
            return True
        error_msg = str(exc).lower()
        if any(kw in error_msg for kw in ("connection", "timeout", "reset", "broken pipe", "eof")):
            return True
        return False

    async def execute_tool(
        self,
        base_url: str,
        tool_name: str,
        arguments: Dict[str, Any],
        is_stdio: bool = False,
        stdio_command: str | None = None,
        stdio_args: list[str] | None = None,
        stdio_env: dict[str, str] | None = None,
        transport_type: str = "mcp",
        method: str = "GET",
        schema_hints: Optional[dict] = None,
        key_values_filter: Optional[Dict[str, List[str]]] = None,
        key_figures_filter: Optional[List[Dict]] = None,
    ) -> MCPResponse:
        """
        Dynamically connects to an MCP server, calls a tool, and maps the result.
        """
        logger.info(
            "[MCP Service] Executing tool '%s' (%s) on %s using %s",
            tool_name,
            transport_type,
            base_url,
            method,
        )

        max_attempts = 3
        last_exc = None

        for attempt in range(1, max_attempts + 1):
            try:
                if transport_type == "rest":
                    async with httpx.AsyncClient() as client:
                        method = method.upper()
                        target_url = base_url

                        # URL Parameter Substitution
                        url_params = re.findall(r"\{(.*?)\}", target_url)
                        remaining_args = arguments.copy()

                        for p in url_params:
                            if p in remaining_args:
                                val = str(remaining_args.pop(p))
                                target_url = target_url.replace(f"{{{p}}}", val)
                            else:
                                logger.warning("[MCP Service] Missing URL parameter '%s' for %s", p, base_url)

                        logger.info("[MCP Service] Final target URL: %s", target_url)

                        if method == "GET":
                            response = await client.get(target_url, params=remaining_args, timeout=30.0)
                        else:
                            response = await client.request(
                                method, target_url, json=remaining_args, timeout=30.0
                            )

                        response.raise_for_status()
                        raw_data = response.json()

                        # Pre-filter BEFORE mapping
                        if isinstance(raw_data, list) and (key_values_filter or key_figures_filter):
                            raw_data = self._apply_filters(raw_data, key_values_filter, key_figures_filter)

                        return await self._auto_map_response(tool_name, raw_data, schema_hints=schema_hints)

                if not _MCP_SDK_AVAILABLE:
                    return MCPResponse(
                        source=tool_name,
                        error="mcp SDK not installed. Cannot use stdio/sse transport.",
                    )

                if is_stdio:
                    server_params = StdioServerParameters(
                        command=stdio_command or "python",
                        args=stdio_args or [base_url],
                        env=stdio_env,
                    )
                    session = await self._get_stdio_session(server_params)
                    try:
                        result = await session.call_tool(tool_name, arguments)
                    except Exception as call_exc:
                        # Session may be stale — invalidate and retry once
                        logger.warning(
                            "[MCP Service] Cached stdio session failed for '%s': %s. Recreating...",
                            tool_name, call_exc,
                        )
                        cache_key = self._stdio_cache_key(server_params)
                        async with self._stdio_cache_lock:
                            if cache_key in self._stdio_cache:
                                entry = self._stdio_cache.pop(cache_key)
                                try:
                                    await entry["session_ctx"].__aexit__(None, None, None)
                                except Exception:
                                    pass
                                try:
                                    await entry["client_ctx"].__aexit__(None, None, None)
                                except Exception:
                                    pass
                        session = await self._get_stdio_session(server_params)
                        result = await session.call_tool(tool_name, arguments)

                    content = result.content[0].text if result.content else "{}"
                    try:
                        data = json.loads(content)
                    except Exception:
                        data = {"text": content}
                    # MCP native: preserve raw JSON for LLM consumption
                    response = MCPResponse(
                        source=tool_name,
                        raw_response=data if isinstance(data, dict) else {"result": data},
                    )
                    # Also populate legacy key_figures/key_values for backward compat
                    auto_mapped = await self._auto_map_response(tool_name, data)
                    response.key_figures = auto_mapped.key_figures
                    response.key_values = auto_mapped.key_values
                    return response
                else:
                    async with sse_client(base_url) as (read, write):
                        async with ClientSession(read, write) as session:
                            await session.initialize()
                            result = await session.call_tool(tool_name, arguments)
                            content = result.content[0].text if result.content else "{}"
                            try:
                                data = json.loads(content)
                            except Exception:
                                data = {"text": content}
                            # MCP native: preserve raw JSON for LLM consumption
                            response = MCPResponse(
                                source=tool_name,
                                raw_response=data if isinstance(data, dict) else {"result": data},
                            )
                            # Also populate legacy key_figures/key_values for backward compat
                            auto_mapped = await self._auto_map_response(tool_name, data)
                            response.key_figures = auto_mapped.key_figures
                            response.key_values = auto_mapped.key_values
                            return response

            except (json.JSONDecodeError, ValueError) as e:
                # Non-transient: fail immediately
                logger.error("[MCP Service] Data parsing failed: %s", str(e))
                return MCPResponse(source=tool_name, error=f"Parse error: {e}")
            except Exception as e:
                last_exc = e
                if attempt < max_attempts and self._is_transient_error(e):
                    delay = (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                    logger.warning(
                        "[MCP Service] Transient error on attempt %d/%d for '%s': %s. Retrying in %.1fs...",
                        attempt, max_attempts, tool_name, e, delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                logger.error("[MCP Service] Execution failed: %s", str(e))
                return MCPResponse(source=tool_name, error=str(e))

        logger.error("[MCP Service] All %d attempts failed for '%s'", max_attempts, tool_name)
        return MCPResponse(source=tool_name, error=f"Failed after {max_attempts} attempts: {last_exc}")
