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

from skills import loader
loader.load_all()
