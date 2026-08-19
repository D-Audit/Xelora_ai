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
from dataclasses import dataclass

import requests

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

VISION_TOOLS_CLAUDE = [
    {
        "name": "parse_screen",
        "description": "Focuses Excel and asks OmniParser to identify UI elements. Use zone='ribbon' for Excel tabs/commands, zone='popup' for a dialog, and zone='window' only when neither narrow zone applies. Observe before acting; use returned element centers for clicks.",
        "input_schema": {"type": "object", "properties": {"zone": {"type": "string", "description": "One of: ribbon, popup, window."}}},
    },
    {
        "name": "click", "description": "Clicks the center of an element returned by the most recent parse_screen call. Never invent coordinates.",
        "input_schema": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}}, "required": ["x", "y"]},
    },
    {
        "name": "double_click", "description": "Double-clicks the center of an element returned by the most recent parse_screen call.",
        "input_schema": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}}, "required": ["x", "y"]},
    },
    {
        "name": "type_text", "description": "Types text into the currently focused control.",
        "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
    },
    {
        "name": "press_key", "description": "Presses one keyboard key, for example enter, tab, esc, or f2.",
        "input_schema": {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]},
    },
    {
        "name": "hotkey", "description": "Presses a keyboard shortcut, for example ctrl+s or alt+h.",
        "input_schema": {"type": "object", "properties": {"keys": {"type": "array", "items": {"type": "string"}}}, "required": ["keys"]},
    },
    {
        "name": "go_to_range", "description": "Uses Excel's Go To / Name Box behavior (Ctrl+G) to select a valid cell, range, whole column range, or defined name without visual parsing. Quote sheet names containing spaces, for example 'Sales Data'!A1 or 'Sales Data'!A:M.",
        "input_schema": {"type": "object", "properties": {"reference": {"type": "string"}}, "required": ["reference"]},
    },
    {
        "name": "paste_table", "description": "Pastes a complete rectangular data table into Excel in one atomic action. Use this for any headers plus multiple rows; never enter a table cell by cell.",
        "input_schema": {"type": "object", "properties": {"headers": {"type": "array", "items": {"type": "string"}}, "rows": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}}, "start_cell": {"type": "string"}}, "required": ["headers", "rows"]},
    },
    {"name": "fill_formula_down", "description": "Writes a formula to one cell and fills it down a single column through an end cell.", "input_schema": {"type": "object", "properties": {"start_cell": {"type": "string"}, "end_cell": {"type": "string"}, "formula": {"type": "string"}}, "required": ["start_cell", "end_cell", "formula"]}},
    {"name": "format_currency", "description": "Applies Excel's currency format to a valid selected range.", "input_schema": {"type": "object", "properties": {"reference": {"type": "string"}}, "required": ["reference"]}},
    {"name": "format_bold", "description": "Makes a valid Excel range bold.", "input_schema": {"type": "object", "properties": {"reference": {"type": "string"}}, "required": ["reference"]}},
    {"name": "autofit_columns", "description": "AutoFits the columns containing a valid Excel range.", "input_schema": {"type": "object", "properties": {"reference": {"type": "string"}}, "required": ["reference"]}},
    {"name": "create_clustered_column_chart", "description": "Creates a clustered column chart from a prepared two-column source range with headers.", "input_schema": {"type": "object", "properties": {"reference": {"type": "string"}}, "required": ["reference"]}},
    {
        "name": "scroll", "description": "Scrolls the current screen. Positive clicks scroll up and negative clicks scroll down.",
        "input_schema": {"type": "object", "properties": {"clicks": {"type": "integer"}}, "required": ["clicks"]},
    },
]


def build_claude_tools():
    if config.VISUAL_ONLY_MODE:
        return VISION_TOOLS_CLAUDE
    tools = claude_tools()
    if config.ENABLE_CODEGEN_LAYER:
        tools.append(CODEGEN_TOOL_CLAUDE)
    if config.ENABLE_VISUAL_FALLBACK:
        tools += VISION_TOOLS_CLAUDE
    return tools


_OPENROUTER_CORE_TOOLS = {
    # The minimum reliable workflow for nearly every structured Excel task.
    "get_excel_version", "inspect_workbook", "read_range", "create_sheet", "rename_sheet",
    "copy_sheet", "reorder_sheet", "write_cell", "write_table", "clear_range",
    "insert_formula", "apply_formatting", "format_range", "auto_fit_columns",
    "conditional_formatting", "create_chart", "modify_chart", "position_chart",
    "delete_chart", "freeze_panes", "set_autofilter", "sort_range", "filter_data",
    # This is the universal fallback when a specialised skill is not offered.
    "run_excel_code",
}

_OPENROUTER_INTENT_GROUPS = (
    (
        {"add_sparkline", "add_slicer", "add_shape", "create_chart", "modify_chart", "position_chart"},
        ("dashboard", "chart", "graph", "visual", "kpi", "sparkline", "slicer"),
    ),
    (
        {"color_scale_formatting", "data_bar_formatting", "icon_set_formatting", "format_currency", "format_bold", "autofit_columns"},
        ("format", "colour", "color", "currency", "percent", "percentage", "highlight", "conditional", "professional"),
    ),
    (
        {"create_pivot_table", "refresh_pivot_table", "add_slicer"},
        ("pivot", "slicer"),
    ),
    (
        {"data_validation", "add_dropdown_control", "remove_duplicates", "find_replace", "split_column", "merge_columns"},
        ("validation", "dropdown", "duplicate", "replace", "split column", "merge column", "clean data"),
    ),
    (
        {"insert_row", "insert_column", "delete_row", "delete_column", "group_rows_columns", "merge_cells", "unmerge_cells"},
        ("insert row", "insert column", "delete row", "delete column", "group", "merge cells", "unmerge"),
    ),
    (
        {"create_named_range", "set_sheet_visibility", "protect_sheet", "unprotect_sheet", "set_page_layout", "export_to_pdf"},
        ("named range", "hide sheet", "show sheet", "protect", "password", "page layout", "print", "pdf"),
    ),
    (
        {"open_workbook", "create_new_workbook", "combine_sheets", "import_from_database", "import_unstructured_document", "fetch_live_data"},
        ("open workbook", "new workbook", "combine", "database", "import", "pdf document", "live data", "external data"),
    ),
    (
        {"add_comment", "add_hyperlink", "insert_picture"},
        ("comment", "hyperlink", "link", "picture", "image", "logo"),
    ),
    (
        {"check_vba_access", "create_vba_macro", "delete_vba_macro", "list_vba_macros", "run_macro", "save_as_macro_enabled", "add_macro_button"},
        ("vba", "macro", "xlsm"),
    ),
    (
        {"parse_screen", "click", "double_click", "type_text", "press_key", "hotkey", "go_to_range", "paste_table", "fill_formula_down", "format_currency", "format_bold", "autofit_columns", "create_clustered_column_chart", "scroll"},
        ("click", "ribbon", "dialog", "screen", "shortcut", "keyboard", "go to", "visual only"),
    ),
)


def _openrouter_intent_text(task) -> str:
    """Use the original goal and later user instructions to select tools."""
    messages = getattr(task, "messages", []) if task is not None else []
    text_parts = [str(getattr(task, "instruction", ""))]
    for message in messages:
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, str):
            text_parts.append(content)
    return "\n".join(text_parts).lower()


def _select_openrouter_tools(tools, task=None):
    """Fit the task's tools under the provider limit without losing code fallback."""
    if len(tools) <= config.OPENROUTER_MAX_TOOLS:
        return tools

    intent = _openrouter_intent_text(task)
    selected_names = set(_OPENROUTER_CORE_TOOLS)
    for group_tools, terms in _OPENROUTER_INTENT_GROUPS:
        if any(term in intent for term in terms):
            selected_names.update(group_tools)

    selected = [tool for tool in tools if tool["name"] in selected_names]
    if len(selected) > config.OPENROUTER_MAX_TOOLS:
        # Core tools occur first so an overly broad request retains the most
        # dependable tools and can still use run_excel_code for the rest.
        core = [tool for tool in selected if tool["name"] in _OPENROUTER_CORE_TOOLS]
        extras = [tool for tool in selected if tool["name"] not in _OPENROUTER_CORE_TOOLS]
        selected = (core + extras)[:config.OPENROUTER_MAX_TOOLS]

    return selected


def build_openrouter_tools(task=None):
    """Translate only task-relevant Claude-style tools to OpenAI/OpenRouter format."""
    selected_tools = _select_openrouter_tools(build_claude_tools(), task)
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"],
            },
        }
        for tool in selected_tools
    ]


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
    if config.VISUAL_ONLY_MODE:
        return [{"function_declarations": [
            {"name": t["name"], "description": t["description"], "parameters": _strip_unsupported_schema_keys(t["input_schema"])}
            for t in VISION_TOOLS_CLAUDE
        ]}]
    merged = gemini_tools()[0]["function_declarations"]
    merged = [
        {**decl, "parameters": _strip_unsupported_schema_keys(decl["parameters"])}
        for decl in merged
    ]
    if config.ENABLE_CODEGEN_LAYER:
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
    def _serialize_block(block):
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


@dataclass
class OpenRouterToolCall:
    id: str
    name: str
    input: dict


def call_openrouter(task, system_prompt: str):
    """Call an OpenRouter model through its OpenAI-compatible chat endpoint."""
    if not config.OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not configured.")

    tools = build_openrouter_tools(task)
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": config.OPENROUTER_MODEL,
            "messages": [{"role": "system", "content": system_prompt}, *task.messages],
            "tools": tools,
            "tool_choice": "auto",
            "max_tokens": 1024,
        },
        timeout=config.OPENROUTER_TIMEOUT_SECONDS,
    )
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        detail = response.text[:500]
        raise RuntimeError(f"OpenRouter request failed ({response.status_code}): {detail}") from exc

    payload = response.json()
    choices = payload.get("choices") or []
    if not choices or not isinstance(choices[0].get("message"), dict):
        raise RuntimeError("OpenRouter returned no assistant message.")

    choice = choices[0]
    message = choice["message"]
    # Keep only request-compatible fields; provider response metadata must not
    # be sent back on the next tool-execution turn.
    assistant_message = {"role": "assistant", "content": message.get("content")}
    if message.get("tool_calls"):
        assistant_message["tool_calls"] = message["tool_calls"]
    task.messages.append(assistant_message)
    text = message.get("content")
    text_blocks = [text] if isinstance(text, str) and text else []
    tool_calls = []

    for tool_call in message.get("tool_calls") or []:
        function = tool_call.get("function") or {}
        name = function.get("name")
        arguments = function.get("arguments", "{}")
        if not tool_call.get("id") or not name:
            continue
        try:
            tool_input = json.loads(arguments) if isinstance(arguments, str) else arguments
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"OpenRouter returned invalid arguments for tool '{name}'.") from exc
        if not isinstance(tool_input, dict):
            raise RuntimeError(f"OpenRouter returned non-object arguments for tool '{name}'.")
        tool_calls.append(OpenRouterToolCall(id=tool_call["id"], name=name, input=tool_input))

    return tool_calls, text_blocks, choice.get("finish_reason", "stop")


def submit_openrouter_tool_result(task, tool_call, result):
    task.messages.append({
        "role": "tool",
        "tool_call_id": tool_call.id,
        "content": json.dumps(result, default=str),
    })


def tool_input(tool_call) -> dict:
    """Return a provider-neutral mapping of the tool arguments."""
    if config.AI_PROVIDER in {"claude", "openrouter"}:
        return dict(tool_call.input)
    return gemini_tool_input(tool_call)


def submit_tool_result(task, tool_call, result):
    """Append a tool result in the conversation format expected by the active provider."""
    if config.AI_PROVIDER == "claude":
        submit_claude_tool_result(task, tool_call, result)
    elif config.AI_PROVIDER == "openrouter":
        submit_openrouter_tool_result(task, tool_call, result)
    else:
        submit_gemini_tool_result(task, tool_call, result)


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

    # Desktop work must not appear frozen while an external service waits for
    # quota. Try each configured fallback once, then return the real error.
    RETRIES_PER_MODEL = 1
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
                if attempt < RETRIES_PER_MODEL - 1 and config.GEMINI_RATE_LIMIT_WAIT_SECONDS > 0:
                    task.log_step(f"⏸️ '{model_name}' rate-limited - waiting {wait_seconds}s and retrying "
                                   f"the same model once more.")
                    time.sleep(min(wait_seconds, config.GEMINI_RATE_LIMIT_WAIT_SECONDS))
                else:
                    task.log_step(f"🔀 '{model_name}' is rate-limited - switching models without waiting.")
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
