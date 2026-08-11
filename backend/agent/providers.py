"""
agent/providers.py
Provider-specific glue for Claude and Gemini. Same pattern as the
original backend - kept isolated here so agent/core.py's loop doesn't
care which provider is active.

Tool list = skill library tools + the code-gen tool + (optionally) the
visual fallback tools, so the AI genuinely sees all three layers as
options every turn, in the priority order explained in the system prompt.
"""

import json
import config
from skills.registry import claude_tools, gemini_tools

CODEGEN_TOOL_CLAUDE = {
    "name": "run_excel_code",
    "description": (
        "Runs real Python (xlwings/openpyxl) against the live workbook for anything "
        "the skill library doesn't cover. Must use native Excel features, never a "
        "precomputed value. Assign your JSON-serializable result to a variable `result`."
    ),
    "input_schema": {
        "type": "object",
        "properties": {"code": {"type": "string", "description": "Python source code to execute."}},
        "required": ["code"],
    },
}

VISION_TOOLS_CLAUDE = []  # superseded by the click_on_screen_element skill (see vision/decision_loop.py),
                          # which wires screenshot -> locate -> click into one atomic, safer skill
                          # instead of exposing raw click_at/type_text coordinates directly to the planner.


def build_claude_tools():
    tools = claude_tools() + [CODEGEN_TOOL_CLAUDE]
    if config.ENABLE_VISUAL_FALLBACK:
        tools += VISION_TOOLS_CLAUDE
    return tools


_GEMINI_UNSUPPORTED_SCHEMA_KEYS = {"default", "additionalProperties", "$schema"}


def _strip_unsupported_schema_keys(schema):
    """The older google.generativeai SDK's Schema proto is much stricter
    than plain JSON-schema (which is all Claude requires). It rejects
    unsupported keywords like 'default', AND it requires every array to
    declare 'items' (including nested arrays-of-arrays) and every field
    to declare a 'type' (no bare '{}' for "any value" fields). This walks
    the schema recursively and patches all of that in one pass, so a new
    skill with a slightly loose schema doesn't need a Gemini-specific
    fix each time it trips a new validation rule."""
    if isinstance(schema, list):
        return [_strip_unsupported_schema_keys(item) for item in schema]
    if not isinstance(schema, dict):
        return schema

    cleaned = {k: v for k, v in schema.items() if k not in _GEMINI_UNSUPPORTED_SCHEMA_KEYS}

    if "properties" in cleaned:
        cleaned["properties"] = {k: _strip_unsupported_schema_keys(v) for k, v in cleaned["properties"].items()}
    if "items" in cleaned:
        cleaned["items"] = _strip_unsupported_schema_keys(cleaned["items"])

    if "type" not in cleaned:
        cleaned["type"] = "string"

    if cleaned["type"] == "array" and "items" not in cleaned:
        cleaned["items"] = {"type": "string"}

    if cleaned["type"] == "object" and "properties" not in cleaned:
        cleaned["properties"] = {}

    return cleaned


def build_gemini_tools():
    merged = gemini_tools()[0]["function_declarations"]
    merged = [
        {**decl, "parameters": _strip_unsupported_schema_keys(decl["parameters"])}
        for decl in merged
    ]
    merged.append({
        "name": CODEGEN_TOOL_CLAUDE["name"],
        "description": CODEGEN_TOOL_CLAUDE["description"],
        "parameters": CODEGEN_TOOL_CLAUDE["input_schema"],
    })
    if config.ENABLE_VISUAL_FALLBACK:
        for t in VISION_TOOLS_CLAUDE:
            merged.append({"name": t["name"], "description": t["description"], "parameters": t["input_schema"]})
    return [{"function_declarations": merged}]


def call_claude(task, system_prompt: str):
    from anthropic import Anthropic

    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system_prompt,
        tools=build_claude_tools(),
        messages=task.messages,
    )
    # Store plain, JSON-serializable dicts instead of raw Anthropic SDK
    # block objects. The Claude API accepts either form as input (a list
    # of dicts is standard, documented usage), so this changes nothing
    # about live behavior - but it means task.messages can now be safely
    # json.dumps()'d for real persistence and later reconstructed into a
    # working conversation after a server restart, instead of only ever
    # being usable within this same process.
    def _serialize_block(block):
        # Handle both pydantic v2 (.model_dump) and older v1-style SDKs
        # (.dict) without guessing which one is installed.
        if hasattr(block, "model_dump"):
            return block.model_dump()
        if hasattr(block, "dict"):
            return block.dict()
        return block  # already a plain dict/primitive

    serializable_content = [_serialize_block(block) for block in response.content]
    task.messages.append({"role": "assistant", "content": serializable_content})

    tool_calls = [b for b in response.content if b.type == "tool_use"]
    text_blocks = [b.text for b in response.content if b.type == "text"]
    return tool_calls, text_blocks, response.stop_reason


def submit_claude_tool_result(task, tool_call, result):
    task.messages.append({
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": tool_call.id, "content": json.dumps(result, default=str)}],
    })


def _clean_gemini_value(value):
    if hasattr(value, "items"):
        return {k: _clean_gemini_value(v) for k, v in value.items()}
    if hasattr(value, "__iter__") and not isinstance(value, str):
        return [_clean_gemini_value(v) for v in value]
    return value


def _convert_history_for_gemini(messages):
    history = []
    for m in messages:
        if isinstance(m["content"], str):
            role = "user" if m["role"] == "user" else "model"
            history.append({"role": role, "parts": [m["content"]]})
    return history


def call_gemini(task, system_prompt: str):
    import time
    import google.generativeai as genai
    from google.api_core.exceptions import ResourceExhausted

    genai.configure(api_key=config.GEMINI_API_KEY)
    last_user_msg = task.messages[-1]["content"]
    tools = build_gemini_tools()
    from google.generativeai.types.generation_types import StopCandidateException

    RETRIES_PER_MODEL = 2
    last_error = None

    for model_offset in range(len(config.GEMINI_MODEL_CHAIN)):
        model_index = (task.gemini_model_index + model_offset) % len(config.GEMINI_MODEL_CHAIN)
        model_name = config.GEMINI_MODEL_CHAIN[model_index]
        model = genai.GenerativeModel(model_name, tools=tools, system_instruction=system_prompt)
        chat = model.start_chat(history=_convert_history_for_gemini(task.messages[:-1]))

        for attempt in range(RETRIES_PER_MODEL):
            try:
                response = chat.send_message(last_user_msg)
                task.gemini_model_index = model_index
                return _parse_gemini_response(task, response)
            except ResourceExhausted as e:
                last_error = e
                wait_seconds = 15
                for detail in getattr(e, "details", []) or []:
                    retry_delay = getattr(detail, "retry_delay", None)
                    if retry_delay is not None:
                        wait_seconds = retry_delay.seconds + 1
                if attempt < RETRIES_PER_MODEL - 1:
                    task.log_step(f"⏸️ '{model_name}' rate-limited - waiting {wait_seconds}s and retrying "
                                   f"the same model once more.")
                    time.sleep(wait_seconds)
                else:
                    task.log_step(f"🔀 '{model_name}' still rate-limited after retrying - "
                                   f"switching to the next model in the fallback chain.")
            except StopCandidateException as e:
                last_error = e
                if attempt < RETRIES_PER_MODEL - 1:
                    task.log_step(f"⚠️ '{model_name}' produced a malformed function call - retrying once more.")
                else:
                    task.log_step(f"🔀 '{model_name}' keeps producing malformed function calls - "
                                   f"switching to the next model in the fallback chain.")

    raise last_error


def _parse_gemini_response(task, response):
    parts = response.candidates[0].content.parts
    function_calls, text_parts = [], []
    for part in parts:
        fc = getattr(part, "function_call", None)
        if fc and fc.name:
            function_calls.append(fc)
        else:
            t = getattr(part, "text", None)
            if t:
                text_parts.append(t)

    if function_calls:
        return function_calls, text_parts, "tool_use"

    combined_text = " ".join(text_parts)
    task.messages.append({"role": "assistant", "content": combined_text})
    return [], [combined_text], "end_turn"


def submit_gemini_tool_result(task, tool_call, result):
    try:
        result_text = json.dumps(result, default=str)
    except TypeError:
        result_text = str(result)
    task.messages.append({"role": "user", "content": f"Tool '{tool_call.name}' returned: {result_text}"})


def gemini_tool_input(tool_call) -> dict:
    return {k: _clean_gemini_value(v) for k, v in tool_call.args.items()}