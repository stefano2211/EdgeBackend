"""Maquinaria API client.

Thin HTTP client that queries the apiEjemplo server (port 7000)
for industrial machinery metrics.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "http://apiejemplo-api-1:7000"


class MaquinariaClient:
    """Client for the apiEjemplo machinery data API."""

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or os.environ.get("MAQUINARIA_API_URL", _DEFAULT_BASE_URL)).rstrip("/")

    def _get(self, path: str, params: dict | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(url, params=params)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error("Maquinaria API HTTP error: %s", exc)
            return {"success": False, "error": f"HTTP {exc.response.status_code}: {exc.response.text}"}
        except Exception as exc:
            logger.error("Maquinaria API request failed: %s", exc)
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def get_metrics(self, equipment: str, metric: str | None = None) -> dict[str, Any]:
        """Get the latest metrics for a specific equipment.

        Args:
            equipment: Equipment name (e.g. "Motor1", "BombaA", "CompresorX").
            metric: Optional metric type filter (e.g. "temperature", "vibration").
        """
        params: dict[str, Any] = {"equipment": equipment}
        if metric:
            params["metric"] = metric
        return self._get("/api/v1/maquinaria", params=params)

    def list_equipment(self) -> dict[str, Any]:
        """List all equipment with their latest status summary."""
        return self._get("/api/v1/maquinaria")


# Module-level singleton (env-var based, no caching needed — stateless HTTP)
_client: MaquinariaClient | None = None


def get_client() -> MaquinariaClient:
    """Return the shared MaquinariaClient singleton."""
    global _client
    if _client is None:
        _client = MaquinariaClient()
    return _client
