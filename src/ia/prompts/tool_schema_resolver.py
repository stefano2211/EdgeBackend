"""Dynamic tool & KB schema resolver for prompt injection.

Reads tool configs and knowledge bases from the database at runtime,
formats them as human-readable text blocks for Jinja2 template injection.

This replaces ALL hardcoded tool/integration references in prompts.
"""

from __future__ import annotations

import json
import logging
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def resolve_mcp_tool_docs(
    context: Literal["chat", "reactive"],
    session: AsyncSession,
    user_id: int | None = None,
) -> str:
    """Build a <tool_catalog> text block from the DB.

    Returns a formatted string listing every enabled MCP tool with its
    name, description, and parameter schema — ready for prompt injection.
    """
    tools = await _fetch_tool_configs(context, session, user_id)

    if not tools:
        return (
            "No integration tools are currently registered.\n"
            "If a task requires external data or actions, report this limitation clearly."
        )

    lines: list[str] = ["Available tools (call via mcp_execute):\n"]
    for i, t in enumerate(tools, 1):
        name = t.get("name", "unknown")
        desc = t.get("description") or "No description provided."
        schema = t.get("parameter_schema") or {}

        line = f"{i}. {name} — {desc}"
        params = schema.get("parameters") or schema.get("properties")
        if params:
            param_parts = []
            for pname, pinfo in params.items():
                ptype = pinfo.get("type", "any") if isinstance(pinfo, dict) else "any"
                param_parts.append(f"{pname}: {ptype}")
            line += f"\n   Parameters: {{{', '.join(param_parts)}}}"
        elif schema:
            line += f"\n   Parameters: {json.dumps(schema, ensure_ascii=False)}"

        lines.append(line)

    return "\n".join(lines)


async def resolve_kb_docs(
    context: Literal["chat", "reactive"],
    session: AsyncSession,
    user_id: int | None = None,
) -> str:
    """Build a knowledge base catalog text block from the DB.

    Returns a formatted string listing every active KB with its name
    and description — ready for prompt injection.
    """
    kbs = await _fetch_kb_configs(context, session, user_id)

    if not kbs:
        return (
            "No knowledge bases are currently active.\n"
            "If a task requires document lookup, report this limitation."
        )

    lines: list[str] = ["Active knowledge bases:\n"]
    for i, kb in enumerate(kbs, 1):
        name = kb.get("name", "unknown")
        desc = kb.get("description") or ""
        line = f"{i}. {name}"
        if desc:
            line += f" — {desc}"
        lines.append(line)

    return "\n".join(lines)


# ── Private helpers ──

async def _fetch_tool_configs(
    context: str, session: AsyncSession, user_id: int | None
) -> list[dict]:
    """Fetch enabled tool configs from the appropriate table."""
    try:
        if context == "reactive":
            from src.persistencia.repositories.reactive_tool_repository import (
                ReactiveToolRepository,
            )
            repo = ReactiveToolRepository(session)
            if user_id is not None:
                tools = await repo.list_enabled_by_user(user_id)
            else:
                tools = await repo.list()
                tools = [t for t in tools if t.is_enabled]
        else:
            from src.persistencia.repositories.tool_repository import ToolRepository
            repo = ToolRepository(session)
            tools = await repo.list()
            tools = [t for t in tools if t.is_enabled]

        return [
            {
                "name": t.name,
                "description": t.description,
                "parameter_schema": t.parameter_schema,
            }
            for t in tools
        ]
    except Exception as e:
        logger.warning("Failed to fetch tool configs for %s: %s", context, e)
        return []


async def _fetch_kb_configs(
    context: str, session: AsyncSession, user_id: int | None
) -> list[dict]:
    """Fetch active knowledge base configs from the appropriate table."""
    try:
        if context == "reactive":
            from src.persistencia.repositories.reactive_knowledge_repository import (
                ReactiveKnowledgeRepository,
            )
            repo = ReactiveKnowledgeRepository(session)
            if user_id is not None:
                kbs = await repo.list_by_user(user_id)
            else:
                kbs = await repo.list()
            kbs = [kb for kb in kbs if kb.is_enabled]
        else:
            from src.persistencia.repositories.knowledge_repository import (
                KnowledgeRepository,
            )
            repo = KnowledgeRepository(session)
            kbs = await repo.list()

        return [
            {
                "name": kb.name,
                "description": getattr(kb, "description", None),
            }
            for kb in kbs
        ]
    except Exception as e:
        logger.warning("Failed to fetch KB configs for %s: %s", context, e)
        return []
