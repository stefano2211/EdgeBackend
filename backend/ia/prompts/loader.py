"""Prompt loader — Jinja2 templates from .md files.

Usage:
    from backend.ia.prompts.loader import load_prompt
    prompt = load_prompt("orchestrator", context="reactive", subagents=[...])
"""

from __future__ import annotations

import jinja2
from pathlib import Path

_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(Path(__file__).parent / "templates"),
    trim_blocks=True,
    lstrip_blocks=True,
)


def load_prompt(name: str, **variables) -> str:
    """Render a prompt template by name.

    Args:
        name: Template filename without .md extension.
        **variables: Jinja2 template variables.

    Returns:
        Fully rendered prompt string.
    """
    template = _env.get_template(f"{name}.md")
    return template.render(**variables)
