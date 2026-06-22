"""Domain detection — classifies events into user-configured domains.

Architecture:
  1. Rule-based matching (fast, deterministic, user-configurable)
  2. LLM inference fallback (smart, cached by source pattern)

SOLID:
  - SRP: Only classifies events; no persistence logic.
  - OCP: New detection strategies can be added as plugins.
  - DIP: Depends on DomainConfigRepository abstraction, not DB directly.
"""

from __future__ import annotations

import fnmatch
import json
import logging
import time
from typing import Any

from backend.infrastructure.llm.client import get_llm_client
from backend.infrastructure.persistence.domain_config_repository import DomainConfigRepository

logger = logging.getLogger(__name__)

# In-memory TTL cache for LLM inferences to avoid repeated calls.
# Key: source string, Value: {"result": {...}, "ts": float (epoch)}
_CACHE_TTL_SECONDS = 300  # 5 minutes
_inference_cache: dict[str, dict[str, Any]] = {}


def _get_cached(source: str) -> dict[str, Any] | None:
    """Return cached result if not expired."""
    entry = _inference_cache.get(source)
    if not entry:
        return None
    if time.time() - entry["ts"] > _CACHE_TTL_SECONDS:
        del _inference_cache[source]
        return None
    return entry["result"]


def _set_cached(source: str, result: dict[str, Any]) -> None:
    _inference_cache[source] = {"result": result, "ts": time.time()}


class DomainDetector:
    """Detects the domain of an event using rules + LLM fallback."""

    def __init__(self, repo: DomainConfigRepository) -> None:
        self._repo = repo

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def detect(
        self,
        payload: dict[str, Any],
        user_id: int | None,
        source: str | None = None,
    ) -> dict[str, Any]:
        """Return {"domain": str, "subdomain": str|None, "confidence": float, "source": str}."""
        # 1. Rule-based detection (fast path)
        if user_id is not None:
            rule_match = await self._match_rules(payload, user_id, source)
            if rule_match:
                return {**rule_match, "source": "rule"}

        # 2. LLM inference fallback (cached by source with TTL)
        if source:
            cached = _get_cached(source)
            if cached:
                return {**cached, "source": "llm_cache"}

        llm_result = await self._llm_infer(payload, source)
        if source:
            _set_cached(source, llm_result)
        return {**llm_result, "source": "llm"}

    # ------------------------------------------------------------------
    # Rule-based matching
    # ------------------------------------------------------------------

    async def _match_rules(
        self,
        payload: dict[str, Any],
        user_id: int,
        source: str | None,
    ) -> dict[str, Any] | None:
        """Match against user-configured detection rules."""
        domains = await self._repo.list_for_user(user_id)

        for domain in domains:
            rules = domain.detection_rules or {}

            # Keyword matching (case-insensitive)
            keywords = rules.get("keywords", [])
            if keywords and self._payload_contains_any(payload, keywords):
                return {
                    "domain": domain.name,
                    "subdomain": None,
                    "confidence": 0.95,
                }

            # Source pattern matching (unix glob style)
            patterns = rules.get("source_patterns", [])
            if source and patterns:
                if any(fnmatch.fnmatch(source, pat) for pat in patterns):
                    return {
                        "domain": domain.name,
                        "subdomain": None,
                        "confidence": 0.95,
                    }

        return None

    @staticmethod
    def _payload_contains_any(payload: dict[str, Any], keywords: list[str]) -> bool:
        """Recursively check if any keyword appears in payload keys/values."""
        lowered = [k.lower() for k in keywords]
        stack: list[Any] = [payload]

        while stack:
            current = stack.pop()
            if isinstance(current, dict):
                for key, value in current.items():
                    if any(k in key.lower() for k in lowered):
                        return True
                    stack.append(value)
            elif isinstance(current, list):
                stack.extend(current)
            elif isinstance(current, str):
                if any(k in current.lower() for k in lowered):
                    return True
        return False

    # ------------------------------------------------------------------
    # LLM inference
    # ------------------------------------------------------------------

    async def _llm_infer(
        self,
        payload: dict[str, Any],
        source: str | None,
    ) -> dict[str, Any]:
        """Use a fast LLM call to infer the domain from payload structure."""
        try:
            client = get_llm_client()
        except RuntimeError:
            logger.warning("LLM not available for domain inference; defaulting to generic")
            return {"domain": "generic", "subdomain": None, "confidence": 0.5}

        prompt = self._build_llm_prompt(payload, source)

        try:
            response = await client.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a domain classifier. Analyze the event payload and "
                            "return ONLY a JSON object with keys: domain (string), "
                            "subdomain (string or null), confidence (0.0-1.0). "
                            "Possible domains: healthcare, logistics, manufacturing, "
                            "finance, it_operations, energy, generic."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=150,
                stream=False,
            )

            raw = response.get("choices", [{}])[0].get("message", {}).get("content", "")
            parsed = self._extract_json(raw)
            if parsed and "domain" in parsed:
                return {
                    "domain": parsed["domain"],
                    "subdomain": parsed.get("subdomain"),
                    "confidence": float(parsed.get("confidence", 0.7)),
                }
        except Exception as exc:
            logger.warning("LLM domain inference failed: %s", exc)

        return {"domain": "generic", "subdomain": None, "confidence": 0.5}

    @staticmethod
    def _build_llm_prompt(payload: dict[str, Any], source: str | None) -> str:
        payload_json = json.dumps(payload, ensure_ascii=False, indent=2)[:800]
        parts = ["Classify the domain of this event."]
        if source:
            parts.append(f"Source: {source}")
        parts.append(f"Payload:\n{payload_json}")
        return "\n".join(parts)

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any] | None:
        """Extract JSON from possible markdown fences."""
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
        if cleaned.endswith("```"):
            cleaned = cleaned.rsplit("\n", 1)[0]
        cleaned = cleaned.strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return None
