"""Maquinaria MCP tool definitions.

Registers machinery monitoring tools on a FastMCP instance.
Each tool is a thin wrapper around MaquinariaClient methods.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .client import get_client


def register_tools(mcp: FastMCP) -> None:
    """Attach all Maquinaria tools to the given FastMCP server."""

    @mcp.tool()
    def get_machinery_metrics(equipment: str, metric: str | None = None) -> dict:
        """Get the latest metrics for a specific piece of equipment.

        Args:
            equipment: Name of the equipment to query.
                Valid values: Motor1, BombaA, CompresorX, TurbinaY, ReductorZ.
            metric: Optional metric type to filter by.
                Valid values: temperature, vibration, pressure, current, rpm, flow.
        """
        return get_client().get_metrics(equipment, metric)

    @mcp.tool()
    def list_equipment_status() -> dict:
        """List all equipment with their latest status summary."""
        return get_client().list_equipment()
