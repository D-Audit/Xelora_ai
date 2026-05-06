"""
config.py
Single place every other module reads settings from. Nothing here talks
to Excel, the DB, or the AI - it's pure environment plumbing.
"""

import os
from dotenv import load_dotenv


load_dotenv()

AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
LOCAL_API_KEY = os.getenv("LOCAL_API_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")

MAX_STEPS_PER_TASK = int(os.getenv("MAX_STEPS_PER_TASK", 60))
MAX_RETRIES_PER_ACTION = int(os.getenv("MAX_RETRIES_PER_ACTION", 2))

ENABLE_CODEGEN_LAYER = os.getenv("ENABLE_CODEGEN_LAYER", "true").lower() == "true"
ENABLE_VISUAL_FALLBACK = os.getenv("ENABLE_VISUAL_FALLBACK", "false").lower() == "true"

GEMINI_MODEL_CHAIN = [
    m.strip() for m in os.getenv(
        "GEMINI_MODEL_CHAIN",
        "gemini-2.5-flash-lite,gemini-3.1-flash-lite,gemini-3.5-flash,gemini-3.1-flash-lite"
    ).split(",") if m.strip()
]
# --- Security ---
# If LOCAL_API_KEY is unset, the API is open to anyone who can reach it.
# ALLOW_NO_AUTH must be explicitly set to "true" to run that way on
# purpose (e.g. quick local testing) - otherwise the app refuses to
# start with no key configured, rather than silently running open.
ALLOW_NO_AUTH = os.getenv("ALLOW_NO_AUTH", "false").lower() == "true"

# Comma-separated list of allowed origins for browser-based frontends,
# e.g. "http://localhost:3000,https://app.example.com". Empty = no
# cross-origin browser access at all (fine for an Electron/Tauri
# desktop frontend, which doesn't send an Origin header the same way).
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]

# Simple in-memory rate limit: max requests per API key (or IP, if no
# key) within RATE_LIMIT_WINDOW_SECONDS.
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", 60))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", 60))

# Knowledge-base file ingestion is restricted to this directory (and its
# subfolders) to prevent a file_path like "../../../etc/passwd" or
# "C:\Users\someone_else\Documents\private.xlsx" from reading arbitrary
# files off the machine this server runs on.
KNOWLEDGE_INGEST_ALLOWED_DIR = os.getenv("KNOWLEDGE_INGEST_ALLOWED_DIR", os.path.join(os.path.expanduser("~"), "Documents"))
