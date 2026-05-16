"""MCP Service — dynamic tool discovery and execution for external APIs.

Replicated from IndustrialBackend with EdgeBackend adaptations:
- Uses src.core.logging instead of loguru
- Uses src.ia.langchain_models for LLM bridge discovery
- Uses src.services.mcp_schemas for response models
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Dict, List, Optional

import httpx

from src.core.config import settings
from src.core.logging import logging
from src.services.mcp_schemas import MCPResponse, KeyFigure, KeyValue

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
    Service for dynamic MCP tool discovery and execution.
    Implements the 'Zero-Config' pattern with intelligent pre-filtering.
    """

    def __init__(self) -> None:
        pass

    # ------------------------------------------------------------------
    # Schema extraction: discover filterable fields from a list of records
    # ------------------------------------------------------------------

    def _extract_filterable_schema(self, data: list) -> dict:
        """
        Scans a list of records and returns:
          {
            "key_figures": ["field1", ...],
            "key_values": {"field": ["v1","v2"], ...}
          }
        """
        figures: set = set()
        values: dict = {}

        def _scan(record: dict, prefix: str = "") -> None:
            for key, val in record.items():
                full_key = f"{prefix}{key}" if prefix else key
                if isinstance(val, dict):
                    _scan(val, f"{full_key}.")
                elif isinstance(val, list):
                    if val and isinstance(val[0], dict):
                        _scan(val[0], f"{full_key}[].")
                    elif val and all(isinstance(v, str) for v in val):
                        existing = values.setdefault(full_key, set())
                        existing.update(val)
                elif isinstance(val, (int, float)) and not isinstance(val, bool):
                    figures.add(full_key)
                elif isinstance(val, str) and val:
                    existing = values.setdefault(full_key, set())
                    existing.add(val)

        for record in data:
            if isinstance(record, dict):
                _scan(record)

        return {
            "key_figures": sorted(figures),
            "key_values": {k: sorted(v) for k, v in values.items() if v},
        }

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

    async def execute_tool(
        self,
        base_url: str,
        tool_name: str,
        arguments: Dict[str, Any],
        is_stdio: bool = False,
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
                server_params = StdioServerParameters(command="python", args=[base_url])
                async with stdio_client(server_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        result = await session.call_tool(tool_name, arguments)
                        return await self._auto_map_response(tool_name, result.content)
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
                        return await self._auto_map_response(tool_name, data)

        except httpx.HTTPError as e:
            logger.error("[MCP Service] HTTP execution failed: %s", str(e))
            return MCPResponse(source=tool_name, error=f"HTTP error: {e}")
        except (json.JSONDecodeError, ValueError) as e:
            logger.error("[MCP Service] Data parsing failed: %s", str(e))
            return MCPResponse(source=tool_name, error=f"Parse error: {e}")
        except Exception as e:
            logger.error("[MCP Service] Execution failed: %s", str(e))
            return MCPResponse(source=tool_name, error=str(e))

    # ------------------------------------------------------------------
    # LLM Bridge helper
    # ------------------------------------------------------------------

    async def _analyze_with_llm(self, prompt: str) -> Optional[dict]:
        """Call a local LLM via LLMClient for REST API analysis. Returns parsed JSON or None."""
        try:
            from src.ia.llm_client import get_llm_client

            client = get_llm_client()
            response = await client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                stream=False,
                temperature=0,
                max_tokens=1000,
                response_format={"type": "json_object"},
            )

            # Parse OpenAI-compatible response format
            choices = response.get("choices", [])
            raw = ""
            if choices:
                raw = choices[0].get("message", {}).get("content", "").strip()

            # Strip think tags and markdown fences
            raw = re.sub(r"\s*<think>.*?</think>\s*", "", raw, flags=re.DOTALL)
            raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
            raw = re.sub(r"```\s*$", "", raw, flags=re.MULTILINE).strip()

            if raw:
                return json.loads(raw)
        except (httpx.HTTPError, json.JSONDecodeError, ValueError) as e:
            logger.warning("[MCP Service] LLM analysis failed: %s", e)
        except Exception as e:
            logger.warning("[MCP Service] LLM analysis unexpected error: %s", e)
        return None

    # ------------------------------------------------------------------
    # Tool discovery
    # ------------------------------------------------------------------

    async def discover_tools(
        self,
        base_url: str,
        is_stdio: bool = False,
        is_resource: bool = False,
        method: str = "GET",
    ) -> List[Dict[str, Any]]:
        """
        Lists tools from an MCP server for dynamic registration.
        Supports Hybrid Discovery: Native MCP -> AI REST Bridge.
        """
        method = method.upper()

        if not _MCP_SDK_AVAILABLE:
            raise RuntimeError("mcp SDK not installed. Cannot discover via stdio/sse.")

        try:
            if is_stdio:
                server_params = StdioServerParameters(command="python", args=[base_url])
                async with stdio_client(server_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        tools_result = await session.list_tools()
                        return [t.model_dump() for t in tools_result.tools]
            else:
                last_err = None
                for attempt, delay in enumerate([2, 4, 8], start=1):
                    try:
                        async with sse_client(base_url) as (read, write):
                            async with ClientSession(read, write) as session:
                                await session.initialize()
                                tools_result = await session.list_tools()
                                return [t.model_dump() for t in tools_result.tools]
                    except Exception as sse_err:
                        last_err = sse_err
                        error_msg = str(sse_err).lower()
                        if isinstance(sse_err, BaseExceptionGroup):
                            error_msg = " ".join(str(e).lower() for e in sse_err.exceptions)
                        if "name resolution" in error_msg or "getaddrinfo" in error_msg or "connection" in error_msg:
                            if attempt < 3:
                                logger.warning(
                                    "[MCP Service] Discovery attempt %s/%s failed for %s: %s. Retrying in %ss...",
                                    attempt, 3, base_url, error_msg, delay,
                                )
                                await asyncio.sleep(delay)
                                continue
                        if "text/event-stream" in error_msg or "404" in error_msg or "405" in error_msg:
                            logger.info(
                                "[MCP Service] Protocol mismatch on %s, triggering AI Bridge (method=%s)...",
                                base_url,
                                method,
                            )
                            return await self._discover_rest_bridge(
                                base_url, is_resource=is_resource, method=method
                            )
                        raise sse_err
                raise last_err
        except RuntimeError:
            raise
        except httpx.HTTPError as e:
            error_msg = str(e)
            logger.error("[MCP Service] Discovery HTTP error: %s", error_msg)

            if not is_stdio and ("connection" in error_msg.lower() or "timeout" in error_msg.lower()):
                try:
                    return await self._discover_rest_bridge(
                        base_url, is_resource=is_resource, method=method
                    )
                except Exception as bridge_err:
                    error_msg = f"Fallo total (MCP y Bridge): {str(bridge_err)}"

            raise RuntimeError(error_msg)
        except Exception as e:
            error_msg = str(e)
            logger.error("[MCP Service] Discovery fatal error: %s", error_msg)
            raise RuntimeError(error_msg)

    async def _discover_rest_bridge(
        self,
        url: str,
        initial_response: Optional[httpx.Response] = None,
        is_resource: bool = False,
        method: str = "GET",
    ) -> List[Dict[str, Any]]:
        """
        Smart tool discovery for REST APIs using LLM analysis.
        """
        try:
            path_params: list[str] = re.findall(r"\{(.*?)\}", url)

            # Fetch sample response for context + schema extraction
            sample_data = ""
            raw_sample = None
            if initial_response and initial_response.status_code < 400:
                sample_data = initial_response.text[:1500]
                try:
                    raw_sample = initial_response.json()
                except Exception:
                    pass
            else:
                async with httpx.AsyncClient() as client:
                    fetch_url = re.sub(r"\{.*?\}", "example", url)
                    try:
                        resp = await client.get(fetch_url, timeout=10.0)
                        sample_data = resp.text[:1000]
                        try:
                            raw_sample = resp.json()
                        except Exception:
                            pass
                    except Exception as fe:
                        sample_data = f"(fetch failed: {fe})"

            # Extract filterable schema from the sample data
            filterable_schema = {}
            if isinstance(raw_sample, list) and raw_sample:
                filterable_schema = self._extract_filterable_schema(raw_sample)
                logger.info(
                    "[MCP Service] Extracted filterable schema: %d key_figures, %d key_values",
                    len(filterable_schema.get("key_figures", [])),
                    len(filterable_schema.get("key_values", {})),
                )
            elif isinstance(raw_sample, dict):
                filterable_schema = self._extract_filterable_schema([raw_sample])

            # Build resource name deterministically
            parts = [p for p in url.split("/") if p and not p.startswith("http") and "{" not in p]
            resource_name = parts[-1] if parts else "resource"
            method_prefix = {"GET": "get", "POST": "create", "PUT": "update", "PATCH": "patch", "DELETE": "delete"}
            tool_name = f"{method_prefix.get(method, 'call')}_{resource_name}"

            # Ask the LLM to analyse the endpoint
            path_params_hint = (
                f"The URL has these path parameters (already detected): {path_params}"
                if path_params
                else "The URL has no path parameters."
            )
            param_placement = "JSON request body" if method in ("POST", "PUT", "PATCH") else "URL query string"

            analysis_prompt = f"""You are an API analyst. Analyze the following REST endpoint and respond with a valid JSON object ONLY (no markdown, no explanation, no extra text).

Endpoint URL: {url}
HTTP Method: {method}
{path_params_hint}
Extra parameters location: {param_placement}

Sample response data (first 1000 chars):
{sample_data[:1000]}

Return ONLY this JSON structure:
{{
  "description": "<one sentence, max 20 words, describing what this endpoint does>",
  "params": {{
    "<param_name>": {{
      "type": "<string|integer|number|boolean|object>",
      "description": "<what this param does>",
      "example": "<a realistic example value>"
    }}
  }},
  "response_fields": {{
    "<field_name>": {{
      "type": "<string|number|boolean|array|object>",
      "unit": "<measurement unit if numeric, e.g. °C, kW, %, or empty string>",
      "description": "<brief description of what this field means>"
    }}
  }}
}}

Rules:
- Include ALL path parameters in "params" (those wrapped in {{}} in the URL). They are always [required].
- For {method} requests, also infer body/query parameters from the URL name and sample data.
- In "response_fields" include only the top-level fields visible in the sample response (max 10).
- If the sample is a list, describe fields of ONE item.
- Do not include internal/system fields (e.g. _id, __v).
"""

            llm_result = await self._analyze_with_llm(analysis_prompt)

            description = (llm_result or {}).get("description") or f"Access to endpoint {url}"
            llm_params: dict = (llm_result or {}).get("params", {})
            llm_response: dict = (llm_result or {}).get("response_fields", {})

            properties: dict = {}
            for pp in path_params:
                if pp in llm_params:
                    properties[pp] = llm_params[pp]
                else:
                    properties[pp] = {
                        "type": "string",
                        "description": f"Path parameter '{pp}' embedded in the URL",
                        "example": pp,
                    }
            for pname, pdef in llm_params.items():
                if pname not in properties:
                    properties[pname] = pdef

            parameter_schema = {
                "type": "object",
                "properties": properties,
                "required": path_params,
                "response": llm_response,
                "filterable_schema": filterable_schema,
            }

            tool_def = {
                "name": tool_name,
                "description": description,
                "inputSchema": parameter_schema,
                "parameter_schema": parameter_schema,
                "config": {
                    "transport": "rest",
                    "url": url,
                    "method": method,
                },
            }

            logger.info(
                "[MCP Service] Smart discovery successful for %s (path_params=%s, response_fields=%s)",
                url,
                path_params,
                list(llm_response.keys()),
            )
            return [tool_def]

        except Exception as e:
            logger.error("[MCP Service] Smart Discovery failed for %s: %s", url, e)
            try:
                pp = re.findall(r"\{(.*?)\}", url)
                return [
                    {
                        "name": "get_api_resource",
                        "description": f"Access to endpoint {url}",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                p: {"type": "string", "description": f"Parameter {p}"} for p in pp
                            },
                            "required": pp,
                        },
                        "parameter_schema": {
                            "type": "object",
                            "properties": {
                                p: {"type": "string", "description": f"Parameter {p}"} for p in pp
                            },
                            "required": pp,
                            "response": {},
                            "filterable_schema": {},
                        },
                        "config": {"transport": "rest", "url": url, "method": method},
                    }
                ]
            except Exception:
                return []
