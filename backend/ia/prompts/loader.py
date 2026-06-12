"""Prompt loader — Jinja2 templates from .md files.

Usage:
    from backend.ia.prompts.loader import load_prompt
    prompt = load_prompt("orchestrator", context="reactive", subagents=[...])
"""

from __future__ import annotations

import logging

import jinja2
from pathlib import Path

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"

_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(TEMPLATES_DIR),
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

    Raises:
        RuntimeError: If the template file is not found.
    """
    try:
        template = _env.get_template(f"{name}.md")
        return template.render(**variables)
    except jinja2.exceptions.TemplateNotFound:
        logger.error("Prompt template not found: %s.md", name)
        raise RuntimeError(
            f"Prompt template '{name}.md' not found in {TEMPLATES_DIR}. "
            f"Ensure the template file exists."
        )
