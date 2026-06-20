"""Extract prompt strings from .py files into .md templates.

Run from repo root: python scripts/extract_prompts.py
"""

import ast
import textwrap
from pathlib import Path

SRC = Path("src/ia/prompts")
OUT = SRC / "templates"


def extract_string_assignments(path: Path):
    """Return dict {name: value} for top-level string assignments."""
    code = path.read_text(encoding="utf-8")
    tree = ast.parse(code)
    result = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and isinstance(node.value, ast.Constant):
                    val = node.value.value
                    if isinstance(val, str) and len(val) > 200:
                        result[target.id] = val
    return result


def save_template(name: str, content: str, replacements: dict | None = None):
    out_path = OUT / f"{name}.md"
    text = content
    if replacements:
        for old, new in replacements.items():
            text = text.replace(old, new)
    out_path.write_text(text, encoding="utf-8")
    print(f"Wrote {out_path}")


def main():
    OUT.mkdir(exist_ok=True)

    # ── orchestrator ──
    orch = extract_string_assignments(SRC / "orchestrator.py")
    # The main template is _PROMPT_TEMPLATE which contains placeholders
    if "_PROMPT_TEMPLATE" in orch:
        save_template(
            "orchestrator",
            orch["_PROMPT_TEMPLATE"],
            replacements={
                "{subagent_descriptions}": "{{ subagent_descriptions }}",
                "{routing_rules}": "{{ routing_rules }}",
                "{routing_examples}": "{{ routing_examples }}",
            },
        )

    # ── subagents ──
    sub = extract_string_assignments(SRC / "subagents.py")
    for key, tmpl_name in [
        ("INDUSTRIAL_AGENT_SYSTEM_PROMPT", "subagent_industrial"),
        ("VL_AGENT_SYSTEM_PROMPT", "subagent_vl"),
    ]:
        if key in sub:
            save_template(tmpl_name, sub[key])

    # ── reactive ──
    react = extract_string_assignments(SRC / "reactive.py")
    for key, tmpl_name in [
        ("REACTIVE_S2_TRIAGE_PROMPT", "reactive_triage"),
        ("_S2_ORCHESTRATOR_TEMPLATE", "reactive_orchestrator"),
        ("_S2_SYNTHESIS_TEMPLATE", "reactive_synthesis"),
        ("_S1_COORDINATOR_TEMPLATE", "reactive_s1_coordinator"),
    ]:
        if key in react:
            text = react[key]
            replacements = {}
            if key == "_S2_ORCHESTRATOR_TEMPLATE":
                replacements = {
                    "{subagents_section}": "{{ subagents_section }}",
                    "{industrial_delegation_rules}": "{{ industrial_delegation_rules }}",
                }
            elif key == "_S2_SYNTHESIS_TEMPLATE":
                replacements = {
                    "{input_sections}": "{{ input_sections }}",
                    "{event_context}": "{{ event_context }}",
                }
            elif key == "_S1_COORDINATOR_TEMPLATE":
                replacements = {
                    "{notification_email}": "{{ notification_email }}",
                }
            save_template(tmpl_name, text, replacements)

    print("Done.")


if __name__ == "__main__":
    main()
