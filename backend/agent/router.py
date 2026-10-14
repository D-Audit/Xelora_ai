"""Deterministic capability routing for a task instruction.

The model still chooses individual tool calls, but it receives a short,
ordered capability chain computed here from the instruction and the live
configuration, instead of inferring priorities from ~100 tool schemas.
Execution policy is enforced separately (agent.permissions); this module
only recommends.

Priority for Excel work (cheapest reliable method first):
    Excel skill/API -> bounded Python codegen (large transforms)
    -> keyboard shortcuts / Name Box -> Cua accessibility-targeted input
    -> visual UI automation -> OmniParser (unknown visual elements only)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import config


@dataclass(frozen=True)
class RouteStep:
    capability: str
    tools: tuple[str, ...]
    reason: str


@dataclass
class RoutePlan:
    intents: list[str]
    steps: list[RouteStep] = field(default_factory=list)
    unavailable: list[str] = field(default_factory=list)

    def capabilities(self) -> list[str]:
        return [step.capability for step in self.steps]

    def as_dict(self) -> dict[str, Any]:
        return {
            "intents": list(self.intents),
            "chain": [{"capability": s.capability, "tools": list(s.tools), "reason": s.reason} for s in self.steps],
            "unavailable": list(self.unavailable),
        }


_CELL_REF = re.compile(r"\b[A-Z]{1,3}[1-9][0-9]{0,6}(:[A-Z]{1,3}[1-9][0-9]{0,6})?\b")
_URL = re.compile(r"https?://", re.I)
_PATTERNS: dict[str, re.Pattern[str]] = {
    "research": re.compile(
        r"\b(latest|current|today'?s?|recent|news|look ?up|search (the )?(web|internet|online)|research|"
        r"on the (web|internet)|online|website|exchange rate|stock price|inflation|population)\b", re.I),
    "user_file": re.compile(r"\b(csv|tsv|json|txt|uploaded|my files?|the file|this file|attachment|workspace file)\b|\.(csv|tsv|json|txt|md)\b", re.I),
    # Only work the skills cannot express well. Dedicated skills exist for
    # dedupe (remove_duplicates), merge (merge_columns/combine_sheets) and
    # unpivot (unpivot_data), so those words alone do not force codegen.
    "large_transform": re.compile(
        r"\b(pandas|numpy|python|large (data ?set|dataset|file)|huge|millions?|"
        r"(thousands|hundreds) of rows|\d{1,3}(,\d{3})+ rows|\d{4,} rows|\d{3,} (records|transactions|rows)|"
        r"join (the |two )?tables|fuzzy|reshape|group ?by|standard deviation|regression|correlation)\b", re.I),
    "terminal": re.compile(r"\b(terminal|command line|shell|run (the )?tests?|pytest|git (status|log|diff)|pip (show|install))\b", re.I),
    "gui": re.compile(
        r"\b(click|press the|button|dialog|ribbon|menu|checkbox|check box|drop-?down|popup|pop-up|"
        r"window|toolbar|task pane|add-?in|on screen|visible)\b", re.I),
    "mcp": re.compile(r"\b(mcp|integration|connector)\b", re.I),
    "excel": re.compile(
        r"\b(excel|workbook|worksheet|sheet|cells?|range|column|row|formula|format|currency|bold|"
        r"sort|filter|table|chart|pivot|conditional|fill down|sum|average|vlookup|xlookup|spreadsheet)\b", re.I),
}


# Request wording -> the dedicated skills built for it, so the model reaches
# for e.g. export_to_pdf or data_validation instead of improvising with
# generic writes or code. Only registered skills are ever recommended.
_FEATURE_HINTS: tuple[tuple[re.Pattern[str], tuple[str, ...], str], ...] = tuple(
    (re.compile(pattern, re.I), tools, reason) for pattern, tools, reason in (
        (r"\bdashboard|kpi|scorecard\b", ("create_sheets", "create_pivot_table", "create_chart", "add_slicer",
         "add_shape", "add_sparkline", "arrange_dashboard_layout"),
         "Dashboard: data Table -> summary formulas/pivot -> KPI cards, charts, slicers -> reflow layout."),
        (r"\bpdf\b|\bprint|page setup|landscape|portrait", ("set_page_layout", "export_to_pdf"),
         "Set the page layout first, then export the sheet to PDF."),
        (r"\bpivot|summari[sz]e by|break ?down by|group(ed)? by", ("create_pivot_table", "refresh_pivot_table", "add_slicer"),
         "Use a native PivotTable (and slicers for interactive filtering)."),
        (r"\bchart|graph|plot|visuali[sz]", ("create_chart", "modify_chart", "position_chart"),
         "Chart from a bounded summary range, titled and placed beside the data."),
        (r"\bsparkline|trend line in (the )?cell", ("add_sparkline",), "In-cell trend per row."),
        (r"drop-?down|pick ?list|list of (options|choices)|validation|restrict (input|entries)",
         ("data_validation", "add_dropdown_control"), "In-cell lists and input limits via data validation."),
        (r"\bfilter", ("set_autofilter", "filter_data"),
         "set_autofilter adds filter arrows; filter_data only reads matching rows."),
        (r"highlight|heat ?map|colou?r (code|scale)|traffic light|data bars?|icons?\b",
         ("conditional_formatting", "color_scale_formatting", "data_bar_formatting", "icon_set_formatting"),
         "Use the matching conditional-format skill rather than static fills."),
        (r"duplicate", ("remove_duplicates",), "Dedicated de-duplication."),
        (r"\bsplit\b|separate (the )?(first|last) names?", ("split_column",), "Split one column into several."),
        (r"\b(merge|join|concatenate|combine)\b.*\bcolumns?\b", ("merge_columns",),
         "Join several columns into one."),
        (r"\bcombine|merge (the )?sheets|consolidate|stack", ("combine_sheets",),
         "Stack or consolidate similar sheets."),
        (r"unpivot|wide to long|long format", ("unpivot_data",), "Reshape wide data to long."),
        (r"budget|actual vs|vs\.? actual|variance", ("variance_analysis",), "Formula-based budget vs actual."),
        (r"scenario|what-?if|sensitivity|best case|worst case", ("scenario_builder", "create_named_range"),
         "Scenario tables driven by named inputs."),
        (r"\bprotect|\block\b|password", ("protect_sheet", "unprotect_sheet"), "Sheet protection, only as asked."),
        (r"\bhide|unhide", ("set_sheet_visibility", "group_rows_columns"), "Hide sheets or collapse rows/columns."),
        (r"\bcomment|\bnote\b", ("add_comment",), "Cell notes for assumptions and sources."),
        (r"hyperlink|\blink to|table of contents|contents page", ("add_hyperlink",), "Clickable links."),
        (r"\blogo|picture|image|photo", ("insert_picture",), "Place an image file on the sheet."),
        (r"\bmacro|\bvba\b|\bbutton|\.xlsm", ("check_vba_access", "create_vba_macro", "add_macro_button",
         "run_macro", "save_as_macro_enabled"), "Check VBA trust first; save as .xlsm."),
        (r"\bsql\b|database|postgres|mysql|sql server", ("import_from_database",), "Run the user's query into a sheet."),
        (r"power query|get data|refreshable|connection", ("create_power_query_connection",), "A refreshable data connection."),
        (r"\bapi\b|live (rate|price|data)|exchange rate|stock price", ("fetch_live_data", "web_search"),
         "Live values from a named API, or researched with a cited source."),
        (r"\bpdf\b.*\b(into|to) (excel|a sheet)|scanned|invoice|receipt|\.docx|word document|extract (the )?table",
         ("import_unstructured_document",), "Extract tables/text from a document into a sheet."),
        (r"\bopen\b.*\.(xlsx|xlsm|xls|csv)|open (my|the) (file|workbook)", ("open_workbook",), "Open the named file."),
        (r"\bsave as|save (it )?(to|in|as)|name (it|the file)", ("create_new_workbook",), "Save under the requested name."),
        (r"knowledge base|our (policy|policies|sop|manual|documents?)|company (data|documents?)",
         ("search_knowledge_base",), "Use the user's stored documents."),
        (r"\bfreeze", ("freeze_panes",), "Freeze header rows/columns."),
        (r"named range|name (the|this) (cell|range)", ("create_named_range",), "Readable named inputs."),
        (r"sort|rank|order by|largest|smallest|top \d+", ("sort_range",), "Native sort."),
        (r"copy (the |this )?sheet|duplicate (the |this )?sheet", ("copy_sheet",), "Duplicate a sheet with formatting."),
        (r"insert (a |an )?(row|column)|add (a |an )?(row|column)", ("insert_row", "insert_column"), "Insert rows/columns."),
        (r"delete (the )?(row|column|sheet|chart)|remove (the )?(row|column|sheet|chart)",
         ("delete_row", "delete_column", "delete_sheet", "delete_chart"), "Delete only what was asked."),
    )
)


def feature_skills(instruction: str) -> list[RouteStep]:
    """Dedicated skills whose purpose matches the instruction's wording."""
    try:
        from skills.registry import has_skill
    except Exception:  # registry unavailable (e.g. a minimal test import)
        has_skill = None
    steps, seen = [], set()
    for pattern, tools, reason in _FEATURE_HINTS:
        if not pattern.search(instruction or ""):
            continue
        usable = tuple(t for t in tools if t not in seen and (
            has_skill is None or has_skill(t) or t.startswith("web_")))
        if usable:
            seen.update(usable)
            steps.append(RouteStep("feature_skills", usable, reason))
    return steps


def _availability() -> dict[str, bool]:
    return {
        "codegen": bool(config.ENABLE_CODEGEN_LAYER),
        "terminal": bool(config.ENABLE_TERMINAL_TOOLS),
        "cua": bool(config.ENABLE_CUA_DRIVER),
        "visual": bool(config.ENABLE_VISUAL_FALLBACK or config.VISUAL_ONLY_MODE),
        "shortcuts": bool(config.ENABLE_EXCEL_SHORTCUTS or config.ENABLE_VISUAL_FALLBACK or config.VISUAL_ONLY_MODE),
        "omniparser": bool(config.OMNIPARSER_URL or config.OMNIPARSER_LOCAL_MODE),
        "mcp": bool(getattr(config, "ENABLE_MCP_CLIENT", False)),
    }


def ui_method_chain(available: dict[str, bool]) -> tuple[list[RouteStep], list[str]]:
    """Ordered methods for an Excel UI interaction the API cannot perform."""
    steps: list[RouteStep] = []
    missing: list[str] = []
    if available.get("shortcuts", available["visual"]):
        steps.append(RouteStep("excel_shortcuts", ("execute_excel_shortcut", "press_alt", "inspect_popup", "click_popup_button"),
                               "Known ribbon/dialog actions have deterministic keyboard paths (shortcuts, KeyTips)."))
    if available["cua"]:
        steps.append(RouteStep(
            "cua_accessibility", ("cua__get_window_state", "cua_act_and_verify", "cua__verify_state"),
            "Observe the exact Excel window's accessibility tree, act by element, verify with predicates."))
    else:
        missing.append("cua (ENABLE_CUA_DRIVER=false)")
    if available["visual"]:
        steps.append(RouteStep("ui_automation", ("inspect_popup", "click_popup_button", "find_and_click"),
                               "Windows UI Automation for dialogs and named controls."))
        if available["omniparser"]:
            steps.append(RouteStep("omniparser", ("parse_screen", "click"),
                                   "Last resort for unlabelled visual elements; costs a screenshot parse."))
        else:
            missing.append("omniparser (OMNIPARSER_URL/OMNIPARSER_LOCAL_MODE not set)")
    else:
        missing.append("visual UI automation (ENABLE_VISUAL_FALLBACK=false)")
    return steps, missing


def route_instruction(instruction: str, *, file_access: bool = True, available: dict[str, bool] | None = None) -> RoutePlan:
    """Classify an instruction and return an ordered capability chain."""
    text = instruction or ""
    available = available or _availability()
    matched = {name for name, pattern in _PATTERNS.items() if pattern.search(text)}
    if _URL.search(text):
        matched.add("research")
    if _CELL_REF.search(text):
        matched.add("excel")
    plan = RoutePlan(intents=sorted(matched) or ["excel"])

    if "terminal" in matched:
        if available["terminal"]:
            plan.steps.append(RouteStep("terminal", ("run_terminal",), "Explicit command-line request; allowlisted argv only."))
        else:
            plan.unavailable.append("terminal (ENABLE_TERMINAL_TOOLS=false): explain that the administrator must enable it.")
    if "research" in matched:
        plan.steps.append(RouteStep("web_research", ("web_search", "web_fetch"),
                                    "Current facts: search, fetch the primary source, cite its URL."))
    if "user_file" in matched:
        if file_access:
            plan.steps.append(RouteStep("user_files", ("list_workspace_files", "import_workspace_file_to_sheet", "read_workspace_file"),
                                        "Find the stored file (uploaded names show as uploaded_as). To put a CSV/XLSX into Excel use "
                                        "import_workspace_file_to_sheet (bulk, any size); read_workspace_file only to inspect text."))
        else:
            plan.unavailable.append("user files (task is not signed in)")
    if "mcp" in matched and available["mcp"]:
        plan.steps.append(RouteStep("mcp", ("mcp__*",), "An administrator-configured MCP integration was requested."))

    wants_excel = "excel" in matched or not (matched - {"gui"}) or "large_transform" in matched or (
        matched & {"research", "user_file"} and re.search(r"\b(put|write|insert|place|add|into|table|sheet)\b", text, re.I)
    )
    if "large_transform" in matched and available["codegen"]:
        plan.steps.append(RouteStep("python_codegen", ("run_excel_code",),
                                    "Large or multi-step data transformation; run sandboxed xlwings + pandas/numpy code (read from one sheet, write to one sheet), then read back. Prefer a dedicated skill (remove_duplicates, combine_sheets, unpivot_data, create_pivot_table) when one fits."))
    if wants_excel:
        plan.steps.append(RouteStep("excel_skills", ("inspect_workbook", "read_range", "write_table", "write_cell", "insert_formula", "format_range"),
                                    "Structured Excel API skills are the default for cells, ranges, formulas, and formatting."))
        plan.steps.extend(feature_skills(text))
        if available.get("shortcuts", available["visual"]) and "gui" not in matched:
            plan.steps.append(RouteStep(
                "excel_shortcuts", ("go_to_range", "go_to_sheet", "execute_excel_shortcut", "press_alt"),
                "Navigate, select, reveal results and run standard commands by keyboard; check the effect."))
    if "gui" in matched:
        ui_steps, missing = ui_method_chain(available)
        plan.steps.extend(ui_steps)
        plan.unavailable.extend(missing)
    if not plan.steps:
        plan.steps.append(RouteStep("excel_skills", ("inspect_workbook",), "Default: inspect the workbook first."))
    return plan


def routing_context(plan: RoutePlan) -> str:
    """A compact prompt section describing the recommended chain."""
    lines = ["\n\nCAPABILITY HINTS (matched from the request's wording; a starting point, not an order. "
             "Your reading of the live workbook and the request decides; verify each result):"]
    for index, step in enumerate(plan.steps, 1):
        lines.append(f"{index}. {step.capability}: {', '.join(step.tools)} - {step.reason}")
    if plan.unavailable:
        lines.append("Unavailable here: " + "; ".join(plan.unavailable) + ". Do not pretend to use these.")
    return "\n".join(lines) + "\n"
