"""Webhook Mapping Engine — transforms arbitrary JSON payloads into
normalized EventIngestPayload objects using dynamic JSONPath-based rules.

Supports auto-discovery via LLM for unknown payload shapes.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from jsonpath_ng import parse as jsonpath_parse

from backend.api.v1.schemas.event import EventIngestPayload
from backend.core.logging import logging
from backend.ia.llm_client import get_llm_client

logger = logging.getLogger(__name__)


class WebhookMappingEngine:
    """Execute dynamic extractors against raw JSON payloads."""

    # ═══════════════════════════════════════════════════════════════════════
    #  Public API
    # ═══════════════════════════════════════════════════════════════════════

    def execute(
        self,
        raw_payload: dict[str, Any],
        mapping_config: dict[str, Any] | None,
        webhook_name: str = "unknown",
    ) -> EventIngestPayload:
        """Transform a raw payload into an EventIngestPayload.

        If *mapping_config* is missing or empty, falls back to a default
        mapping that tries common heuristics.
        """
        if not mapping_config:
            mapping_config = self._default_mapping(webhook_name)

        extractors = mapping_config.get("extractors", {})
        extracted: dict[str, Any] = {}

        for field, rule in extractors.items():
            extracted[field] = self._resolve_field(raw_payload, rule)

        # Build EventIngestPayload
        return EventIngestPayload(
            type=extracted.get("event_type") or "generic",
            source=extracted.get("source") or webhook_name,
            title=extracted.get("title") or "Untitled Event",
            description=extracted.get("description"),
            severity_text=extracted.get("severity_text"),
            severity_number=extracted.get("severity_number"),
            timestamp=extracted.get("timestamp"),
            subject=extracted.get("subject"),
            data=raw_payload,  # ALWAYS full payload
        )

    async def auto_discover(
        self,
        raw_payload: dict[str, Any],
        webhook_name: str,
    ) -> dict[str, Any]:
        """Generate a mapping_config by asking the LLM to analyse the payload.

        Returns a dict ready to be persisted in WebhookSource.mapping_config.
        """
        try:
            client = get_llm_client()
        except RuntimeError:
            logger.warning("LLM client unavailable — cannot auto-discover mapping")
            return self._default_mapping(webhook_name)

        prompt = self._build_auto_discover_prompt(raw_payload, webhook_name)

        try:
            response = await client.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a webhook payload analyzer. "
                            "You receive JSON payloads from external systems and produce "
                            "mapping configurations that extract event fields."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
                max_tokens=800,
                stream=False,
            )

            raw = (
                response.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            mapping = self._extract_json(raw)

            if mapping and "extractors" in mapping:
                logger.info(
                    "Auto-discovered mapping for webhook '%s' with %d extractors",
                    webhook_name,
                    len(mapping.get("extractors", {})),
                )
                return mapping

        except Exception as exc:
            logger.exception("Auto-discover failed for webhook '%s': %s", webhook_name, exc)

        return self._default_mapping(webhook_name)

    # ═══════════════════════════════════════════════════════════════════════
    #  Resolution helpers
    # ═══════════════════════════════════════════════════════════════════════

    def _resolve_field(self, payload: dict[str, Any], rule: dict[str, Any]) -> Any:
        """Apply a single extractor rule against the payload."""
        rule_type = rule.get("type", "jsonpath")

        # ── Static ──
        if rule_type == "static":
            return rule.get("value")

        # ── Template ──
        if rule_type == "template":
            template = rule.get("template", "")
            # Simple variable substitution: {{ $.foo.bar }}
            result = template
            for key in self._extract_template_vars(template):
                val = self._jsonpath(payload, key)
                result = result.replace(f"{{{{ {key} }}}}", str(val) if val is not None else "")
            return result

        # ── Computed ──
        if rule_type == "computed":
            op = rule.get("operation", "concat")
            if op == "concat":
                parts = []
                for part_rule in rule.get("parts", []):
                    parts.append(str(self._resolve_field(payload, part_rule) or ""))
                return "".join(parts)
            if op == "hash":
                import hashlib
                src = self._resolve_field(payload, rule.get("source", {}))
                return hashlib.sha256(str(src).encode()).hexdigest()[:16]
            return None

        # ── JSONPath (default) ──
        value = self._jsonpath(payload, rule.get("path"))

        # Fallback chain: supports legacy "fallback" / "fallback2" keys
        # as well as a modern "fallbacks" list.
        if value is None:
            for fb in rule.get("fallbacks", []):
                value = self._jsonpath(payload, fb)
                if value is not None:
                    break
            if value is None and "fallback" in rule:
                value = self._jsonpath(payload, rule["fallback"])
            if value is None and "fallback2" in rule:
                value = self._jsonpath(payload, rule["fallback2"])

        # Default value
        if value is None and "default" in rule:
            value = rule["default"]

        # Transformations
        if value is not None and "transform" in rule:
            value = self._apply_transform(value, rule["transform"], rule)

        return value

    def _jsonpath(self, payload: dict[str, Any], path: str | None) -> Any:
        """Safely evaluate a JSONPath expression."""
        if not path:
            return None
        try:
            parsed = jsonpath_parse(path)
            matches = parsed.find(payload)
            if matches:
                # If multiple matches, return list; otherwise scalar
                if len(matches) == 1:
                    return matches[0].value
                return [m.value for m in matches]
        except Exception as exc:
            logger.debug("JSONPath parse error for '%s': %s", path, exc)
        return None

    def _apply_transform(
        self, value: Any, transform: str, rule: dict[str, Any]
    ) -> Any:
        """Apply a named transformation to a value."""
        if transform == "severity_map":
            mapping = rule.get("severity_map", {})
            return mapping.get(str(value), rule.get("default", "warning"))

        if transform == "iso_datetime":
            return self._parse_datetime(value)

        if transform == "unix_timestamp":
            try:
                ts = float(value)
                return datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)
            except Exception:
                return None

        if transform == "uppercase":
            return str(value).upper()

        if transform == "lowercase":
            return str(value).lower()

        if transform == "trim":
            return str(value).strip()

        if transform == "json_stringify":
            return json.dumps(value, ensure_ascii=False)

        return value

    def _parse_datetime(self, value: Any) -> datetime | None:
        """Parse ISO-8601, RFC-2822, or common datetime strings."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.replace(tzinfo=None) if value.tzinfo else value
        try:
            # ISO-8601
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(
                tzinfo=None
            )
        except Exception:
            pass
        try:
            # Common format fallback
            return datetime.strptime(str(value)[:19], "%Y-%m-%dT%H:%M:%S")
        except Exception:
            pass
        return None

    # ═══════════════════════════════════════════════════════════════════════
    #  Auto-discover helpers
    # ═══════════════════════════════════════════════════════════════════════

    def _build_auto_discover_prompt(
        self, payload: dict[str, Any], webhook_name: str
    ) -> str:
        payload_json = json.dumps(payload, indent=2, ensure_ascii=False)
        return (
            f"Analyze this JSON payload from external system '{webhook_name}'.\n"
            f"Generate a mapping_config JSON that extracts these fields:\n"
            f"- title (string, REQUIRED)\n"
            f"- description (string, optional)\n"
            f"- severity_text (one of: critical, error, warning, info, debug)\n"
            f"- source (string, fixed = '{webhook_name}')\n"
            f"- event_type (string)\n"
            f"- timestamp (ISO-8601 datetime or null → use 'now')\n"
            f"- subject (string, optional)\n\n"
            f"Use jsonpath expressions compatible with jsonpath-ng library.\n"
            f"If a field cannot be found, use a default value or null.\n\n"
            f"Payload:\n```json\n{payload_json}\n```\n\n"
            f"Respond ONLY with a valid JSON object matching this schema:\n"
            f"```json\n"
            f'{{\n'
            f'  "version": "1",\n'
            f'  "extractors": {{\n'
            f'    "title": {{"type": "jsonpath", "path": "...", "default": "..."}},\n'
            f'    "description": {{"type": "jsonpath", "path": "...", "default": null}},\n'
            f'    "severity_text": {{"type": "jsonpath", "path": "...", "transform": "severity_map", "severity_map": {{...}}, "default": "warning"}},\n'
            f'    "source": {{"type": "static", "value": "{webhook_name}"}},\n'
            f'    "event_type": {{"type": "jsonpath", "path": "...", "default": "generic"}},\n'
            f'    "timestamp": {{"type": "jsonpath", "path": "...", "transform": "iso_datetime", "default": "now"}},\n'
            f'    "subject": {{"type": "jsonpath", "path": "...", "default": null}}\n'
            f'  }},\n'
            f'  "body_strategy": "full_payload"\n'
            f'}}\n'
            f"```"
        )

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any] | None:
        """Extract the first JSON object from a text block (handles markdown fences)."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Drop first line (```json or ```)
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return None

    def _default_mapping(self, webhook_name: str) -> dict[str, Any]:
        """Return a safe fallback mapping that tries common field names."""
        return {
            "version": "1",
            "extractors": {
                "title": {
                    "type": "jsonpath",
                    "path": "$.title",
                    "fallback": "$.message",
                    "fallback2": "$.alert.title",
                    "default": "Untitled Event",
                },
                "description": {
                    "type": "jsonpath",
                    "path": "$.description",
                    "fallback": "$.body",
                    "fallback2": "$.alert.body",
                    "default": None,
                },
                "severity_text": {
                    "type": "jsonpath",
                    "path": "$.severity",
                    "fallback": "$.priority",
                    "fallback2": "$.alert.severity",
                    "default": "warning",
                },
                "source": {"type": "static", "value": webhook_name},
                "event_type": {
                    "type": "jsonpath",
                    "path": "$.type",
                    "fallback": "$.alert.type",
                    "default": "generic",
                },
                "timestamp": {
                    "type": "jsonpath",
                    "path": "$.timestamp",
                    "fallback": "$.time",
                    "fallback2": "$.alert.timestamp",
                    "transform": "iso_datetime",
                    "default": "now",
                },
                "subject": {
                    "type": "jsonpath",
                    "path": "$.subject",
                    "default": None,
                },
            },
            "body_strategy": "full_payload",
        }

    @staticmethod
    def _extract_template_vars(template: str) -> list[str]:
        """Extract variable names from a template string like '{{ $.foo.bar }}'."""
        import re
        return re.findall(r"\{\{\s*([^}]+?)\s*\}\}", template)
