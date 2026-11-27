"""
agent/openai_responses.py
OpenAI (GPT) client for Xelora, on the Responses API (POST /v1/responses).

Current GPT models (the GPT-6.x family) support tool calling only through the
Responses API, not Chat Completions, so this module speaks that protocol for
both the Excel agent loop (agent/providers.py) and quick chat (quick_chat.py).

What lives here is protocol, not judgment:
  * tool declarations converted to Responses "function" tools, with schemas
    patched where OpenAI is stricter than other providers (an array must
    declare ``items``), and the catalogue kept within OpenAI's tool limit;
  * the conversation stored in ``task.messages`` replayed as Responses input
    items, guaranteeing every function_call has exactly one output (a paused
    task can stop between calls; OpenAI rejects a call left without one);
  * one HTTP request with clear, provider-neutral errors, which also drops an
    optional parameter (reasoning effort, encrypted reasoning) when a model
    reports that it does not support it, rather than failing the whole turn.
"""
from __future__ import annotations

import copy
import json
import logging

import config

logger = logging.getLogger(__name__)

# Key under which task.messages stores native Responses items.
ITEMS_KEY = "_openai_items"

# Item types replayed from a model response. Anything else (for example a
# hosted tool call Xelora never requested) is not part of Xelora's protocol.
_REPLAYED_OUTPUT_TYPES = {"reasoning", "message", "function_call"}

# A permissive element type for arrays whose schema forgot ``items``.
_ANY_SCALAR = {"type": ["string", "number", "integer", "boolean", "null"]}

# Optional request fields a model may refuse. Removing one is always safe:
# the request keeps its meaning, only its tuning or caching changes.
_OPTIONAL_FIELDS = ("reasoning", "include", "parallel_tool_calls")

_NOT_EXECUTED_OUTPUT = json.dumps({
    "verified": False,
    "status": "not_executed",
    "error": "This tool call was not executed: the task paused or stopped before reaching it.",
})


class OpenAIError(RuntimeError):
    """A failed OpenAI request with its HTTP status and OpenAI error code."""

    def __init__(self, message: str, *, status: int | None = None, code: str = "", param: str = ""):
        super().__init__(message)
        self.status = status
        self.code = code or ""
        self.param = param or ""

    @property
    def model_unavailable(self) -> bool:
        """The model id is unknown to (or not enabled on) this API key."""
        return self.status == 404 or self.code == "model_not_found" or (
            self.status == 400 and self.param == "model"
        )

    @property
    def retry_next_model(self) -> bool:
        """Another model in the chain may succeed where this one did not."""
        return self.model_unavailable or self.status in {408, 409, 429, 500, 502, 503, 504}


# ── Tool declarations ───────────────────────────────────────────────────────

def openai_schema(schema) -> dict:
    """Return a copy of a JSON Schema that OpenAI's function tools accept.

    OpenAI accepts ordinary JSON Schema in non-strict mode but rejects an
    array without ``items`` (Xelora's write_table rows use one) and needs an
    object at the top level.
    """
    cleaned = copy.deepcopy(schema) if isinstance(schema, dict) else {}

    def patch(node):
        if isinstance(node, dict):
            node_type = node.get("type")
            is_array = node_type == "array" or (isinstance(node_type, list) and "array" in node_type)
            if is_array and "items" not in node:
                node["items"] = dict(_ANY_SCALAR)
            for value in node.values():
                patch(value)
        elif isinstance(node, list):
            for value in node:
                patch(value)

    patch(cleaned)
    if cleaned.get("type") != "object":
        cleaned = {"type": "object", "properties": {"value": cleaned}} if cleaned else {"type": "object"}
    if not isinstance(cleaned.get("properties"), dict):
        cleaned["properties"] = {}
    return cleaned


def function_tools(declarations: list[dict], *, drop_first: set[str] | frozenset = frozenset(),
                   limit: int | None = None) -> tuple[list[dict], list[str]]:
    """Convert Claude-style declarations to Responses function tools.

    ``limit`` keeps the catalogue within OpenAI's per-request tool limit.
    When it is exceeded, tools named in ``drop_first`` go first, latest
    first (callers list the slowest, last-resort controls there); then the
    end of the catalogue, which holds the lowest-priority layers. Returns
    (tools, dropped_names).
    """
    tools = [
        {
            "type": "function",
            "name": str(item["name"]),
            "description": str(item.get("description") or ""),
            "parameters": openai_schema(item.get("input_schema") or {}),
            "strict": False,
        }
        for item in declarations
    ]
    dropped: list[str] = []
    limit = limit if limit is not None else config.OPENAI_MAX_TOOLS
    if limit and len(tools) > limit:
        for index in range(len(tools) - 1, -1, -1):
            if len(tools) <= limit:
                break
            if tools[index]["name"] in drop_first:
                dropped.append(tools.pop(index)["name"])
        while len(tools) > limit:
            dropped.append(tools.pop()["name"])
    return tools, dropped


# ── Conversation replay ────────────────────────────────────────────────────

def replayable_output(output: list) -> list[dict]:
    """The response items to keep in history for the next request.

    Item ids are dropped from messages and function calls: with ``store``
    off, OpenAI cannot resolve an id it never persisted. Reasoning items keep
    theirs, because their encrypted content is bound to it; one without
    encrypted content can only be replayed when responses are stored.
    """
    kept = []
    for item in output or []:
        if not isinstance(item, dict) or item.get("type") not in _REPLAYED_OUTPUT_TYPES:
            continue
        item = {key: value for key, value in item.items() if key != "status"}
        if item["type"] == "reasoning":
            if not config.OPENAI_STORE and not item.get("encrypted_content"):
                continue
            item.setdefault("summary", [])
        else:
            item.pop("id", None)
        kept.append(item)
    return kept


def _text_of(content) -> str:
    """Plain text from a non-OpenAI message payload (provider handoff, legacy turns)."""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        return str(content.get("text") or "")
    if isinstance(content, list):
        return " ".join(
            str(block.get("text"))
            for block in content
            if isinstance(block, dict) and block.get("type") == "text" and block.get("text")
        )
    return ""


def input_items(messages: list[dict], *, include_reasoning: bool = True) -> list[dict]:
    """Rebuild Responses input items from ``task.messages``.

    Pairs every function_call with exactly one function_call_output: a call
    the task never ran (it paused or stopped mid-batch) gets an explicit
    "not executed" output, and an output whose call is no longer in history
    is dropped. OpenAI rejects a request that breaks either rule.
    """
    items: list[dict] = []
    pending: list[str] = []
    seen_calls: set[str] = set()
    answered: set[str] = set()

    def settle_pending():
        for call_id in pending:
            items.append({"type": "function_call_output", "call_id": call_id, "output": _NOT_EXECUTED_OUTPUT})
            answered.add(call_id)
        pending.clear()

    for message in messages or []:
        content = message.get("content")
        if isinstance(content, dict) and isinstance(content.get(ITEMS_KEY), list):
            new_items = [item for item in content[ITEMS_KEY] if isinstance(item, dict)]
        else:
            text = _text_of(content).strip()
            role = "assistant" if message.get("role") == "assistant" else "user"
            new_items = [{"role": role, "content": text}] if text else []

        for item in new_items:
            kind = item.get("type")
            if kind == "function_call_output":
                call_id = item.get("call_id")
                if call_id not in seen_calls or call_id in answered:
                    continue
                answered.add(call_id)
                if call_id in pending:
                    pending.remove(call_id)
                items.append(item)
                continue
            if kind == "reasoning" and not include_reasoning:
                continue
            if pending and kind not in {"function_call", "reasoning"}:
                settle_pending()
            if kind == "function_call":
                call_id = item.get("call_id")
                if not call_id or call_id in seen_calls:
                    continue
                seen_calls.add(call_id)
                pending.append(call_id)
            items.append(item)
    settle_pending()
    return items


def function_call_output(call_id: str, result) -> dict:
    return {"type": "function_call_output", "call_id": call_id, "output": json.dumps(result, default=str)}


# ── Response parsing ───────────────────────────────────────────────────────

def parse_output(data: dict) -> tuple[list[dict], str]:
    """Return (function calls as {"name", "arguments", "id"}, text) from a response."""
    calls, texts = [], []
    for item in data.get("output") or []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "function_call":
            raw = item.get("arguments") or "{}"
            try:
                arguments = json.loads(raw) if isinstance(raw, str) else dict(raw)
            except (TypeError, ValueError):
                logger.warning("OpenAI returned unparseable arguments for %s", item.get("name"))
                arguments = {}
            if not isinstance(arguments, dict):
                arguments = {}
            calls.append({"name": str(item.get("name") or ""), "arguments": arguments,
                          "id": str(item.get("call_id") or "")})
        elif item.get("type") == "message":
            for part in item.get("content") or []:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "output_text" and part.get("text"):
                    texts.append(str(part["text"]))
                elif part.get("type") == "refusal" and part.get("refusal"):
                    texts.append(str(part["refusal"]))
    return calls, "\n".join(text.strip() for text in texts if text.strip())


# ── HTTP ────────────────────────────────────────────────────────────────────

def _error_from(response) -> OpenAIError:
    try:
        error = (response.json() or {}).get("error") or {}
    except ValueError:
        error = {}
    message = str(error.get("message") or response.text[:300] or "no error message")
    code = str(error.get("code") or error.get("type") or "")
    param = str(error.get("param") or "")
    status = response.status_code
    if status == 401:
        text = "OpenAI rejected the API key (HTTP 401). Check OPENAI_API_KEY in backend/.env."
    elif status == 429 and code == "insufficient_quota":
        text = "OpenAI quota exhausted (HTTP 429 insufficient_quota): add billing credit to the OpenAI account."
    elif status == 429:
        text = f"OpenAI rate limit reached (HTTP 429): {message}"
    elif status >= 500:
        text = f"OpenAI service unavailable (HTTP {status}): {message}"
    else:
        text = f"OpenAI request failed (HTTP {status}{', ' + code if code else ''}): {message}"
    return OpenAIError(text, status=status, code=code, param=param)


def _unsupported_optional_field(error: OpenAIError, payload: dict) -> str | None:
    """The optional field a 400 response says this model does not support."""
    if error.status != 400:
        return None
    detail = f"{error.param} {error}".lower()
    for field in _OPTIONAL_FIELDS:
        if field in payload and (error.param.split(".")[0] == field or f"'{field}" in detail or f"{field}." in detail):
            return field
    return None


def create_response(payload: dict, *, timeout: float) -> dict:
    """POST /responses once, removing optional fields a model rejects.

    Raises OpenAIError for an HTTP error, and the requests exception for a
    network failure or timeout (callers treat both as provider availability).
    """
    import requests

    if not config.OPENAI_API_KEY:
        raise OpenAIError("OPENAI_API_KEY is not configured.", status=401)
    payload = dict(payload)
    headers = {"Authorization": f"Bearer {config.OPENAI_API_KEY}", "Content-Type": "application/json"}
    for _ in range(len(_OPTIONAL_FIELDS) + 2):
        response = requests.post(f"{config.OPENAI_BASE_URL}/responses", headers=headers,
                                 json=payload, timeout=max(1.0, timeout))
        if response.status_code < 400:
            return response.json()
        error = _error_from(response)
        field = _unsupported_optional_field(error, payload)
        if field is None:
            raise error
        logger.info("OpenAI model %s does not support %r; retrying without it.", payload.get("model"), field)
        payload.pop(field)
        if field == "include":
            # Encrypted reasoning cannot be replayed without being requested.
            payload["input"] = [item for item in payload.get("input", []) if item.get("type") != "reasoning"]
    raise error


def base_payload(model: str, instructions: str, items: list[dict], *, max_output_tokens: int,
                 reasoning_effort: str = "") -> dict:
    """The fields every Xelora request sends."""
    payload = {
        "model": model,
        "instructions": instructions,
        "input": items,
        "max_output_tokens": max_output_tokens,
        "store": config.OPENAI_STORE,
    }
    if reasoning_effort:
        payload["reasoning"] = {"effort": reasoning_effort}
    if not config.OPENAI_STORE:
        # Stateless requests replay reasoning between tool calls, so a
        # reasoning model keeps its chain of thought across a multi-step task.
        payload["include"] = ["reasoning.encrypted_content"]
    return payload
