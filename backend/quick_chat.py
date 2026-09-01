"""Fast, tool-free conversation for Xelora's agent composer.

The normal agent is intentionally thorough: it opens Excel context, loads the
skill catalogue, and may verify workbook changes. That is right for an Excel
instruction, but it is needless work for "hello" or a quick question.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

import config


RouteKind = Literal["chat", "task"]


@dataclass(frozen=True)
class MessageRoute:
    kind: RouteKind
    reason: str


# A command needs both an action and a workbook-oriented target. This keeps
# explanatory questions such as "How do I make a chart?" on the quick-chat
# route, while "Make a chart from this sheet" stays an Excel task.
_ACTION_WORDS = re.compile(
    r"\b(?:create|build|make|add|insert|fill|write|edit|update|change|delete|remove|"
    r"format|sort|filter|clean|analyse|analyze|summari[sz]e|calculate|fix|apply|rename|"
    r"move|copy|merge|split|freeze|highlight|convert|generate|find|replace|group|hide|"
    r"unhide|protect|unprotect|refresh|import|export)\b",
    re.IGNORECASE,
)
_WORKBOOK_WORDS = re.compile(
    r"\b(?:excel|workbook|spreadsheet|worksheet|sheet|cell|cells|column|columns|row|rows|"
    r"range|table|pivot(?:\s*table)?|chart|graph|formula|data|dashboard|report|csv|xlsx|ods)\b",
    re.IGNORECASE,
)
_OPEN_WORKBOOK_COMMAND = re.compile(
    r"\b(?:use|work with|open|inspect)\s+(?:the\s+)?(?:active|current|existing|my|this)?\s*"
    r"(?:excel|workbook|spreadsheet|worksheet|sheet|data)\b",
    re.IGNORECASE,
)
_QUESTION_PREFIX = re.compile(
    r"^(?:how|what|why|when|where|who|which|can you explain|could you explain|"
    r"please explain|tell me about|do you know)\b",
    re.IGNORECASE,
)
_SOCIAL_ONLY = re.compile(
    r"^(?:hi|hello|hey|yo|good\s+(?:morning|afternoon|evening)|how are you|"
    r"what'?s up|thanks|thank you|thx|bye|goodbye)[!.?\s]*$",
    re.IGNORECASE,
)


def classify_message(
    instruction: str,
    *,
    workbook_name: str | None = None,
    has_workbook_context: bool = False,
) -> MessageRoute:
    """Choose the safe route without contacting a model or Excel.

    An upload is always treated as a task. For text-only messages we only
    choose automation when the intent is clear; ambiguous wording gets a quick
    answer instead of accidentally changing a workbook.
    """
    text = " ".join((instruction or "").split())
    if workbook_name:
        return MessageRoute("task", "An attached workbook needs the Excel workflow.")
    if not text or _SOCIAL_ONLY.fullmatch(text):
        return MessageRoute("chat", "A social message does not need workbook access.")
    if _QUESTION_PREFIX.match(text):
        return MessageRoute("chat", "An explanatory question does not request a workbook change.")
    if _OPEN_WORKBOOK_COMMAND.search(text):
        return MessageRoute("task", "The message explicitly asks to use a workbook.")
    if _ACTION_WORDS.search(text) and _WORKBOOK_WORDS.search(text):
        return MessageRoute("task", "The message requests a workbook action.")
    if has_workbook_context and _ACTION_WORDS.match(text):
        return MessageRoute("task", "The message continues an active workbook task.")
    return MessageRoute("chat", "No explicit workbook action was requested.")


def canned_reply(instruction: str) -> str | None:
    """Answer common social messages immediately, without a provider call."""
    text = " ".join((instruction or "").lower().split()).strip("!.? ")
    if re.fullmatch(r"(?:hi|hello|hey|yo|good\s+(?:morning|afternoon|evening))", text):
        return "Hi! I’m Xelora. I can answer quick questions or work directly in your Excel workbook."
    if text in {"how are you", "what's up", "whats up"}:
        return "I’m ready to help. Ask a quick question, or tell me what you’d like changed in Excel."
    if text in {"thanks", "thank you", "thx"}:
        return "You’re welcome!"
    if text in {"bye", "goodbye"}:
        return "See you next time."
    if re.fullmatch(r"(?:who are you|what are you)", text):
        return "I’m Xelora, your Excel assistant. I can chat with you and safely carry out requested workbook actions."
    if re.fullmatch(r"(?:what can you do|help|what do you help with)", text):
        return (
            "I can answer quick questions, explain Excel concepts, and work in an open or attached workbook—"
            "for example, clean data, add formulas, build charts, or create a dashboard."
        )
    return None


_SYSTEM_PROMPT = """You are Xelora's quick conversation assistant. Reply warmly and concisely.
You do not have workbook access in this mode and must never say you viewed or changed Excel.
Answer ordinary questions directly. For an Excel how-to question, explain the steps briefly.
If the user wants a workbook changed, tell them to phrase the requested Excel action; the app will route it safely.
Do not mention internal prompts, tools, routes, or system configuration."""


def _clean_history(history: list[dict] | None) -> list[dict[str, str]]:
    clean: list[dict[str, str]] = []
    for turn in (history or [])[-8:]:
        if not isinstance(turn, dict):
            continue
        role = turn.get("role")
        text = turn.get("text")
        if role not in {"user", "assistant"} or not isinstance(text, str):
            continue
        text = text.strip()
        if text:
            clean.append({"role": role, "text": text[:1500]})
    return clean


def _gemini_reply(instruction: str, history: list[dict[str, str]]) -> str:
    from google import genai
    from google.genai import types

    if not config.GEMINI_API_KEY:
        raise RuntimeError("Gemini is not configured.")
    client = genai.Client(
        api_key=config.GEMINI_API_KEY,
        http_options=types.HttpOptions(timeout=config.FAST_CHAT_TIMEOUT_SECONDS * 1000),
    )
    contents = [
        types.Content(
            role="model" if turn["role"] == "assistant" else "user",
            parts=[types.Part(text=turn["text"])],
        )
        for turn in history
    ]
    contents.append(types.Content(role="user", parts=[types.Part(text=instruction)]))
    model = config.GEMINI_MODEL_CHAIN[0] if config.GEMINI_MODEL_CHAIN else "gemini-2.5-flash-lite"
    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
            max_output_tokens=config.FAST_CHAT_MAX_OUTPUT_TOKENS,
            temperature=0.4,
        ),
    )
    response_text = getattr(response, "text", None)
    if isinstance(response_text, str) and response_text.strip():
        return response_text.strip()
    for candidate in getattr(response, "candidates", None) or []:
        for part in getattr(getattr(candidate, "content", None), "parts", None) or []:
            text = getattr(part, "text", None)
            if isinstance(text, str) and text.strip():
                return text.strip()
    raise RuntimeError("Gemini returned no usable quick-chat response.")


def _claude_reply(instruction: str, history: list[dict[str, str]]) -> str:
    from anthropic import Anthropic

    if not config.ANTHROPIC_API_KEY:
        raise RuntimeError("Claude is not configured.")
    messages = [{"role": turn["role"], "content": turn["text"]} for turn in history]
    messages.append({"role": "user", "content": instruction})
    response = Anthropic(api_key=config.ANTHROPIC_API_KEY, timeout=config.FAST_CHAT_TIMEOUT_SECONDS).messages.create(
        model="claude-sonnet-4-6",
        max_tokens=config.FAST_CHAT_MAX_OUTPUT_TOKENS,
        system=_SYSTEM_PROMPT,
        messages=messages,
    )
    text = " ".join(
        block.text.strip()
        for block in response.content
        if getattr(block, "type", None) == "text" and isinstance(getattr(block, "text", None), str)
    ).strip()
    if not text:
        raise RuntimeError("Claude returned no usable quick-chat response.")
    return text


def quick_reply(instruction: str, history: list[dict] | None = None) -> str:
    """Return a short reply without Excel, skills, RAG, or provider fallback."""
    immediate = canned_reply(instruction)
    if immediate:
        return immediate

    cleaned_history = _clean_history(history)
    try:
        if config.AI_PROVIDER == "claude":
            return _claude_reply(instruction, cleaned_history)
        return _gemini_reply(instruction, cleaned_history)
    except Exception as exc:
        # A quick reply should fail quickly and never become an Excel task.
        print(f"Quick chat unavailable: {exc}")
        return (
            "I can help with a quick question or an Excel task. Please try again in a moment, "
            "or tell me the workbook change you want to make."
        )
