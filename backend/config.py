"""
config.py
Single place every other module reads settings from. Nothing here talks
to Excel, the DB, or the AI - it's pure environment plumbing.
"""

import os
import importlib
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
# A configured secondary provider keeps an in-progress workbook task alive
# when the primary provider is rate-limited or its DNS/network route fails.
# It is used only after a verified availability failure; it is not a normal
# load-balancer and will never send concurrent Excel actions.
AI_PROVIDER_FALLBACK_CHAIN = [
    provider.strip().lower()
    for provider in _local_agent_setting("AI_PROVIDER_FALLBACK_CHAIN", "openrouter,claude,gemini").split(",")
    if provider.strip() and provider.strip().lower() != AI_PROVIDER
]
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
LOCAL_API_KEY = os.getenv("LOCAL_API_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")

MAX_STEPS_PER_TASK = int(_local_agent_setting("MAX_STEPS_PER_TASK", "60"))
MAX_RETRIES_PER_ACTION = int(_local_agent_setting("MAX_RETRIES_PER_ACTION", "2"))
SKILL_TIMEOUT_SECONDS = int(_local_agent_setting("SKILL_TIMEOUT_SECONDS", "60"))
# Startup must not appear frozen because an optional Excel-version probe is
# slow.  Formula planning can safely begin in legacy-compatible mode and do a
# deeper capability check only when it is genuinely needed.
INITIAL_EXCEL_CHECK_TIMEOUT_SECONDS = int(
    _local_agent_setting("INITIAL_EXCEL_CHECK_TIMEOUT_SECONDS", "8")
)
# A large visual workbook needs more than the old 80-action ceiling, but the
# cap remains finite so a faulty UI loop cannot keep typing indefinitely.
# Use the same .env precedence as the other local automation controls.
MAX_VISUAL_ACTIONS_PER_TASK = int(_local_agent_setting("MAX_VISUAL_ACTIONS_PER_TASK", "240"))

ENABLE_CODEGEN_LAYER = _local_agent_setting("ENABLE_CODEGEN_LAYER", "true").lower() == "true"
ENABLE_VISUAL_FALLBACK = _local_agent_setting("ENABLE_VISUAL_FALLBACK", "false").lower() == "true"
VISUAL_ONLY_MODE = _local_agent_setting("VISUAL_ONLY_MODE", "false").lower() == "true"
# Hybrid mode keeps the real Excel window visible while structured skills do
# the precise workbook work.  Visual controls remain a narrow fallback for
# native shortcuts and dialogs that have no dependable object-model path.
HYBRID_VISIBLE_MODE = _local_agent_setting("HYBRID_VISIBLE_MODE", "true").lower() == "true"
# A visible hybrid session should use the available working area by default.
# This stays configurable for kiosk, remote-desktop, or multi-window setups.
MAXIMIZE_EXCEL_WINDOW = _local_agent_setting("MAXIMIZE_EXCEL_WINDOW", "true").lower() == "true"
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


def validate_local_omniparser_configuration() -> None:
    """Fail at service startup when the opted-in local parser is unavailable.

    Local mode previously deferred its import until the first screen parse.
    That made every unresolved visual click wait through parser retries before
    reporting a missing module. Startup validation turns the configuration
    error into one clear, actionable failure instead.
    """
    if not OMNIPARSER_LOCAL_MODE:
        return
    try:
        importlib.import_module("vision.local_omniparser")
    except Exception as exc:
        raise RuntimeError(
            "OMNIPARSER_LOCAL_MODE=true requires the local parser module "
            "'vision.local_omniparser', but it could not be imported. "
            "Install/provide that module or set OMNIPARSER_LOCAL_MODE=false "
            "and configure OMNIPARSER_URL."
        ) from exc

GEMINI_MODEL_CHAIN = [
    m.strip() for m in os.getenv(
        "GEMINI_MODEL_CHAIN",
        "gemini-2.5-flash-lite,gemini-3.5-flash,gemini-3.5-flash-lite,gemini-3.1-flash-lite"
    ).split(",") if m.strip()
]
GEMINI_RATE_LIMIT_WAIT_SECONDS = int(os.getenv("GEMINI_RATE_LIMIT_WAIT_SECONDS", "0"))
# A model response that takes a full minute makes the desktop agent look
# frozen. Fail over quickly; model switching is cheaper than blocking Excel.
GEMINI_TIMEOUT_SECONDS = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "20"))
# A Gemini turn may try more than one model, but never indefinitely.
GEMINI_TOTAL_TIMEOUT_SECONDS = int(os.getenv("GEMINI_TOTAL_TIMEOUT_SECONDS", "45"))

# OpenRouter settings
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL_CHAIN = [
    m.strip() for m in os.getenv(
        "OPENROUTER_MODEL_CHAIN",
        # Curated only for verified tool calling.  Do not treat every model
        # available through OpenRouter as an agent model: Xelora needs native
        # function calls to make safe, observable Excel actions.
        "deepseek/deepseek-v4-flash-0731,xiaomi/mimo-v2.5,tencent/hy3,minimax/minimax-m3:free,openrouter/free"
    ).split(",") if m.strip()
]
# Fail over quickly rather than making a desktop task appear frozen for two
# minutes per model.  The model chain provides the availability resilience.
OPENROUTER_TIMEOUT_SECONDS = int(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "35"))
OPENROUTER_INTER_MODEL_DELAY_SECONDS = float(
    os.getenv("OPENROUTER_INTER_MODEL_DELAY_SECONDS", "0")
)
# Applies across the complete OpenRouter model chain, not per model.  This is
# what prevents five fallback models from looking like a multi-minute freeze.
OPENROUTER_TOTAL_TIMEOUT_SECONDS = int(
    os.getenv("OPENROUTER_TOTAL_TIMEOUT_SECONDS", "45")
)
CLAUDE_TIMEOUT_SECONDS = int(os.getenv("CLAUDE_TIMEOUT_SECONDS", "35"))


def validate_ai_provider_configuration() -> None:
    """Reject an explicitly selected provider that has no credential.

    Secondary providers are optional and are skipped until their keys are
    configured.  The primary provider is different: accepting a task only to
    fail on its first model request is misleading, so fail loudly at startup.
    """
    configured_keys = {
        "gemini": GEMINI_API_KEY,
        "claude": ANTHROPIC_API_KEY,
        "openrouter": OPENROUTER_API_KEY,
    }
    if AI_PROVIDER not in configured_keys:
        raise RuntimeError(
            "AI_PROVIDER must be one of: gemini, claude, openrouter. "
            f"Received {AI_PROVIDER!r}."
        )
    if not configured_keys[AI_PROVIDER]:
        env_name = {
            "gemini": "GEMINI_API_KEY",
            "claude": "ANTHROPIC_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
        }[AI_PROVIDER]
        raise RuntimeError(
            f"AI_PROVIDER={AI_PROVIDER} requires {env_name} to be set. "
            "Add the key to backend/.env, then restart the backend."
        )
    if AI_PROVIDER == "openrouter" and not OPENROUTER_MODEL_CHAIN:
        raise RuntimeError(
            "AI_PROVIDER=openrouter requires at least one OPENROUTER_MODEL_CHAIN entry."
        )
ALLOW_NO_AUTH = os.getenv("ALLOW_NO_AUTH", "false").lower() == "true"

ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]

RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", 60))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", 60))

KNOWLEDGE_INGEST_ALLOWED_DIR = os.getenv("KNOWLEDGE_INGEST_ALLOWED_DIR", os.path.join(os.path.expanduser("~"), "Documents"))
