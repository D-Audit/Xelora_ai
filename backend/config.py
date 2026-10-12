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


def _sqlalchemy_database_url(url: str) -> str:
    """Pin Postgres URLs to psycopg2 (the installed driver).

    SQLAlchemy 2.1 maps a bare postgresql:// URL to psycopg 3, and some hosts
    hand out the legacy postgres:// scheme, which SQLAlchemy rejects.
    """
    url = url.strip()
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg2://" + url[len(prefix):]
    return url


DATABASE_URL = _sqlalchemy_database_url(os.getenv("DATABASE_URL", ""))

# Model API base URLs. Blank means the provider's public endpoint. The desktop
# local agent points these at the cloud relay (/agent-link/llm/<provider>/) so
# provider keys never leave the server.
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "")
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "")
OPENROUTER_BASE_URL = (os.getenv("OPENROUTER_BASE_URL", "") or "https://openrouter.ai/api/v1").rstrip("/")

# Where signed-in users' tasks run. "server": in this process (local install,
# backend on the same PC as Excel). "agent": the cloud queues each task for the
# user's own Xelora Desktop local agent (see agent_link.py, local_agent.py).
TASK_EXECUTION = os.getenv("TASK_EXECUTION", "server").strip().lower()
# Public URL of this API, given to paired desktop agents. Falls back to the
# URL the pairing request arrived on.
PUBLIC_API_URL = os.getenv("PUBLIC_API_URL", "").rstrip("/")

# Complex dashboard work can legitimately need several planning, repair, and
# verification turns. Keep a finite safety boundary, but do not stop a healthy
# task at the old 60-turn default before its charts and final audit are done.
# 180 still leaves a firm stop for a genuinely faulty agent loop.
MAX_STEPS_PER_TASK = int(_local_agent_setting("MAX_STEPS_PER_TASK", "180"))
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
# General terminal tools are isolated behind a dedicated opt-in.
ENABLE_TERMINAL_TOOLS = _local_agent_setting("ENABLE_TERMINAL_TOOLS", "false").lower() == "true"
# Even with terminal tools enabled, mutating commands stay blocked unless the
# administrator also opts in to the bounded write allowlist (pip install -r,
# pytest) anchored to XELORA_TERMINAL_ROOT.
TERMINAL_WRITE_TOOLS = _local_agent_setting("TERMINAL_WRITE_TOOLS", "false").lower() == "true"
ENABLE_CUA_DRIVER = _local_agent_setting("ENABLE_CUA_DRIVER", "false").lower() == "true"
TERMINAL_TIMEOUT_SECONDS = int(_local_agent_setting("TERMINAL_TIMEOUT_SECONDS", "30"))
# Absolute path to the Cua Driver binary when it is not on PATH (use the
# location reported by `cua-driver doctor`). Leave empty to resolve
# `cua-driver` from PATH. CUA_DRIVER_ARGS defaults to its stdio MCP server.
CUA_DRIVER_COMMAND = os.getenv("CUA_DRIVER_COMMAND", "").strip()
CUA_DRIVER_ARGS = os.getenv("CUA_DRIVER_ARGS", "mcp").strip()
# Cua input normally must target an observed pid+window_id, and only the
# task's bound Excel process once one is known. These widen that boundary.
CUA_ALLOW_DESKTOP_SCOPE = _local_agent_setting("CUA_ALLOW_DESKTOP_SCOPE", "false").lower() == "true"
CUA_ALLOW_OTHER_APPS = _local_agent_setting("CUA_ALLOW_OTHER_APPS", "false").lower() == "true"
# Outbound MCP: tools from administrator-configured stdio MCP servers. Every
# server lists the exact tools it may expose; nothing is exposed by default.
ENABLE_MCP_CLIENT = _local_agent_setting("ENABLE_MCP_CLIENT", "false").lower() == "true"
MCP_SERVERS_FILE = _local_agent_setting("MCP_SERVERS_FILE", "").strip()
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

# Scheduled automation runs over existing workflows. Disabled by default:
# recurring actions must never start without an explicit administrator and
# user opt-in. Schedules themselves are still created per user through the
# automation API; this flag only starts the background scheduler process.
ENABLE_AUTOMATIONS = _local_agent_setting("ENABLE_AUTOMATIONS", "false").lower() == "true"

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


def validate_terminal_configuration() -> None:
    """Fail at startup when opted-in agent tools are misconfigured.

    Terminal tools without a workspace root, or an MCP client without a
    readable server file, are refused. A Cua command override that does not
    exist only warns: the Driver may be installed after the backend starts,
    and /agent/cua/health reports the live state.
    """
    if ENABLE_TERMINAL_TOOLS:
        root = os.getenv("XELORA_TERMINAL_ROOT", "").strip()
        if not root:
            raise RuntimeError(
                "ENABLE_TERMINAL_TOOLS=true requires XELORA_TERMINAL_ROOT to point at the "
                "directory the agent may inspect. Set it in backend/.env, then restart."
            )
        if not os.path.isdir(os.path.expanduser(root)):
            raise RuntimeError(f"XELORA_TERMINAL_ROOT={root} is not an existing directory.")
    if ENABLE_MCP_CLIENT:
        if not MCP_SERVERS_FILE or not os.path.isfile(MCP_SERVERS_FILE):
            raise RuntimeError(
                "ENABLE_MCP_CLIENT=true requires MCP_SERVERS_FILE to point at a JSON server "
                "configuration (see backend/mcp_servers.example.json)."
            )
        from tools.mcp_external import load_server_config
        load_server_config(MCP_SERVERS_FILE)  # raises RuntimeError with the exact problem
    if ENABLE_CUA_DRIVER and CUA_DRIVER_COMMAND and not os.path.isfile(CUA_DRIVER_COMMAND):
        import shutil as _shutil
        if _shutil.which(CUA_DRIVER_COMMAND) is None:
            print(f"WARNING: CUA_DRIVER_COMMAND={CUA_DRIVER_COMMAND} was not found; Cua tools stay unavailable until it is fixed.")


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

# Excel tasks are multi-step tool use: lead with the most capable model and
# fail over to the lighter ones. Quick chat uses QUICK_CHAT_GEMINI_MODEL.
GEMINI_MODEL_CHAIN = [
    m.strip() for m in os.getenv(
        "GEMINI_MODEL_CHAIN",
        "gemini-3.5-flash,gemini-3.5-flash-lite,gemini-2.5-flash-lite,gemini-3.1-flash-lite"
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

# Optional agent-expansion features. They are independently switchable so a
# desktop installation can disable a nonessential capability without changing
# its existing Excel execution path.
ENABLE_TASK_PLANNER = _local_agent_setting("ENABLE_TASK_PLANNER", "true").lower() == "true"
ENABLE_SUBAGENTS = _local_agent_setting("ENABLE_SUBAGENTS", "true").lower() == "true"
ENABLE_SKILL_EXTRACTION = _local_agent_setting("ENABLE_SKILL_EXTRACTION", "true").lower() == "true"
ENABLE_DATA_PROFILING = _local_agent_setting("ENABLE_DATA_PROFILING", "true").lower() == "true"
ENABLE_PDF_REPORTS = _local_agent_setting("ENABLE_PDF_REPORTS", "true").lower() == "true"
ENABLE_SSE_STREAMING = _local_agent_setting("ENABLE_SSE_STREAMING", "true").lower() == "true"
ENABLE_MEMORY_STORAGE = _local_agent_setting("ENABLE_MEMORY_STORAGE", "true").lower() == "true"
MEMORY_STORE_DIR = _local_agent_setting("MEMORY_STORE_DIR", str(Path(__file__).parent / "memory" / "store"))
# Newest entries kept per memory list; older ones are dropped on write so a
# user's memory row stays small (Postgres row, desktop-agent sync payload).
MEMORY_MAX_RECORDS = {
    "chat_memory": int(os.getenv("MEMORY_MAX_CHAT_RECORDS", "200")),
    "task_history": int(os.getenv("MEMORY_MAX_TASK_RECORDS", "300")),
    "skills": int(os.getenv("MEMORY_MAX_SKILLS", "200")),
}
# Past tasks/skills shown to the agent as context for a new request.
MEMORY_CONTEXT_ITEMS = int(os.getenv("MEMORY_CONTEXT_ITEMS", "3"))

# Quick chat (the fast, tool-free conversation route in quick_chat.py).
FAST_CHAT_TIMEOUT_SECONDS = int(os.getenv("FAST_CHAT_TIMEOUT_SECONDS", "25"))
FAST_CHAT_MAX_OUTPUT_TOKENS = int(os.getenv("FAST_CHAT_MAX_OUTPUT_TOKENS", "1200"))
QUICK_CHAT_CLAUDE_MODEL = os.getenv("QUICK_CHAT_CLAUDE_MODEL", "claude-sonnet-4-6")
# Fast model for conversation; on failure quick chat tries GEMINI_MODEL_CHAIN next.
QUICK_CHAT_GEMINI_MODEL = os.getenv("QUICK_CHAT_GEMINI_MODEL", "gemini-2.5-flash-lite")

# Web search. Keyed providers are tried in this order, then DuckDuckGo (no
# key; often blocked from cloud hosts). SEARCH_PROVIDER pins a single one.
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
BRAVE_SEARCH_API_KEY = os.getenv("BRAVE_SEARCH_API_KEY", "")
SERPER_API_KEY = os.getenv("SERPER_API_KEY", "")
SEARCH_PROVIDER = os.getenv("SEARCH_PROVIDER", "").strip().lower()
# Quick chat may search the web when a question needs current or unfamiliar facts.
QUICK_CHAT_WEB_SEARCH = os.getenv("QUICK_CHAT_WEB_SEARCH", "true").lower() == "true"
QUICK_CHAT_MAX_TOOL_ROUNDS = int(os.getenv("QUICK_CHAT_MAX_TOOL_ROUNDS", "3"))

# Where uploaded file contents live (see blob_store.py): "local" disk under
# STORAGE_DIR, "database" (Postgres; survives restarts on hosts with an
# ephemeral disk), or "s3" (any S3-compatible bucket: AWS, Cloudflare R2, ...).
FILE_STORAGE = os.getenv("FILE_STORAGE", "local").strip().lower()
S3_BUCKET = os.getenv("S3_BUCKET", "")
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "")  # e.g. https://<account>.r2.cloudflarestorage.com
S3_REGION = os.getenv("S3_REGION", "auto")
S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID", "")
S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY", "")
S3_PREFIX = os.getenv("S3_PREFIX", "xelora/")
