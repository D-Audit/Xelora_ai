"""
config.py
Single place every other module reads settings from. Nothing here talks
to Excel, the DB, or the AI - it's pure environment plumbing.
"""

import os
from pathlib import Path
from dotenv import dotenv_values, load_dotenv


_ENV_FILE = Path(__file__).with_name(".env")
load_dotenv(_ENV_FILE)
_LOCAL_ENV_VALUES = dotenv_values(_ENV_FILE)


def _local_agent_setting(name: str, default: str) -> str:
    """Prefer this desktop project's .env value for automation mode switches.

    A Uvicorn reloader inherits its parent's environment.  If that parent was
    once launched with VISUAL_ONLY_MODE=true, python-dotenv's normal
    non-overriding load left the backend stuck in visual-only mode even after
    the local .env was changed to false.  For these local automation switches,
    the project's explicit .env value is the source of truth; environment
    values remain the fallback when the setting is absent from .env.
    """
    value = _LOCAL_ENV_VALUES.get(name)
    return value if value is not None else os.getenv(name, default)

AI_PROVIDER = _local_agent_setting("AI_PROVIDER", "gemini").strip().lower()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
LOCAL_API_KEY = os.getenv("LOCAL_API_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")

MAX_STEPS_PER_TASK = int(_local_agent_setting("MAX_STEPS_PER_TASK", "60"))
MAX_RETRIES_PER_ACTION = int(_local_agent_setting("MAX_RETRIES_PER_ACTION", "2"))
SKILL_TIMEOUT_SECONDS = int(_local_agent_setting("SKILL_TIMEOUT_SECONDS", "60"))
MAX_VISUAL_ACTIONS_PER_TASK = int(os.getenv("MAX_VISUAL_ACTIONS_PER_TASK", 80))

ENABLE_CODEGEN_LAYER = _local_agent_setting("ENABLE_CODEGEN_LAYER", "true").lower() == "true"
ENABLE_VISUAL_FALLBACK = _local_agent_setting("ENABLE_VISUAL_FALLBACK", "false").lower() == "true"
VISUAL_ONLY_MODE = _local_agent_setting("VISUAL_ONLY_MODE", "false").lower() == "true"
# Hybrid mode keeps the real Excel window visible while structured skills do
# the precise workbook work.  Visual controls remain a narrow fallback for
# native shortcuts and dialogs that have no dependable object-model path.
HYBRID_VISIBLE_MODE = _local_agent_setting("HYBRID_VISIBLE_MODE", "true").lower() == "true"
ENABLE_VISUAL_CHECKPOINTS = _local_agent_setting("ENABLE_VISUAL_CHECKPOINTS", "true").lower() == "true"
ENABLE_VISIBLE_RANGE_NAVIGATION = _local_agent_setting("ENABLE_VISIBLE_RANGE_NAVIGATION", "true").lower() == "true"
# Visual recognition is optional. A backend restart or Uvicorn reload applies
# these environment settings. It must point to a separately running
# OmniParser service; a fixed default port is unsafe because users can run the
# FastAPI backend on that port and accidentally send parser requests back to
# Xelora itself.
OMNIPARSER_URL = _local_agent_setting("OMNIPARSER_URL", "").strip()
OMNIPARSER_TIMEOUT_SECONDS = int(_local_agent_setting("OMNIPARSER_TIMEOUT_SECONDS", "120"))

# A deliberate visual execution profile for installations that want to avoid
# the Excel object model, the skill library, and generated Python entirely.
# OmniParser identifies UI targets; the selected AI provider still plans the
# requested natural-language task and chooses safe keyboard/mouse actions.
OMNIPARSER_ONLY_MODE = _local_agent_setting("OMNIPARSER_ONLY_MODE", "false").lower() == "true"
ALLOW_VISUAL_STRUCTURED_EDITS = _local_agent_setting("ALLOW_VISUAL_STRUCTURED_EDITS", "false").lower() == "true"
if OMNIPARSER_ONLY_MODE:
    VISUAL_ONLY_MODE = True
    ENABLE_CODEGEN_LAYER = False
    ENABLE_VISUAL_FALLBACK = True
    HYBRID_VISIBLE_MODE = True
    ENABLE_VISUAL_CHECKPOINTS = True
    ENABLE_VISIBLE_RANGE_NAVIGATION = True
    # This profile is an explicit opt-in to the less reliable visual path.
    # It permits bounded visual table/formula/chart helpers rather than
    # rejecting every structured workbook request before OmniParser can help.
    ALLOW_VISUAL_STRUCTURED_EDITS = True

# Local OmniParser mode: when true, loads YOLOv9 + Florence-2 models directly
# in-process instead of calling an external HTTP service. Requires PyTorch +
# transformers + easyocr. Model weights are cached to ~/.cache/omniparser/.
# Set OMNIPARSER_LOCAL_MODE=true and leave OMNIPARSER_URL empty.
OMNIPARSER_LOCAL_MODE = _local_agent_setting("OMNIPARSER_LOCAL_MODE", "false").lower() == "true"
# Disable Florence-2 captioning for speed. When false, only YOLOv9 + OCR are
# used (much faster, ~1-2s per parse). When true (default), unlabelled icons
# also get AI-generated captions (~3-5s additional). Set to false on Windows
# if you don't need icon descriptions and want snappy visual responses.
ENABLE_FLORENCE_CAPTION = _local_agent_setting("ENABLE_FLORENCE_CAPTION", "true").lower() == "true"

GEMINI_MODEL_CHAIN = [
    m.strip() for m in os.getenv(
        "GEMINI_MODEL_CHAIN",
        "gemini-2.5-flash-lite,gemini-3.5-flash,gemini-3.5-flash-lite,gemini-3.1-flash-lite"
    ).split(",") if m.strip()
]
GEMINI_RATE_LIMIT_WAIT_SECONDS = int(os.getenv("GEMINI_RATE_LIMIT_WAIT_SECONDS", "0"))
GEMINI_TIMEOUT_SECONDS = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "60"))

# OpenRouter settings
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL_CHAIN = [
    m.strip() for m in os.getenv(
        "OPENROUTER_MODEL_CHAIN",
        "openrouter/free"
    ).split(",") if m.strip()
]
OPENROUTER_TIMEOUT_SECONDS = int(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "120"))
ALLOW_NO_AUTH = os.getenv("ALLOW_NO_AUTH", "false").lower() == "true"

ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]

RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", 60))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", 60))

KNOWLEDGE_INGEST_ALLOWED_DIR = os.getenv("KNOWLEDGE_INGEST_ALLOWED_DIR", os.path.join(os.path.expanduser("~"), "Documents"))
