"""
skills/loader.py
Discovers and loads skills from skills/library/<name>/{SKILL.md, impl.py}
instead of requiring every skill to be a hand-written @skill(...)-decorated
Python function scattered across large files. Each skill now lives in its
own small folder:

  skills/library/insert_formula/
    SKILL.md   - human- and AI-readable metadata: name, category,
                 description, and the JSON input_schema, all in one place
    impl.py    - the actual implementation: a single run(**kwargs)
                 function plus whatever imports/helpers it needs

Every folder under skills/library/ that has both files is loaded. A
folder that cannot be loaded (bad frontmatter, missing schema, import
error, no run()) is skipped and logged as an ERROR at startup, so a broken
skill shows up in the agent log instead of as a confusing "the AI says
this skill doesn't exist" bug report.
"""

import importlib.util
import json
import logging
import os
import re

from skills.base import SKILL_REGISTRY

logger = logging.getLogger("skills.loader")

LIBRARY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "library")

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
_JSON_BLOCK_RE = re.compile(r"```json\n(.*?)\n```", re.DOTALL)


def _parse_frontmatter(md_text: str) -> dict:
    m = _FRONTMATTER_RE.match(md_text)
    if not m:
        raise ValueError("SKILL.md is missing a --- frontmatter block")
    fm = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fm[key.strip()] = value.strip().strip('"')
    return fm


def _parse_input_schema(md_text: str) -> dict:
    m = _JSON_BLOCK_RE.search(md_text)
    if not m:
        raise ValueError("SKILL.md is missing a ```json input schema block")
    return json.loads(m.group(1))


def load_all():
    """Loads every skill folder in skills/library/ into SKILL_REGISTRY.
    Call once, at import time (see skills/__init__.py)."""
    if not os.path.isdir(LIBRARY_DIR):
        logger.warning("Skill library folder not found: %s", LIBRARY_DIR)
        return

    loaded, skipped = [], []

    for name in sorted(os.listdir(LIBRARY_DIR)):
        folder = os.path.join(LIBRARY_DIR, name)
        if not os.path.isdir(folder) or name.startswith(("_", ".")):
            continue
        md_path = os.path.join(folder, "SKILL.md")
        impl_path = os.path.join(folder, "impl.py")

        if not (os.path.isfile(md_path) and os.path.isfile(impl_path)):
            logger.error("Skill folder '%s' needs both SKILL.md and impl.py - skipping it.", name)
            skipped.append(name)
            continue

        try:
            with open(md_path, "r", encoding="utf-8") as f:
                md_text = f.read()
            frontmatter = _parse_frontmatter(md_text)
            input_schema = _parse_input_schema(md_text)

            if frontmatter.get("name") != name:
                logger.error("'%s' folder name doesn't match SKILL.md frontmatter "
                             "name ('%s') - skipping it.", name, frontmatter.get("name"))
                skipped.append(name)
                continue

            spec = importlib.util.spec_from_file_location(f"skills.library.{name}.impl", impl_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            if not hasattr(module, "run"):
                logger.error("'%s' impl.py has no run() function - skipping it.", name)
                skipped.append(name)
                continue

            SKILL_REGISTRY[name] = {
                "func": module.run,
                "description": frontmatter.get("description", ""),
                "input_schema": input_schema,
                "category": frontmatter.get("category", "general"),
            }
            loaded.append(name)
        except Exception as e:
            logger.error("Failed to load skill '%s': %s", name, e)
            skipped.append(name)

    logger.info("Skill library: loaded %d skill(s), skipped %d.", len(loaded), len(skipped))
    if skipped:
        logger.warning("Skipped skills (see errors above): %s", skipped)
