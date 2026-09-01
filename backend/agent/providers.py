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
import time

import config
from skills.registry import claude_tools, gemini_tools

CODEGEN_TOOL_CLAUDE = {
    "name": "run_excel_code",
    "description": (
        "Runs real Python (xlwings) only when no available skill or safe visible command "
        "covers the exact operation, for a large raw-data batch that cannot fit a tool payload, "
        "or for the exact goal of a skill result that explicitly requires codegen fallback. "
        "The call must explain that decision and name the result range/chart source that Excel "
        "should visibly reveal. Must use native Excel features, never a "
        "precomputed value. Allowed imports are xlwings, datetime, math, random, "
        "re, json, and statistics. Never assign .formula or .formula2 here: use the "
        "insert_formula skill (with fill_to for a formula column) so formula writes are "
        "verified safely. Assign a JSON-serializable dictionary to `result`. Only set "
        "`verified: true` after reading back the changed workbook state, and include a "
        "non-empty `verification_note` describing that evidence."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Python source code to execute."},
            "fallback_reason": {
                "type": "string",
                "description": "Why the available shortcut and skill routes cannot safely perform this exact operation."
            },
            "atomic_goal": {
                "type": "string",
                "description": "One bounded worksheet-level goal, not a whole-workbook build."
            },
            "alternatives_considered": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Named shortcuts/skills considered, with why each is unsuitable for this one atomic goal."
            },
            "reveal_reference": {
                "type": "string",
                "description": "A valid range or defined name to visibly select after the change, e.g. 'Sales Summary'!A1."
            },
        },
        "required": ["code", "fallback_reason", "atomic_goal", "alternatives_considered", "reveal_reference"],
    },
}

VISION_TOOLS_CLAUDE = [
    {
        "name": "get_execution_capabilities",
        "description": "Return the live catalogue of registered Excel skills/API operations, named shortcuts, UI options, selection order, and safety policy. Use when choosing an unfamiliar operation or an alternative after a verified failure; it does not change the workbook.",
        "input_schema": {"type": "object", "properties": {}},
    },
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
        "description": "Send an Alt-key ribbon sequence to reach commands without a direct Ctrl shortcut. Example: press_alt(['h','o','i']) opens Format Cells; press_alt(['n','c']) inserts a chart. Use when execute_excel_shortcut lacks the command. This is more reliable than parse_screen.",
        "input_schema": {"type": "object", "properties": {"keys": {"type": "array", "items": {"type": "string"}, "description": "Keys to send after Alt, e.g. ['h','o','i']"}}, "required": ["keys"]},
    },
    {
        "name": "press_shortcut",
        "description": "Perform a common Excel operation ENTIRELY via Alt-key ribbon sequences (no mouse, no vision). Use this to complete tasks like format_cells, insert_chart, insert_table, borders_all, fill_color, font_color, bold, merge_center, autofit_columns, wrap_text, number_format, sum_below. More reliable than clicking for these operations.",
        "input_schema": {"type": "object", "properties": {"shortcut_name": {"type": "string", "description": "One of: format_cells, insert_chart, insert_pivot, insert_table, borders_all, borders_thick, fill_color, font_color, bold, merge_center, autofit_columns, wrap_text, number_format, sum_below"}}, "required": ["shortcut_name"]},
    },
    {
        "name": "click_button",
        "description": "Click a button by name. Uses UIA first (fast, no screenshot), then falls back to OmniParser.",
        "input_schema": {"type": "object", "properties": {"button_name": {"type": "string", "description": "Name of the button"}}, "required": ["button_name"]},
    },
    {
        "name": "execute_excel_shortcut",
        "description": "Execute an Excel keyboard shortcut DIRECTLY (bypasses vision). Accepts a named operation or any standard validated chord such as ctrl+shift+l, ctrl+alt+v, f4, or alt+f1. The named insert_table operation is transactional: it validates the native Create Table range and clicks its visible OK button before returning. Use press_alt for sequential Ribbon KeyTips. This is the fastest path for standard operations.",
        "input_schema": {"type": "object", "properties": {"shortcut_name": {"type": "string", "description": "Named operation (for example save, insert_table, default_chart, format_cells) or a standard chord expression such as ctrl+shift+l, ctrl+alt+v, f4, or alt+f1."}}, "required": ["shortcut_name"]},
    },
    {
        "name": "save_workbook",
        "description": "Save the current Excel workbook through its native UI. A new unnamed workbook is saved automatically to the local Documents folder with a timestamped Xelora_Workbook filename; Xelora chooses Browse, never OneDrive, enters the filename, clicks visible Save, and verifies the title. Provide file_name only to choose a custom filename (not a folder path).",
        "input_schema": {"type": "object", "properties": {"file_name": {"type": "string", "description": "Optional filename only, including .xlsx when known. Do not provide a folder path."}}},
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
        "name": "hover_and_read_tooltip",
        "description": "Hover, without clicking, over the center of a recently parsed Ribbon element and parse Excel's tooltip. Use for an unlabelled icon only after shortcuts and UIA were unavailable.",
        "input_schema": {"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}, "wait_seconds": {"type": "number"}}, "required": ["x", "y"]},
    },
    {
        "name": "inspect_popup",
        "description": "Read a visible Excel popup title, message, buttons, and signature without clicking it. Always use before choosing an action in an unfamiliar popup.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "click_popup_button",
        "description": "Click one exact button in an already inspected Excel popup. Security, protection, overwrite, and link-update dialogs can only be cancelled; do not use Enter or raw coordinates for popup decisions.",
        "input_schema": {"type": "object", "properties": {"button_label": {"type": "string"}}, "required": ["button_label"]},
    },
    {
        "name": "click_popup_control",
        "description": "Configure an exact non-final control inside the sole inspected Excel popup, such as a radio choice, tab, checkbox, or Format button. It uses UI Automation first and one cropped OmniParser fallback only if needed. Do not use for OK, Save, Yes, Cancel, or Close; use click_popup_button for those final decisions.",
        "input_schema": {"type": "object", "properties": {"control_label": {"type": "string"}}, "required": ["control_label"]},
    },
    {
        "name": "set_popup_text",
        "description": "Set one unambiguous text field in the sole inspected Excel popup, then read it back. Use field_hint only when the dialog exposes more than one field; never use normal type_text while a popup is open.",
        "input_schema": {"type": "object", "properties": {"value": {"type": "string"}, "field_hint": {"type": "string"}}, "required": ["value"]},
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
        "name": "hotkey", "description": "Presses one documented modifier chord, for example ctrl+b or ctrl+shift+4. Do not use for bare keys, sequences, or Alt Ribbon KeyTips.",
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
    {
        "name": "create_sheet", "description": "Create one worksheet with the requested name. It verifies the newly created tab before attempting a safe rename; use this instead of Shift+F11 or guessed Sheet2 names.",
        "input_schema": {"type": "object", "properties": {"sheet_name": {"type": "string", "description": "Requested Excel worksheet name"}}, "required": ["sheet_name"]},
    },
    {"name": "fill_formula_down", "description": "Writes a formula to one cell and fills it down a single column through an end cell.", "input_schema": {"type": "object", "properties": {"start_cell": {"type": "string"}, "end_cell": {"type": "string"}, "formula": {"type": "string"}}, "required": ["start_cell", "end_cell", "formula"]}},
    {"name": "format_currency", "description": "Applies Excel's currency format to a valid selected range.", "input_schema": {"type": "object", "properties": {"reference": {"type": "string"}}, "required": ["reference"]}},
    {"name": "format_bold", "description": "Makes a valid Excel range bold.", "input_schema": {"type": "object", "properties": {"reference": {"type": "string"}}, "required": ["reference"]}},
    {"name": "autofit_columns", "description": "AutoFits the columns containing a valid Excel range.", "input_schema": {"type": "object", "properties": {"reference": {"type": "string"}}, "required": ["reference"]}},
    {"name": "create_clustered_column_chart", "description": "Creates a clustered column chart from a prepared two-column source range with headers.", "input_schema": {"type": "object", "properties": {"reference": {"type": "string"}}, "required": ["reference"]}},
    {
        "name": "rename_sheet", "description": "Safely rename an existing worksheet tab through Excel's verified rename editor. It never sends text unless the editor is confirmed.",
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
        "name": "set_fill_color", "description": "Apply a CELL/ROW FILL (background) color using keyboard + vision + autoGUI. color is a hex like '4472C4' or a name (blue, green, red, yellow, orange, purple, lightblue, darkblue, lightgreen, darkred, white, black, gray, lightgray, darkgray). Self-contained: never mutates data.",
        "input_schema": {"type": "object", "properties": {"range_ref": {"type": "string", "description": "Cell or range like 'A1:F1'"}, "color": {"type": "string", "description": "Hex or named color"}}, "required": ["range_ref", "color"]},
    },
    {
        "name": "set_font_color", "description": "Apply a FONT color using keyboard + vision + autoGUI. color is a hex like 'FFFFFF' or a name (see set_fill_color). Self-contained: never mutates data.",
        "input_schema": {"type": "object", "properties": {"range_ref": {"type": "string", "description": "Cell or range like 'A1:F1'"}, "color": {"type": "string", "description": "Hex or named color"}}, "required": ["range_ref", "color"]},
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
    parser_dependent = {"parse_screen", "hover_and_read_tooltip", "search_cached_elements"}
    return [tool for tool in VISION_TOOLS_CLAUDE if tool["name"] not in parser_dependent]


def _assert_unique_tool_names(tool_declarations, provider_name: str) -> None:
    """Fail before contacting a model when a provider tool list is invalid.

    Gemini rejects a whole request if even one function name appears twice.
    Do not rely on a remote 400 response to discover a local catalogue bug.
    """
    names = [str(tool.get("name", "")) for tool in tool_declarations]
    duplicates = sorted({name for name in names if name and names.count(name) > 1})
    if duplicates:
        raise RuntimeError(
            f"{provider_name} tool catalogue contains duplicate function declaration(s): "
            + ", ".join(duplicates)
        )


def _append_non_overlapping_tools(destination: list, candidates: list) -> None:
    """Append only controls not already supplied by a higher-priority layer.

    Skills/API are the canonical hybrid route. Some visual controls use the
    same public name (for example create_sheet), but exposing both to an AI
    provider is invalid and ambiguous. The visual implementation remains
    available in visual-only mode, where no skill declaration is present.
    """
    existing_names = {str(tool.get("name", "")) for tool in destination}
    destination.extend(
        tool for tool in candidates
        if str(tool.get("name", "")) not in existing_names
    )


def build_claude_tools():
    if config.VISUAL_ONLY_MODE:
        tools = _available_vision_tools()
        _assert_unique_tool_names(tools, "Claude visual")
        return tools
    tools = claude_tools()
    if config.ENABLE_CODEGEN_LAYER:
        tools.append(CODEGEN_TOOL_CLAUDE)
    if config.ENABLE_VISUAL_FALLBACK:
        _append_non_overlapping_tools(tools, _available_vision_tools())
    _assert_unique_tool_names(tools, "Claude")
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
        declarations = [
            {"name": t["name"], "description": t["description"], "parameters": _strip_unsupported_schema_keys(t["input_schema"])}
            for t in vision_tools if include(t["name"])
        ]
        _assert_unique_tool_names(declarations, "Gemini visual")
        return [{"function_declarations": declarations}]
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
        _append_non_overlapping_tools(
            merged,
            [
                {"name": t["name"], "description": t["description"], "parameters": t["input_schema"]}
                for t in vision_tools
                if include(t["name"])
            ],
        )
    _assert_unique_tool_names(merged, "Gemini")
    return [{"function_declarations": merged}]


def validate_provider_tool_catalogues() -> None:
    """Run at startup so invalid local tool composition never reaches users."""
    build_claude_tools()
    build_gemini_tools()


_GEMINI_READ_ONLY_TOOL_NAMES = {
    "get_excel_version", "inspect_workbook", "read_range", "screenshot_active_window",
    "take_screenshot", "parse_screen", "get_execution_capabilities",
}

# This is deliberately small enough to work with Gemini's forced-function
# decoder. It covers the first substantive step of the normal Excel workflow;
# after that first verified edit, the model receives the complete catalogue in
# AUTO mode for specialist operations.
_GEMINI_INITIAL_MUTATION_TOOLS = {
    "create_sheet", "create_sheets", "write_cell", "write_table", "insert_formula",
    "apply_formatting", "conditional_formatting", "freeze_panes",
    "auto_fit_columns", "sort_range", "create_pivot_table", "create_chart",
}

# Gemini's initial forced-call decoder needs a bounded catalogue. These
# verified visual choices keep that technical limit from hard-wiring the
# first real workbook action to skills or codegen. They are added only when
# their tool declarations are actually available for this session.
_GEMINI_INITIAL_VISUAL_MUTATION_TOOLS = {
    "go_to_range", "go_to_sheet", "execute_excel_shortcut", "press_alt",
    "press_shortcut", "create_clustered_column_chart", "create_pie_chart",
}


def _recovery_inspection_tool_name(task) -> str | None:
    """Return the one safe observation required before another recovery write."""
    state = getattr(task, "recovery_state", None)
    if not isinstance(state, dict) or state.get("phase") not in {
        "inspecting_failure", "retry_pending"
    }:
        return None
    # Normal/hybrid mode can inspect the full workbook through the object
    # model. Visual-only mode must remain within its visible-control set.
    return "get_sheet_info" if config.VISUAL_ONLY_MODE else "inspect_workbook"


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

    recovery_tool = _recovery_inspection_tool_name(task)
    if recovery_tool:
        return {
            "function_calling_config": {
                "mode": "ANY",
                "allowed_function_names": [recovery_tool],
            }
        }

    action_steps = [
        step for step in task.structured_steps if step.get("type") == "action"
    ]

    if config.VISUAL_ONLY_MODE:
        # Visual-only mode: force visual actions, not API skills
        available_names = [t["name"] for t in _available_vision_tools()]
        required_sheets = list(getattr(task, "required_visual_sheet_names", []) or [])

        # Core has reached the final gate for a structured workbook build.
        # Keep Gemini on the safe completion path rather than allowing it to
        # emit a prose-only success claim or to use a partial sheet list.
        if task.final_verification_requested and required_sheets:
            visual_observations = {
                "take_screenshot", "parse_screen", "inspect_popup", "search_cached_elements",
                "get_active_sheet_name", "verify_current_sheet", "get_sheet_info", "get_cell_value",
                "verify_task_completion",
            }
            latest_change = max(
                (
                    index for index, step in enumerate(action_steps)
                    if step.get("tool_name") not in visual_observations | {"save_workbook"}
                ),
                default=-1,
            )
            completed_check = any(
                index > latest_change
                and step.get("tool_name") == "verify_task_completion"
                and step.get("status") == "success"
                and isinstance(step.get("result"), dict)
                and step["result"].get("verified") is True
                and [" ".join(str(name).split()).casefold() for name in step.get("input", {}).get("expected_sheets", [])]
                    == [" ".join(str(name).split()).casefold() for name in required_sheets]
                for index, step in enumerate(action_steps)
            )
            if not completed_check:
                return {
                    "function_calling_config": {
                        "mode": "ANY",
                        "allowed_function_names": ["verify_task_completion"],
                    }
                }

            if getattr(task, "final_save_requested", False):
                successful_save = any(
                    index > latest_change
                    and step.get("tool_name") == "save_workbook"
                    and step.get("status") == "success"
                    and isinstance(step.get("result"), dict)
                    and step["result"].get("verified") is True
                    for index, step in enumerate(action_steps)
                )
                failed_save = any(
                    step.get("tool_name") == "save_workbook"
                    and step.get("status") in {"failed", "blocked", "retried"}
                    for step in action_steps
                )
                if successful_save or failed_save:
                    return None
                return {
                    "function_calling_config": {
                        "mode": "ANY",
                        "allowed_function_names": ["save_workbook"],
                    }
                }

            return None
        
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
                "find_and_click", "click_ribbon_tab", "parse_screen", "inspect_popup",
                "click_popup_control", "set_popup_text", "click_popup_button",
                "batch_excel_operations", "format_bold", "format_currency",
                "autofit_columns", "create_sheet", "rename_sheet", "go_to_sheet",
                "get_active_sheet_name", "verify_current_sheet", "get_sheet_info",
                "verify_task_completion",
            ]
            return {
                "function_calling_config": {
                    "mode": "ANY",
                    "allowed_function_names": [n for n in allowed_names if n in available_names],
                }
            }
        
        # Enough actions - let model finish
        return None

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
        names = set(_GEMINI_INITIAL_MUTATION_TOOLS)
        if config.ENABLE_VISUAL_FALLBACK:
            names |= _GEMINI_INITIAL_VISUAL_MUTATION_TOOLS
        if config.ENABLE_CODEGEN_LAYER:
            names.add("run_excel_code")
        return {
            "function_calling_config": {
                "mode": "ANY",
                "allowed_function_names": sorted(names),
            }
        }

    return None


def call_claude(task, system_prompt: str):
    from anthropic import Anthropic

    # A provider fallback must not inherit the SDK's default multi-minute
    # retry behaviour.  Core will hand off to the next configured provider on
    # an availability failure, after preserving the workbook state safely.
    client = Anthropic(
        api_key=config.ANTHROPIC_API_KEY,
        timeout=config.CLAUDE_TIMEOUT_SECONDS,
        max_retries=0,
    )
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
    else:
        recovery_tool = _recovery_inspection_tool_name(task)
        if recovery_tool:
            request["tool_choice"] = {"type": "tool", "name": recovery_tool}
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


def active_provider_name(task) -> str:
    """Return the provider currently responsible for this task.

    A task begins on ``config.AI_PROVIDER``.  It may move once to a configured
    fallback when the primary is genuinely unavailable, but all subsequent
    tool-call parsing and tool-result messages must follow that provider's
    protocol rather than the process-wide default.
    """
    provider = str(getattr(task, "active_provider", "") or config.AI_PROVIDER).lower()
    return provider if provider in {"gemini", "claude", "openrouter"} else config.AI_PROVIDER


def _provider_is_configured(provider: str) -> bool:
    if provider == "gemini":
        return bool(config.GEMINI_API_KEY)
    if provider == "claude":
        return bool(config.ANTHROPIC_API_KEY)
    if provider == "openrouter":
        return bool(config.OPENROUTER_API_KEY)
    return False


def _is_provider_availability_failure(error: Exception) -> bool:
    """Return whether changing providers is safer than ending the task.

    Do not switch for an invalid tool schema or an invalid prompt.  Switching
    is reserved for availability events such as DNS outages, timeouts, and
    quota/rate-limit responses, where a clean continuation on another
    configured provider can continue from the real workbook state.
    """
    detail = f"{type(error).__name__}: {error}".lower()
    availability_terms = (
        "getaddrinfo", "name or service not known", "temporary failure in name resolution",
        "connection reset", "connection aborted", "connection refused", "network is unreachable",
        "timed out", "timeout", "server disconnected", "remote protocol error",
        "rate limit", "rate-limit", "too many requests", "429", "quota",
    )
    return any(term in detail for term in availability_terms)


def _provider_neutral_continuation(task, failed_provider: str, error: Exception) -> str:
    """Build a compact, safe handoff after provider-native history is unusable."""
    actions = []
    for step in list(getattr(task, "structured_steps", []) or []):
        if step.get("type") != "action":
            continue
        result = step.get("result") if isinstance(step.get("result"), dict) else {}
        actions.append({
            "tool": step.get("tool_name"),
            "status": step.get("status"),
            "verified": result.get("verified"),
            "note": str(result.get("verification_note") or result.get("error") or "")[:500],
        })
    action_summary = json.dumps(actions[-25:], default=str)
    return (
        "Continue this same Excel task after the previous AI provider became unavailable. "
        "Do not assume planned work is complete and do not repeat a verified write. "
        "First inspect the live workbook, then make only the remaining verified changes. "
        "If a write is required, use the skill library first; use code generation only when no skill covers it.\n\n"
        f"Original user request:\n{getattr(task, 'instruction', '')}\n\n"
        f"Unavailable provider: {failed_provider}. Error: {str(error)[:500]}\n"
        f"Recent tool evidence (not a substitute for inspection): {action_summary}"
    )


def activate_available_provider_fallback(task, error: Exception) -> bool:
    """Switch once to a configured provider after a real availability failure.

    Provider conversation formats are not interchangeable.  Rather than pass
    Gemini signed tool history to Claude (or the reverse), start the fallback
    with a fresh, explicit continuation message and force a safe workbook
    inspection before further writes.  Excel actions remain serial in core.
    """
    if not _is_provider_availability_failure(error):
        return False

    current = active_provider_name(task)
    attempted = set(getattr(task, "provider_failover_history", []) or []) | {current}
    fallback = next(
        (
            candidate for candidate in config.AI_PROVIDER_FALLBACK_CHAIN
            if candidate in {"gemini", "claude", "openrouter"}
            and candidate not in attempted
            and _provider_is_configured(candidate)
        ),
        None,
    )
    if not fallback:
        return False

    task.active_provider = fallback
    task.provider_failover_history = list(getattr(task, "provider_failover_history", []) or []) + [current]
    task.messages = [{
        "role": "user",
        "content": _provider_neutral_continuation(task, current, error),
    }]
    # These are Gemini-specific protocol buffers.  A clean provider handoff
    # must not carry a pending signed function-response batch forward.
    task.gemini_expected_function_responses = 0
    task.gemini_function_response_order = []
    task.gemini_function_response_batch = []
    task.log_step(
        f"AI provider '{current}' is unavailable; continuing safely with configured fallback '{fallback}'."
    )
    if not getattr(task, "pending_codegen_fallback", None) and hasattr(task, "set_recovery_state"):
        task.set_recovery_state(
            "retry_pending",
            "Recovering safely: the AI provider changed. Xelora will inspect the live workbook before any further Excel changes.",
            safe_to_continue=False,
        )
    return True


def tool_input(tool_call) -> dict:
    """Return a provider-neutral mapping of the tool arguments."""
    # ``tool_call`` does not carry its task.  Core supplies the active task to
    # submit_tool_result. Parsing is selected by the native call shape, which
    # is unambiguous across the supported providers.
    if hasattr(tool_call, "input"):
        return dict(tool_call.input)
    if isinstance(tool_call, dict):
        return openrouter_tool_input(tool_call)
    return gemini_tool_input(tool_call)


def submit_tool_result(task, tool_call, result):
    """Append a tool result in the conversation format expected by the active provider."""
    provider = active_provider_name(task)
    if provider == "claude":
        submit_claude_tool_result(task, tool_call, result)
    elif provider == "openrouter":
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


def _starts_with_gemini_tool_response(content) -> bool:
    """Whether ``content`` is a pending response to Gemini function calls."""
    return (
        isinstance(content, dict)
        and isinstance(content.get(_GEMINI_FUNCTION_RESPONSES_KEY), list)
        and bool(content[_GEMINI_FUNCTION_RESPONSES_KEY])
    )


def _begin_clean_gemini_continuation_after_model_switch(task):
    """Create a normal user-turn boundary before changing Gemini models.

    Gemini 3 validates thought signatures for function calls in the current
    turn. A rate limit can force a fallback from the model that produced the
    calls to one with stricter validation. Keep completed tool responses in
    history, then begin a valid new turn for the fallback model.
    """
    original_request = str(getattr(task, "instruction", "") or "").strip()
    # A fallback model does not share the previous model's implicit plan. Make
    # the user goal explicit at the new user-turn boundary, rather than leaving
    # it to infer a large workbook build from a long tool-response history.
    content = (
        "Continue the same Excel task using the completed tool results already "
        "in the conversation history. Do not repeat verified actions; inspect "
        "the workbook before any further changes.\n\n"
        "Authoritative original user request (continue this, do not replace it):\n"
        f"{original_request}"
    )
    task.messages.append({"role": "user", "content": content})
    return content


def _is_transient_gemini_transport_error(error: Exception) -> bool:
    """Identify network/read timeouts that are safe to try on the next model."""
    name = type(error).__name__.lower()
    message = str(error).lower()
    transient_terms = (
        "timeout", "timed out", "connection reset", "connection aborted",
        "connection refused", "network is unreachable", "temporarily unavailable",
        "server disconnected", "remoteprotocolerror", "remote protocol error",
    )
    return any(term in name or term in message for term in transient_terms)


def call_gemini(task, system_prompt: str):
    from google import genai
    from google.genai import errors, types

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
    reset_tool_turn_for_fallback = False
    deadline = time.monotonic() + config.GEMINI_TOTAL_TIMEOUT_SECONDS

    for model_offset in range(len(config.GEMINI_MODEL_CHAIN)):
        remaining_seconds = deadline - time.monotonic()
        if remaining_seconds <= 0:
            last_error = TimeoutError(
                f"Gemini model chain exceeded its {config.GEMINI_TOTAL_TIMEOUT_SECONDS}s response budget."
            )
            task.log_step("Gemini response budget reached; handing off without waiting for more models.")
            break
        model_index = (task.gemini_model_index + model_offset) % len(config.GEMINI_MODEL_CHAIN)
        model_name = config.GEMINI_MODEL_CHAIN[model_index]
        history = _convert_history_for_gemini(task.messages[:-1])
        prompt_parts = _gemini_parts_from_content(last_user_msg, types)
        if not prompt_parts:
            raise ValueError("Gemini received an empty conversation message.")
        contents = history + [types.Content(role="user", parts=prompt_parts)]

        for attempt in range(RETRIES_PER_MODEL):
            try:
                remaining_seconds = deadline - time.monotonic()
                if remaining_seconds <= 0:
                    last_error = TimeoutError(
                        f"Gemini model chain exceeded its {config.GEMINI_TOTAL_TIMEOUT_SECONDS}s response budget."
                    )
                    break
                client = genai.Client(
                    api_key=config.GEMINI_API_KEY,
                    http_options=types.HttpOptions(
                        timeout=max(1, int(min(config.GEMINI_TIMEOUT_SECONDS, remaining_seconds) * 1000))
                    ),
                )
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
                    if (
                        not reset_tool_turn_for_fallback
                        and _starts_with_gemini_tool_response(last_user_msg)
                        and model_offset < len(config.GEMINI_MODEL_CHAIN) - 1
                    ):
                        last_user_msg = _begin_clean_gemini_continuation_after_model_switch(task)
                        reset_tool_turn_for_fallback = True
                        task.log_step(
                            "Gemini rate-limited during a tool turn; starting a clean "
                            "continuation before switching models."
                        )
                    task.log_step(f"🔀 '{model_name}' is rate-limited - switching models without waiting.")
            except errors.ServerError as e:
                last_error = e
                if attempt < RETRIES_PER_MODEL - 1:
                    task.log_step(f"⚠️ '{model_name}' produced a malformed function call - retrying once more.")
                else:
                    task.log_step(f"🔀 '{model_name}' keeps producing malformed function calls - "
                                   f"switching to the next model in the fallback chain.")

            except Exception as e:
                if not _is_transient_gemini_transport_error(e):
                    raise
                last_error = e
                task.log_step(
                    f"Gemini model '{model_name}' had a transient network/read timeout; switching models."
                )

    raise last_error or RuntimeError("Gemini did not return a usable response from any configured model.")


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
    import requests
    
    api_key = config.OPENROUTER_API_KEY
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is not configured")
    
    model_chain = config.OPENROUTER_MODEL_CHAIN  # Already a list from config.py
    timeout = config.OPENROUTER_TIMEOUT_SECONDS
    
    # Diagnostic output deliberately excludes credentials. Logs are often
    # pasted into support chats and must never reveal an API-key prefix.
    import sys
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
    # Keep OpenRouter feature parity with Gemini/Claude: hybrid mode exposes
    # skills, focused code generation, and the visual fallback catalogue.
    for tool in build_claude_tools():
        tools.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"]
            }
        })
    
    # Try each verified function-calling model in the chain.  The chain is
    # deliberately short and curated in config.py; routing to every available
    # OpenRouter model would make a failure path slower and less predictable.
    models_to_try = model_chain  # Already a list from config.py
    last_error = None
    deadline = time.monotonic() + config.OPENROUTER_TOTAL_TIMEOUT_SECONDS
    for model_index, model in enumerate(models_to_try):
        try:
            remaining_seconds = deadline - time.monotonic()
            if remaining_seconds <= 0:
                last_error = TimeoutError(
                    f"OpenRouter model chain exceeded its {config.OPENROUTER_TOTAL_TIMEOUT_SECONDS}s response budget."
                )
                task.log_step("OpenRouter response budget reached; handing off without waiting for more models.")
                break
            # Optional deployment-specific spacing.  There is no deliberate
            # three-second wait before the first model or every normal task.
            # That pause previously made the desktop agent look stuck.
            if model_index and config.OPENROUTER_INTER_MODEL_DELAY_SECONDS > 0:
                time.sleep(min(config.OPENROUTER_INTER_MODEL_DELAY_SECONDS, remaining_seconds))
                remaining_seconds = deadline - time.monotonic()
                if remaining_seconds <= 0:
                    last_error = TimeoutError(
                        f"OpenRouter model chain exceeded its {config.OPENROUTER_TOTAL_TIMEOUT_SECONDS}s response budget."
                    )
                    task.log_step("OpenRouter response budget reached; handing off without waiting for more models.")
                    break
            
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
                "tool_choice": (
                    {"type": "function", "function": {"name": "run_excel_code"}}
                    if getattr(task, "pending_codegen_fallback", None)
                    else (
                        {"type": "function", "function": {"name": _recovery_inspection_tool_name(task)}}
                        if _recovery_inspection_tool_name(task)
                        else "auto"
                    )
                ),
                "max_tokens": 4096,
                "temperature": 0.7
            }
            
            try:
                response = requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=max(1, min(timeout, remaining_seconds))
                )
            except requests.exceptions.Timeout as exc:
                last_error = exc
                print(f"[OpenRouter] Timeout with {model} after {timeout}s", file=sys.stderr)
                task.log_step(f"OpenRouter timeout with {model}")
                continue
            except requests.exceptions.ConnectionError as e:
                last_error = e
                print(f"[OpenRouter] Connection error with {model}: {e}", file=sys.stderr)
                task.log_step(f"OpenRouter connection error with {model}")
                continue
            
            if response.status_code == 429:
                # Rate limited, try next model
                last_error = RuntimeError(f"OpenRouter rate limited model '{model}' (HTTP 429).")
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
            
            if not tool_calls and not isinstance(text, str):
                text = ""
            if not tool_calls and not text.strip():
                last_error = RuntimeError(
                    f"OpenRouter model '{model}' returned neither text nor a tool call."
                )
                task.log_step(
                    f"OpenRouter model '{model}' returned an empty response; trying the next configured model."
                )
                continue

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
        raise last_error
    raise RuntimeError("OpenRouter did not return a usable response from any configured model.")


def submit_openrouter_tool_result(task, tool_call_id: str, result: dict):
    """Submit tool result back to OpenRouter (stored in message history)."""
    # OpenRouter uses OpenAI format - results are stored as messages
    # Excel returns native ``datetime`` and ``Decimal`` values when a range is
    # read.  Unlike Gemini's response normaliser, this OpenAI-compatible path
    # previously passed those objects directly to json.dumps(), which stopped
    # the whole task after a perfectly valid read_range call.  Tool results
    # are conversation data, so stringify only values JSON cannot represent.
    task.messages.append({
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": json.dumps(result, default=str)
    })


def openrouter_tool_input(tool_call: dict) -> dict:
    """Extract tool input from OpenRouter tool call."""
    return tool_call.get("arguments", {})
