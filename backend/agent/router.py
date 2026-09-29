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


def _availability() -> dict[str, bool]:
    return {
        "codegen": bool(config.ENABLE_CODEGEN_LAYER),
        "terminal": bool(config.ENABLE_TERMINAL_TOOLS),
        "cua": bool(config.ENABLE_CUA_DRIVER),
        "visual": bool(config.ENABLE_VISUAL_FALLBACK or config.VISUAL_ONLY_MODE),
        "omniparser": bool(config.OMNIPARSER_URL or config.OMNIPARSER_LOCAL_MODE),
        "mcp": bool(getattr(config, "ENABLE_MCP_CLIENT", False)),
    }


def ui_method_chain(available: dict[str, bool]) -> tuple[list[RouteStep], list[str]]:
    """Ordered methods for an Excel UI interaction the API cannot perform."""
    steps: list[RouteStep] = []
    missing: list[str] = []
    if available["visual"]:
        steps.append(RouteStep("excel_shortcuts", ("execute_excel_shortcut", "press_shortcut", "go_to_range"),
                               "Known ribbon/dialog actions have deterministic keyboard paths."))
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
    if "gui" in matched:
        ui_steps, missing = ui_method_chain(available)
        plan.steps.extend(ui_steps)
        plan.unavailable.extend(missing)
    if not plan.steps:
        plan.steps.append(RouteStep("excel_skills", ("inspect_workbook",), "Default: inspect the workbook first."))
    return plan


def routing_context(plan: RoutePlan) -> str:
    """A compact prompt section describing the recommended chain."""
    lines = ["\n\nCAPABILITY ROUTE (computed by Xelora; prefer this order, verify each result):"]
    for index, step in enumerate(plan.steps, 1):
        lines.append(f"{index}. {step.capability}: {', '.join(step.tools)} - {step.reason}")
    if plan.unavailable:
        lines.append("Unavailable here: " + "; ".join(plan.unavailable) + ". Do not pretend to use these.")
    return "\n".join(lines) + "\n"
