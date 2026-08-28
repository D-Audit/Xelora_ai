"""
agent/providers.py
Provider-specific glue for Claude and Gemini. Same pattern as the
original backend - kept isolated here so agent/core.py's loop doesn't
care which provider is active.

Tool list = skill library tools + the code-gen tool + (optionally) the
visual fallback tools, so the AI genuinely sees all three layers as
options every turn, in the priority order explained in the system prompt.
"""

import base64
import json

import config
from skills.registry import claude_tools, gemini_tools

CODEGEN_TOOL_CLAUDE = {
    "name": "run_excel_code",
    "description": (
        "Runs real Python (xlwings/openpyxl) against the live workbook for anything "
        "the skill library doesn't cover, or for the exact goal of a skill result that "
        "explicitly requires codegen fallback. Must use native Excel features, never a "
        "precomputed value. Allowed imports are xlwings, openpyxl, datetime, math, random, "
        "re, json, and statistics. Never assign .formula or .formula2 here: use the "
        "insert_formula skill (with fill_to for a formula column) so formula writes are "
        "verified safely. Assign a JSON-serializable dictionary to `result`. Only set "
        "`verified: true` after reading back the changed workbook state, and include a "
        "non-empty `verification_note` describing that evidence."
    ),
    "input_schema": {
        "type": "object",
        "properties": {"code": {"type": "string", "description": "Python source code to execute."}},
        "required": ["code"],
    },
}

VISION_TOOLS_CLAUDE = [
    {
        "name": "find_and_click",
        "description": "Find and click a UI element by name. Uses UIA first (fast, no screenshot), then falls back to OmniParser. Use for ribbon tabs, buttons, menu items.",
        "input_schema": {"type": "object", "properties": {"name": {"type": "string", "description": "Name of the element to click (e.g., 'Home', 'Insert', 'Bold')"}, "control_type": {"type": "string", "description": "Optional: TabItem, Button, MenuItem, etc."}, "double": {"type": "boolean", "description": "If true, double-click"}}, "required": ["name"]},
    },
    {
        "name": "click_ribbon_tab",
        "description": "Click a ribbon tab by name. Uses UIA first (fast, no screenshot), then falls back to OmniParser.",
        "input_schema": {"type": "object", "properties": {"tab_name": {"type": "string", "description": "Name of the tab (e.g., 'Home', 'Insert', 'Page Layout', 'Data')"}}, "required": ["tab_name"]},
    },
    {
        "name": "activate_ribbon_tab",
        "description": "Open a ribbon tab using its Excel keyboard shortcut. Use before execute_excel_shortcut when a command lives on a specific tab. This is the keyboard-driven equivalent of click_ribbon_tab.",
        "input_schema": {"type": "object", "properties": {"tab": {"type": "string", "description": "Tab name: home, insert, page_layout, formulas, data, review, view, help"}, "fallback_keys": {"type": "array", "items": {"type": "string"}, "description": "Optional explicit keys (e.g. ['alt','n'] for Insert)"}}, "required": ["tab"]},
    },
    {
        "name": "press_alt",
        "description": "Send an Alt-key ribbon sequence to reach commands without a direct Ctrl shortcut. Example: press_alt(['h','o','i']) opens Format Cells; press_alt(['n','c']) inserts a chart. Use when execute_excel_shortcut lacks the command. This is more reliable than parse_screen for ribbon commands.",
        "input_schema": {"type": "object", "properties": {"keys": {"type": "array", "items": {"type": "string"}, "description": "Keys to send after Alt, e.g. ['h','o','i']"}}, "required": ["keys"]},
    },
    {
        "name": "click_button",
        "description": "Click a button by name. Uses UIA first (fast, no screenshot), then falls back to OmniParser.",
        "input_schema": {"type": "object", "properties": {"button_name": {"type": "string", "description": "Name of the button"}}, "required": ["button_name"]},
    },
    {
        "name": "execute_excel_shortcut",
        "description": "Execute a named Excel keyboard shortcut DIRECTLY (bypasses vision). Use for standard operations: bold, italic, currency, merge, auto-fit, sort, filter, insert chart/table, etc. THIS IS THE FASTEST WAY to perform standard Excel operations.",
        "input_schema": {"type": "object", "properties": {"shortcut_name": {"type": "string", "description": "Shortcut name: bold, italic, underline, currency, percent, comma, center_align, left_align, right_align, all_borders, no_borders, merge_center, unmerge, auto_fit_column, auto_fit_row, sort_ascending, sort_descending, filter, insert_table, insert_column_chart, insert_pie_chart, freeze_panes, copy, cut, paste, paste_values, format_painter, etc."}}, "required": ["shortcut_name"]},
    },
    {
        "name": "batch_excel_operations",
        "description": "Execute multiple Excel operations in sequence without pausing for verification. Use for applying multiple formatting operations, entering data with formulas, etc.",
        "input_schema": {"type": "object", "properties": {"operations": {"type": "array", "items": {"type": "object", "properties": {"type": {"type": "string", "enum": ["shortcut", "alt_sequence", "type_text", "press_key", "go_to_range", "find_and_click"]}, "name": {"type": "string"}, "keys": {"type": "array", "items": {"type": "string"}}, "text": {"type": "string"}, "key": {"type": "string"}, "reference": {"type": "string"}}, "required": ["type"]}}}, "required": ["operations"]},
    },
    {
        "name": "search_cached_elements",
        "description": "Search previously cached screen data for UI elements matching text (no new screenshot needed). Use this before parse_screen to check if the element was already found.",
        "input_schema": {"type": "object", "properties": {"text": {"type": "string", "description": "Text to search for (case-insensitive)"}, "context": {"type": "string", "description": "Optional context filter: ribbon, popup, window"}}, "required": ["text"]},
    },
    {
        "name": "parse_screen",
        "description": "Focuses Excel and asks OmniParser to identify UI elements. USE SPARINGLY - only for new unknown UI elements not found by UIA. Most elements can be found faster via UIA.",
        "input_schema": {"type": "object", "properties": {"zone": {"type": "string", "description": "One of: ribbon, popup, window."}, "use_cache": {"type": "boolean", "description": "If True (default), check cache before taking new screenshot"}}},
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
        "name": "rename_sheet", "description": "Rename an existing worksheet tab. Double-clicks the tab, selects all, types new name, and presses Enter. Use this instead of visual double-clicking which can fail due to stale screens.",
        "input_schema": {"type": "object", "properties": {"old_name": {"type": "string", "description": "Current name of the sheet tab"}, "new_name": {"type": "string", "description": "New name for the sheet"}}, "required": ["old_name", "new_name"]},
    },
    {
        "name": "go_to_sheet", "description": "Switch to a worksheet by clicking its tab via pywinauto. More reliable than using Go To dialog with sheet prefix. Use this before navigating to cells on a different sheet.",
        "input_schema": {"type": "object", "properties": {"sheet_name": {"type": "string", "description": "Name of the sheet to switch to"}}, "required": ["sheet_name"]},
    },
    {
        "name": "navigate_to_cell_on_sheet", "description": "Navigate to a specific cell on a specific sheet. First switches to the sheet via pywinauto, then uses Go To to select the cell. Avoids cross-sheet Go To failures.",
        "input_schema": {"type": "object", "properties": {"sheet_name": {"type": "string", "description": "Name of the sheet"}, "cell": {"type": "string", "description": "Cell reference (default: A1)"}}, "required": ["sheet_name"]},
    },
    {
        "name": "create_pie_chart", "description": "Create a pie chart from a two-column source range with headers. Use for revenue share, distribution, etc.",
        "input_schema": {"type": "object", "properties": {"reference": {"type": "string", "description": "Two-column range with headers (e.g., 'A10:B12')"}}, "required": ["reference"]},
    },
    {
        "name": "verify_task_completion", "description": "Cross-check that all expected deliverables (sheets, data) were created. Call this at the end of a task to verify completeness.",
        "input_schema": {"type": "object", "properties": {"expected_sheets": {"type": "array", "items": {"type": "string"}, "description": "List of sheet names that should exist"}}, "required": []},
    },
    {
        "name": "get_active_sheet_name", "description": "Get the name of the currently active/selected sheet tab. Use to verify you're on the right sheet before pasting data.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "verify_current_sheet", "description": "Verify that the active sheet matches the expected sheet. Call AFTER go_to_sheet and BEFORE paste_table to ensure data goes to the right sheet.",
        "input_schema": {"type": "object", "properties": {"expected_sheet": {"type": "string", "description": "Name of the sheet that should be active"}}, "required": ["expected_sheet"]},
    },
    {
        "name": "get_sheet_info", "description": "Read the structure and content of a sheet. Returns headers, data range, row count, column count, and sample values. Use this to understand what data exists before making changes.",
        "input_schema": {"type": "object", "properties": {"sheet_name": {"type": "string", "description": "Name of the sheet to read. If omitted, reads the active sheet."}}, "required": []},
    },
    {
        "name": "get_cell_value", "description": "Read the value or formula of a specific cell. Use this to verify data before referencing it in formulas.",
        "input_schema": {"type": "object", "properties": {"cell": {"type": "string", "description": "Cell reference like 'A1', 'B3'"}, "sheet_name": {"type": "string", "description": "Optional sheet name. If omitted, reads from active sheet."}}, "required": ["cell"]},
    },
    {
        "name": "apply_cell_style", "description": "Apply styling to a cell or range: bold, italic, font size, colors, number format, alignment.",
        "input_schema": {"type": "object", "properties": {"range_ref": {"type": "string", "description": "Cell or range reference like 'A1:B5'"}, "bold": {"type": "boolean"}, "italic": {"type": "boolean"}, "font_size": {"type": "integer"}, "number_format": {"type": "string", "description": "currency, percent, comma, or custom Excel format"}, "align": {"type": "string", "description": "left, center, or right"}}, "required": ["range_ref"]},
    },
    {
        "name": "set_header_style", "description": "Style a header row with professional formatting: bold, background color, white text, font size.",
        "input_schema": {"type": "object", "properties": {"range_ref": {"type": "string", "description": "Header range like 'A1:E1'"}, "font_size": {"type": "integer", "description": "Font size (default: 11)"}}, "required": ["range_ref"]},
    },
    {
        "name": "apply_dashboard_theme", "description": "Apply a consistent professional theme to the current sheet: headers, alternating row colors, borders, auto-fit columns.",
        "input_schema": {"type": "object", "properties": {"theme": {"type": "string", "description": "Theme name: professional, modern, colorful, minimal"}}, "required": []},
    },
    {
        "name": "scroll", "description": "Scrolls the current screen. Positive clicks scroll up and negative clicks scroll down.",
        "input_schema": {"type": "object", "properties": {"clicks": {"type": "integer"}}, "required": ["clicks"]},
    },
]


def _available_vision_tools():
    """Include parse_screen only when an OmniParser backend is reachable.

    Either an external HTTP service (OMNIPARSER_URL) or local in-process
    inference (OMNIPARSER_LOCAL_MODE) satisfies this requirement.
    """
    if config.OMNIPARSER_URL or config.OMNIPARSER_LOCAL_MODE:
        return VISION_TOOLS_CLAUDE
    return [tool for tool in VISION_TOOLS_CLAUDE if tool["name"] != "parse_screen"]


def build_claude_tools():
    if config.VISUAL_ONLY_MODE:
        return _available_vision_tools()
    tools = claude_tools()
    if config.ENABLE_CODEGEN_LAYER:
        tools.append(CODEGEN_TOOL_CLAUDE)
    if config.ENABLE_VISUAL_FALLBACK:
        tools += _available_vision_tools()
    return tools


_GEMINI_UNSUPPORTED_SCHEMA_KEYS = {"default", "additionalProperties", "$schema"}


def _strip_unsupported_schema_keys(schema):
    """Gemini's function-schema parser is stricter than plain JSON-schema
    (which is all Claude requires). It rejects
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


def build_gemini_tools(allowed_function_names=None):
    """Return Gemini declarations, optionally narrowed to a small tool set.

    Gemini compiles function schemas into a constrained decoder when function
    calling is forced. Sending all 69 Excel schemas in that mode exceeds its
    state limit, even though the same catalogue is acceptable in AUTO mode.
    """
    allowed = set(allowed_function_names or ())

    def include(name):
        return not allowed or name in allowed

    vision_tools = _available_vision_tools()
    if config.VISUAL_ONLY_MODE:
        return [{"function_declarations": [
            {"name": t["name"], "description": t["description"], "parameters": _strip_unsupported_schema_keys(t["input_schema"])}
            for t in vision_tools if include(t["name"])
        ]}]
    merged = [
        declaration for declaration in gemini_tools()[0]["function_declarations"]
        if include(declaration["name"])
    ]
    merged = [
        {**decl, "parameters": _strip_unsupported_schema_keys(decl["parameters"])}
        for decl in merged
    ]
    if config.ENABLE_CODEGEN_LAYER and include(CODEGEN_TOOL_CLAUDE["name"]):
        merged.append({
            "name": CODEGEN_TOOL_CLAUDE["name"],
            "description": CODEGEN_TOOL_CLAUDE["description"],
            "parameters": CODEGEN_TOOL_CLAUDE["input_schema"],
        })
    if config.ENABLE_VISUAL_FALLBACK:
        for t in vision_tools:
            if include(t["name"]):
                merged.append({"name": t["name"], "description": t["description"], "parameters": t["input_schema"]})
    return [{"function_declarations": merged}]


_GEMINI_READ_ONLY_TOOL_NAMES = {
    "get_excel_version", "inspect_workbook", "read_range", "screenshot_active_window",
    "take_screenshot", "parse_screen",
}

# This is deliberately small enough to work with Gemini's forced-function
# decoder. It covers the first substantive step of the normal Excel workflow;
# after that first verified edit, the model receives the complete catalogue in
# AUTO mode for specialist operations.
_GEMINI_INITIAL_MUTATION_TOOLS = {
    "create_sheet", "write_cell", "write_table", "insert_formula",
    "apply_formatting", "conditional_formatting", "freeze_panes",
    "auto_fit_columns", "sort_range", "create_pivot_table", "create_chart",
}


def _is_new_dashboard_build(task) -> bool:
    """Recognise a new dashboard request that needs its first sheet created."""
    text = " ".join(
        str(getattr(task, "instruction", "")).lower().split()
    )
    existing_workbook_markers = (
        "existing workbook", "active workbook", "current workbook", "my workbook",
        "use the data in", "use my data", "use existing data",
    )
    new_work_markers = (
        "dashboard", "new workbook", "brand-new", "dummy data", "sample data",
        "demo workbook", "generate data",
    )
    return (
        not any(marker in text for marker in existing_workbook_markers)
        and any(marker in text for marker in new_work_markers)
    )


def _successful_actions(action_steps, tool_name: str):
    return [
        step for step in action_steps
        if step.get("tool_name") == tool_name
        and step.get("status") == "success"
        and isinstance(step.get("result"), dict)
        and step["result"].get("verified") is True
    ]


def _gemini_tool_config(task):
    """Require a real tool call at the points where prose is not an answer.

    Gemini defaults to ``AUTO`` tool selection.  That is suitable while a
    task is waiting for the user's approval, but it allowed an execution task
    to answer with a detailed fictional completion report without ever
    touching Excel.  Force one tool call to start approved work, then force
    the final inspection requested by the core loop.  Calls between those two
    points remain automatic so Gemini can end the task normally after it has
    received the final inspection result.
    """
    if task.awaiting_approval:
        return None

    # A real skill ran and could not verify its workbook change. Core records
    # that one recovery opportunity; force the next Gemini turn to create the
    # corresponding codegen call instead of allowing another generic skill
    # retry or a fictional text completion.
    if getattr(task, "pending_codegen_fallback", None):
        if config.OMNIPARSER_ONLY_MODE:
            # In visual-only mode, force a visual action instead of codegen
            return {
                "function_calling_config": {
                    "mode": "ANY",
                    "allowed_function_names": ["go_to_range", "type_text", "press_key", "hotkey", "paste_table"],
                }
            }
        return {
            "function_calling_config": {
                "mode": "ANY",
                "allowed_function_names": ["run_excel_code"],
            }
        }

    action_steps = [
        step for step in task.structured_steps if step.get("type") == "action"
    ]

    if config.VISUAL_ONLY_MODE:
        # Visual-only mode: force visual actions, not API skills
        available_names = [t["name"] for t in _available_vision_tools()]
        
        # Count successful actions
        successful_actions = [
            step for step in task.structured_steps
            if step.get("type") == "action"
            and step.get("status") == "success"
            and step.get("result", {}).get("verified") is True
        ]
        
        # Force tool calls until we have enough actions
        # For a typical task, we need at least 3-5 actions
        if len(successful_actions) < 3:
            # Still need more actions - force tool calls
            allowed_names = [
                "go_to_range", "type_text", "press_key", "hotkey",
                "execute_excel_shortcut", "paste_table", "fill_formula_down",
                "find_and_click", "click_ribbon_tab", "parse_screen",
                "batch_excel_operations", "format_bold", "format_currency",
                "autofit_columns"
            ]
            return {
                "function_calling_config": {
                    "mode": "ANY",
                    "allowed_function_names": [n for n in allowed_names if n in available_names],
                }
            }
        
        # Enough actions - let model finish
        return None

    if _is_new_dashboard_build(task) and not task.final_verification_requested:
        created_sheets = _successful_actions(action_steps, "create_sheet")
        written_tables = _successful_actions(action_steps, "write_table")
        if not created_sheets:
            # Do not let Gemini write to an invented sheet name and create it
            # later in the same function-call batch. Excel must have the
            # destination sheet before a table can be written.
            return {
                "function_calling_config": {
                    "mode": "ANY",
                    "allowed_function_names": ["create_sheet"],
                }
            }
        if not written_tables:
            # A model cannot reliably fit hundreds of generated data rows in
            # one function-call payload. Let it use the verified codegen path
            # to populate a large demo dataset, then it will call write_table
            # with rows=[] to turn that existing data into an Excel Table.
            data_creation_tools = {"write_table"}
            if config.ENABLE_CODEGEN_LAYER:
                data_creation_tools.add("run_excel_code")
            return {
                "function_calling_config": {
                    "mode": "ANY",
                    "allowed_function_names": sorted(data_creation_tools),
                }
            }

    if not action_steps:
        # Inspection is a safe, universally valid first step. Forcing a
        # single tiny schema avoids Gemini's state-limit error and gives the
        # next turn the live workbook facts needed for a write action.
        return {
            "function_calling_config": {
                "mode": "ANY",
                "allowed_function_names": ["inspect_workbook"],
            }
        }

    if task.final_verification_requested:
        last_workbook_change = max(
            (
                index for index, step in enumerate(action_steps)
                if step.get("tool_name") not in _GEMINI_READ_ONLY_TOOL_NAMES
            ),
            default=-1,
        )
        final_inspection_succeeded = any(
            index > last_workbook_change
            and step.get("tool_name") == "inspect_workbook"
            and step.get("status") == "success"
            and isinstance(step.get("result"), dict)
            and step["result"].get("verified") is True
            for index, step in enumerate(action_steps)
        )
        if not final_inspection_succeeded:
            return {
                "function_calling_config": {
                    "mode": "ANY",
                    "allowed_function_names": ["inspect_workbook"],
                }
            }

    meaningful_actions = [
        step for step in action_steps
        if step.get("tool_name") not in _GEMINI_READ_ONLY_TOOL_NAMES
        and step.get("status") == "success"
        and isinstance(step.get("result"), dict)
        and step["result"].get("verified") is True
    ]
    if not meaningful_actions:
        # The first inspection succeeded, but Gemini has not yet changed the
        # workbook. Require a real, task-relevant Excel operation instead of
        # accepting another textual completion claim.
        names = sorted(
            _GEMINI_INITIAL_MUTATION_TOOLS
            | ({"run_excel_code"} if config.ENABLE_CODEGEN_LAYER else set())
        )
        return {
            "function_calling_config": {
                "mode": "ANY",
                "allowed_function_names": names,
            }
        }

    return None


def call_claude(task, system_prompt: str):
    from anthropic import Anthropic

    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    request = dict(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system_prompt,
        tools=([] if task.awaiting_approval and getattr(task, "defer_excel_until_approval", False)
               else build_claude_tools()),
        messages=task.messages,
    )
    if getattr(task, "pending_codegen_fallback", None):
        request["tool_choice"] = {"type": "tool", "name": "run_excel_code"}
    response = client.messages.create(**request)
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


def tool_input(tool_call) -> dict:
    """Return a provider-neutral mapping of the tool arguments."""
    if config.AI_PROVIDER == "claude":
        return dict(tool_call.input)
    elif config.AI_PROVIDER == "openrouter":
        return openrouter_tool_input(tool_call)
    return gemini_tool_input(tool_call)


def submit_tool_result(task, tool_call, result):
    """Append a tool result in the conversation format expected by the active provider."""
    if config.AI_PROVIDER == "claude":
        submit_claude_tool_result(task, tool_call, result)
    elif config.AI_PROVIDER == "openrouter":
        tool_call_id = tool_call.get("id", "") if isinstance(tool_call, dict) else getattr(tool_call, "id", "")
        submit_openrouter_tool_result(task, tool_call_id, result)
    else:
        submit_gemini_tool_result(task, tool_call, result)


def _clean_gemini_value(value):
    if hasattr(value, "items"):
        return {k: _clean_gemini_value(v) for k, v in value.items()}
    if hasattr(value, "__iter__") and not isinstance(value, str):
        return [_clean_gemini_value(v) for v in value]
    return value


_GEMINI_FUNCTION_CALLS_KEY = "_gemini_function_calls"
_GEMINI_FUNCTION_RESPONSES_KEY = "_gemini_function_responses"
_GEMINI_TEXT_KEY = "_gemini_text"
_GEMINI_MODEL_PARTS_KEY = "_gemini_model_parts"


def _json_safe_gemini_value(value):
    """Return a value that can be retained in the JSON task transcript.

    ``FunctionCall.args`` is a protobuf map rather than a normal dictionary.
    Task messages are persisted to the database as JSON, so convert it at the
    boundary and recreate Gemini's native parts only when making the next API
    call.
    """
    return json.loads(json.dumps(_clean_gemini_value(value), default=str))


def _encode_thought_signature(signature):
    """Store Gemini's opaque reasoning signature without changing its bytes."""
    if isinstance(signature, bytes):
        return base64.b64encode(signature).decode("ascii")
    if isinstance(signature, bytearray):
        return base64.b64encode(bytes(signature)).decode("ascii")
    return None


def _function_call_record(function_call):
    """Make the provider's FunctionCall JSON-safe, including its response id."""
    try:
        arguments = _json_safe_gemini_value(function_call.args)
    except Exception:
        arguments = {}
    record = {"name": function_call.name, "args": arguments}
    call_id = getattr(function_call, "id", None)
    if isinstance(call_id, str) and call_id:
        record["id"] = call_id
    return record


def _function_call_runtime_key(function_call):
    """Identify one in-memory call while results are buffered for one turn."""
    call_id = getattr(function_call, "id", None)
    return f"id:{call_id}" if isinstance(call_id, str) and call_id else f"object:{id(function_call)}"


def _model_part_record(part):
    """Persist every returned Gemini Part exactly enough to replay it.

    Gemini 3 can attach a thought signature to a text/thought Part *before*
    a function call. Keeping only FunctionCall objects therefore loses the
    signature and makes the next request invalid. A stateless client must
    replay every model Part, in order, with its original signature.
    """
    record = {}
    text = getattr(part, "text", None)
    if isinstance(text, str):
        record["text"] = text

    function_call = getattr(part, "function_call", None)
    if function_call and getattr(function_call, "name", None):
        record["function_call"] = _function_call_record(function_call)

    thought = getattr(part, "thought", None)
    if isinstance(thought, bool):
        record["thought"] = thought

    signature = _encode_thought_signature(getattr(part, "thought_signature", None))
    if signature is not None:
        record["thought_signature"] = signature

    return record


def _part_from_record(record, gemini_types):
    """Rebuild one Gemini Part without merging it with adjacent parts."""
    if not isinstance(record, dict):
        return None

    kwargs = {}
    if isinstance(record.get("text"), str):
        kwargs["text"] = record["text"]
    if isinstance(record.get("thought"), bool):
        kwargs["thought"] = record["thought"]

    function_call = record.get("function_call")
    if isinstance(function_call, dict) and isinstance(function_call.get("name"), str):
        call_kwargs = {
            "name": function_call["name"],
            "args": function_call.get("args") if isinstance(function_call.get("args"), dict) else {},
        }
        if isinstance(function_call.get("id"), str) and function_call["id"]:
            call_kwargs["id"] = function_call["id"]
        kwargs["function_call"] = gemini_types.FunctionCall(**call_kwargs)

    signature = record.get("thought_signature")
    if isinstance(signature, str):
        try:
            kwargs["thought_signature"] = base64.b64decode(signature, validate=True)
        except Exception:
            # A malformed persisted signature cannot be safely invented. Keep
            # the content usable and let Gemini report the exact history issue.
            pass

    if not kwargs:
        return None
    return gemini_types.Part(**kwargs)


def _gemini_parts_from_content(content, gemini_types):
    """Build native Gemini parts from a JSON-safe task-message payload."""
    if isinstance(content, str):
        return [gemini_types.Part(text=content)]
    if not isinstance(content, dict):
        return []

    # New-format model history preserves every response part and, crucially,
    # the thought signature on whichever part originally carried it.
    model_part_records = content.get(_GEMINI_MODEL_PARTS_KEY)
    if isinstance(model_part_records, list):
        return [
            part for record in model_part_records
            if (part := _part_from_record(record, gemini_types)) is not None
        ]

    # Compatibility for tasks persisted before full model-part replay was
    # added. New calls use the branch above.
    parts = []
    for call in content.get(_GEMINI_FUNCTION_CALLS_KEY, []):
        if not isinstance(call, dict) or not isinstance(call.get("name"), str):
            continue
        args = call.get("args")
        signature = call.get("thought_signature")
        call_kwargs = {
            "name": call["name"],
            "args": args if isinstance(args, dict) else {},
        }
        if isinstance(call.get("id"), str) and call["id"]:
            call_kwargs["id"] = call["id"]
        try:
            thought_signature = base64.b64decode(signature) if isinstance(signature, str) else None
        except Exception:
            thought_signature = None
        parts.append(gemini_types.Part(
            function_call=gemini_types.FunctionCall(**call_kwargs),
            thought_signature=thought_signature,
        ))
    for tool_result in content.get(_GEMINI_FUNCTION_RESPONSES_KEY, []):
        if not isinstance(tool_result, dict) or not isinstance(tool_result.get("name"), str):
            continue
        response = tool_result.get("response")
        response_kwargs = {
            "name": tool_result["name"],
            "response": response if isinstance(response, dict) else {"result": response},
        }
        if isinstance(tool_result.get("id"), str) and tool_result["id"]:
            response_kwargs["id"] = tool_result["id"]
        parts.append(gemini_types.Part(
            function_response=gemini_types.FunctionResponse(**response_kwargs),
        ))
    text = content.get(_GEMINI_TEXT_KEY)
    if isinstance(text, str) and text:
        parts.append(gemini_types.Part(text=text))
    elif isinstance(text, list):
        parts.extend(gemini_types.Part(text=part) for part in text if isinstance(part, str) and part)
    return parts


def _convert_history_for_gemini(messages):
    from google.genai import types

    history = []
    for m in messages:
        parts = _gemini_parts_from_content(m.get("content"), types)
        if parts:
            role = "user" if m.get("role") == "user" else "model"
            history.append(types.Content(role=role, parts=parts))
    return history


def call_gemini(task, system_prompt: str):
    import time
    from google import genai
    from google.genai import errors, types

    client = genai.Client(
        api_key=config.GEMINI_API_KEY,
        http_options=types.HttpOptions(timeout=config.GEMINI_TIMEOUT_SECONDS * 1000),
    )
    last_user_msg = task.messages[-1]["content"]
    tool_config = _gemini_tool_config(task)
    allowed_function_names = None
    if tool_config is not None:
        allowed_function_names = tool_config["function_calling_config"].get(
            "allowed_function_names"
        )
    tool_declarations = (
        []
        if task.awaiting_approval and getattr(task, "defer_excel_until_approval", False)
        else build_gemini_tools(allowed_function_names)
    )
    tools = [types.Tool(**declaration) for declaration in tool_declarations]
    generation_config = types.GenerateContentConfig(
        tools=tools or None,
        tool_config=(
            types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    **tool_config["function_calling_config"]
                )
            )
            if tool_config is not None else None
        ),
        system_instruction=system_prompt,
    )

    # Desktop work must not appear frozen while an external service waits for
    # quota. Try each configured fallback once, then return the real error.
    RETRIES_PER_MODEL = 1
    last_error = None

    for model_offset in range(len(config.GEMINI_MODEL_CHAIN)):
        model_index = (task.gemini_model_index + model_offset) % len(config.GEMINI_MODEL_CHAIN)
        model_name = config.GEMINI_MODEL_CHAIN[model_index]
        history = _convert_history_for_gemini(task.messages[:-1])
        prompt_parts = _gemini_parts_from_content(last_user_msg, types)
        if not prompt_parts:
            raise ValueError("Gemini received an empty conversation message.")
        contents = history + [types.Content(role="user", parts=prompt_parts)]

        for attempt in range(RETRIES_PER_MODEL):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=generation_config,
                )
                task.gemini_model_index = model_index
                return _parse_gemini_response(task, response)
            except errors.ClientError as e:
                if getattr(e, "code", None) != 429:
                    raise
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
            except errors.ServerError as e:
                last_error = e
                if attempt < RETRIES_PER_MODEL - 1:
                    task.log_step(f"⚠️ '{model_name}' produced a malformed function call - retrying once more.")
                else:
                    task.log_step(f"🔀 '{model_name}' keeps producing malformed function calls - "
                                   f"switching to the next model in the fallback chain.")

    raise last_error


def _parse_gemini_response(task, response):
    candidates = getattr(response, "candidates", None) or []
    if not candidates or not getattr(candidates[0], "content", None):
        task.messages.append({"role": "assistant", "content": "Gemini returned no usable response."})
        return [], ["Gemini returned no usable response."], "end_turn"

    parts = candidates[0].content.parts or []
    function_calls, function_call_parts, text_parts = [], [], []
    for part in parts:
        fc = getattr(part, "function_call", None)
        if fc and fc.name:
            function_calls.append(fc)
            function_call_parts.append(part)
        else:
            t = getattr(part, "text", None)
            if t:
                text_parts.append(t)

    if function_calls:
        # Keep the full response-part sequence, not just function calls.
        # Gemini 3 validates the original position of every thought signature.
        # In a parallel function-call response only the first call may carry a
        # signature; flattening or reordering those Parts produces a 400 on
        # the next model turn.
        model_part_records = [_model_part_record(part) for part in parts]
        task.messages.append({
            "role": "assistant",
            "content": {
                _GEMINI_MODEL_PARTS_KEY: model_part_records,
            },
        })
        # Function calls in one model response are parallel from Gemini's
        # perspective. Buffer every result and submit one user Content with
        # all FunctionResponse Parts after core has executed them all.
        task.gemini_expected_function_responses = len(function_calls)
        task.gemini_function_response_order = [
            _function_call_runtime_key(function_call) for function_call in function_calls
        ]
        task.gemini_function_response_batch = []
        return function_calls, text_parts, "tool_use"

    combined_text = " ".join(text_parts)
    task.messages.append({"role": "assistant", "content": combined_text})
    return [], [combined_text], "end_turn"


def submit_gemini_tool_result(task, tool_call, result):
    # Function responses must follow the signed FunctionCall directly. Do not
    # add a normal text part here: Gemini treats that as a new user request
    # and rejects the preceding signed call as an invalid tool turn. For
    # parallel calls, Gemini requires all responses in ONE Content; submitting
    # each response separately makes the unsigned second call look like a new
    # (and invalid) tool turn.
    # Handle both object (Gemini) and dict (OpenRouter) formats
    tool_name = tool_call.name if hasattr(tool_call, 'name') else tool_call.get('name', '') if isinstance(tool_call, dict) else ''
    response_record = {
        "name": tool_name,
        "response": _json_safe_gemini_value(result),
    }
    call_id = getattr(tool_call, "id", None) if not isinstance(tool_call, dict) else tool_call.get("id", "")
    if isinstance(call_id, str) and call_id:
        response_record["id"] = call_id

    expected = getattr(task, "gemini_expected_function_responses", 0)
    batch = getattr(task, "gemini_function_response_batch", None)
    if expected and isinstance(batch, list):
        batch.append((_function_call_runtime_key(tool_call), response_record))
        if len(batch) < expected:
            return
        by_call = {key: response for key, response in batch}
        order = getattr(task, "gemini_function_response_order", [])
        responses = [by_call[key] for key in order if key in by_call]
        task.gemini_expected_function_responses = 0
        task.gemini_function_response_order = []
        task.gemini_function_response_batch = []
    else:
        # Compatibility for direct unit tests and any task created before the
        # parser initialised a response batch.
        responses = [response_record]

    task.messages.append({
        "role": "user",
        "content": {
            _GEMINI_FUNCTION_RESPONSES_KEY: responses,
        },
    })


def gemini_tool_input(tool_call) -> dict:
    return {k: _clean_gemini_value(v) for k, v in tool_call.args.items()}


# =============================================================================
# OpenRouter Support
# =============================================================================

def call_openrouter(task, system_prompt: str):
    """Call OpenRouter API with free models.
    
    Supports OpenAI-compatible API format.
    Free models: openrouter/free, gpt-oss-120b:free, google/gemma-3-27b-it:free
    """
    import time
    import requests
    
    api_key = config.OPENROUTER_API_KEY
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is not configured")
    
    model_chain = config.OPENROUTER_MODEL_CHAIN  # Already a list from config.py
    timeout = config.OPENROUTER_TIMEOUT_SECONDS
    
    # Debug output
    import sys
    print(f"[OpenRouter] API Key: {api_key[:10]}...", file=sys.stderr)
    print(f"[OpenRouter] Model chain: {model_chain}", file=sys.stderr)
    print(f"[OpenRouter] Timeout: {timeout}", file=sys.stderr)
    
    # Build messages in OpenAI format
    messages = [{"role": "system", "content": system_prompt}]
    
    i = 0
    while i < len(task.messages):
        msg = task.messages[i]
        role = msg.get("role", "user")
        content = msg.get("content", "")
        
        if role == "assistant" and isinstance(content, dict) and "tool_calls" in content:
            # Assistant message with tool calls - format for OpenAI
            tool_calls_list = []
            for tc in content.get("tool_calls", []):
                tool_calls_list.append({
                    "id": tc.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": tc.get("name", ""),
                        "arguments": json.dumps(tc.get("arguments", {})) if not isinstance(tc.get("arguments", ""), str) else tc.get("arguments", "")
                    }
                })
            messages.append({
                "role": "assistant",
                "tool_calls": tool_calls_list,
                "content": None
            })
        elif role == "tool":
            # Tool result - skip if no preceding assistant tool_calls
            messages.append({
                "role": "tool",
                "tool_call_id": msg.get("tool_call_id", ""),
                "content": json.dumps(content) if not isinstance(content, str) else content
            })
        elif isinstance(content, str):
            messages.append({"role": role, "content": content})
        elif isinstance(content, dict):
            text_parts = []
            if "text" in content:
                text_parts.append(content["text"])
            if text_parts:
                messages.append({"role": role, "content": " ".join(text_parts)})
        i += 1
    
    # Build tools list for OpenAI-compatible format
    tools = []
    vision_tools = _available_vision_tools()
    for tool in vision_tools:
        tools.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"]
            }
        })
    
    # Try each model in the chain
    models_to_try = model_chain  # Already a list from config.py
    
    last_error = None
    for model in models_to_try:
        try:
            # Rate limiting delay for free models (3 seconds between calls)
            time.sleep(3)
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://xelora.ai",
                "X-Title": "Xelora Excel Agent"
            }
            
            payload = {
                "model": model,
                "messages": messages,
                "tools": tools if tools else None,
                "tool_choice": "auto",
                "max_tokens": 4096,
                "temperature": 0.7
            }
            
            try:
                response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=timeout
                )
            except requests.exceptions.Timeout:
                print(f"[OpenRouter] Timeout with {model} after {timeout}s", file=sys.stderr)
                task.log_step(f"OpenRouter timeout with {model}")
                continue
            except requests.exceptions.ConnectionError as e:
                print(f"[OpenRouter] Connection error with {model}: {e}", file=sys.stderr)
                task.log_step(f"OpenRouter connection error with {model}")
                continue
            
            if response.status_code == 429:
                # Rate limited, try next model
                task.log_rate_limit(model)
                continue
            
            response.raise_for_status()
            result = response.json()
            
            # Debug output
            print(f"[OpenRouter] Response status: {response.status_code}", file=sys.stderr)
            print(f"[OpenRouter] Result keys: {list(result.keys())}", file=sys.stderr)
            
            # Parse OpenAI-compatible response
            choice = result.get("choices", [{}])[0]
            message = choice.get("message", {})
            
            # Debug output
            print(f"[OpenRouter] Message keys: {list(message.keys())}", file=sys.stderr)
            print(f"[OpenRouter] Has tool_calls: {'tool_calls' in message}", file=sys.stderr)
            
            # Extract tool calls
            tool_calls = []
            if "tool_calls" in message:
                for tc in message["tool_calls"]:
                    func = tc.get("function", {})
                    tool_calls.append({
                        "name": func.get("name", ""),
                        "arguments": json.loads(func.get("arguments", "{}")),
                        "id": tc.get("id", "")
                    })
            
            # Extract text
            text = message.get("content", "")
            
            # Debug output
            print(f"[OpenRouter] Tool calls: {len(tool_calls)}", file=sys.stderr)
            print(f"[OpenRouter] Text: {text[:100] if text else '(empty)'}", file=sys.stderr)
            
            return tool_calls, [text] if text else [], "end_turn" if not tool_calls else "tool_use"
            
        except requests.exceptions.RequestException as e:
            print(f"[OpenRouter] Request error with {model}: {e}", file=sys.stderr)
            task.log_step(f"OpenRouter error with {model}: {str(e)[:100]}")
            last_error = e
            continue
        except Exception as e:
            print(f"[OpenRouter] Unexpected error with {model}: {e}", file=sys.stderr)
            task.log_step(f"OpenRouter unexpected error: {str(e)[:100]}")
            last_error = e
            continue
    
    if last_error:
        print(f"[OpenRouter] All models failed. Last error: {last_error}", file=sys.stderr)
    raise Exception("All OpenRouter models failed")


def submit_openrouter_tool_result(task, tool_call_id: str, result: dict):
    """Submit tool result back to OpenRouter (stored in message history)."""
    # OpenRouter uses OpenAI format - results are stored as messages
    task.messages.append({
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": json.dumps(result)
    })


def openrouter_tool_input(tool_call: dict) -> dict:
    """Extract tool input from OpenRouter tool call."""
    return tool_call.get("arguments", {})
