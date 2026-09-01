"""
skills/__init__.py
Two registration paths feed skills.base.SKILL_REGISTRY:

1. skills/library/<name>/{SKILL.md, impl.py} - the main, folder-based
   catalog. Loaded and integrity-checked by skills/loader.py at import
   time here. This is where every Excel skill now lives - see
   skills/loader.py's docstring for the manifest/hash security model.
2. The legacy @skill(...) decorator (skills/base.py) - still used by
   vision/decision_loop.py for the visual-fallback layer, since that's
   tightly coupled to screen/click/type control rather than being an
   Excel operation. Both paths land in the same SKILL_REGISTRY dict, so
   agent/core.py and mcp_server/server.py need no changes either way.
"""

import os

from skills import loader

# Generated-code workers import only ``skills.excel_shared`` to resolve the
# workbook that the parent task already chose.  Loading every registered skill
# there adds avoidable startup time to each isolated Python worker and is not
# needed for codegen safety.  The normal backend process always loads the full
# signed registry.
if os.getenv("XELORA_SKIP_SKILL_REGISTRY") != "1":
    loader.load_all()
