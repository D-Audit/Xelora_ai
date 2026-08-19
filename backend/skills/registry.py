r"""
skills/registry.py
Turns the SKILL_REGISTRY into the tool-schema formats each AI provider
expects, and provides the single dispatch function agent/core.py calls
to actually run a skill by name.

Import skills package first so registration has happened, then import
this module.
"""

import skills  # noqa: F401  (triggers registration of all built-in skills)
from skills.base import SKILL_REGISTRY


def claude_tools():
    return [
        {"name": name, "description": entry["description"], "input_schema": entry["input_schema"]}
        for name, entry in SKILL_REGISTRY.items()
    ]


def gemini_tools():
    return [{
        "function_declarations": [
            {"name": name, "description": entry["description"], "parameters": entry["input_schema"]}
            for name, entry in SKILL_REGISTRY.items()
        ]
    }]


def list_skill_names():
    return list(SKILL_REGISTRY.keys())


def run_skill(name: str, **kwargs):
    """Runs a registered skill by name. Raises KeyError if it doesn't exist -
    callers (agent/core.py) are expected to check first via has_skill()."""
    entry = SKILL_REGISTRY[name]
    return entry["func"](**kwargs)


def has_skill(name: str) -> bool:
    return name in SKILL_REGISTRY
