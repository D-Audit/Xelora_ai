"""
config.py
Single place every other module reads settings from. Nothing here talks
to Excel, the DB, or the AI - it's pure environment plumbing.
"""

import os
from pathlib import Path
from dotenv import load_dotenv


load_dotenv(Path(__file__).with_name(".env"))

AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
LOCAL_API_KEY = os.getenv("LOCAL_API_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")

MAX_STEPS_PER_TASK = int(os.getenv("MAX_STEPS_PER_TASK", 60))
MAX_RETRIES_PER_ACTION = int(os.getenv("MAX_RETRIES_PER_ACTION", 2))

ENABLE_CODEGEN_LAYER = os.getenv("ENABLE_CODEGEN_LAYER", "true").lower() == "true"
ENABLE_VISUAL_FALLBACK = os.getenv("ENABLE_VISUAL_FALLBACK", "false").lower() == "true"
VISUAL_ONLY_MODE = os.getenv("VISUAL_ONLY_MODE", "false").lower() == "true"
OMNIPARSER_URL = os.getenv("OMNIPARSER_URL", "http://127.0.0.1:8000/parse/")
OMNIPARSER_TIMEOUT_SECONDS = int(os.getenv("OMNIPARSER_TIMEOUT_SECONDS", "120"))

GEMINI_MODEL_CHAIN = [
    m.strip() for m in os.getenv(
        "GEMINI_MODEL_CHAIN",
        "gemini-2.5-flash-lite,gemini-3.5-flash,gemini-3.5-flash,gemini-3.1-flash-lite"
    ).split(",") if m.strip()
]
ALLOW_NO_AUTH = os.getenv("ALLOW_NO_AUTH", "false").lower() == "true"

ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]

RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", 60))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", 60))

KNOWLEDGE_INGEST_ALLOWED_DIR = os.getenv("KNOWLEDGE_INGEST_ALLOWED_DIR", os.path.join(os.path.expanduser("~"), "Documents"))
