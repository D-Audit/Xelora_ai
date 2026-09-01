"""Runtime capability catalogue for evidence-based Excel tool selection.

This module describes what Xelora can do *now* from the live registries and
configuration.  It deliberately does not prescribe task-specific scripts.
The planning model receives the current workbook evidence plus this catalogue,
then selects the smallest safe tool for each goal.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import config
from skills.base import SKILL_REGISTRY
from vision.excel_shortcuts import EXCEL_SHORTCUTS, OPERATION_MODULES


def _execution_profile() -> str:
    if config.VISUAL_ONLY_MODE:
        return "visual_only"
    if config.ENABLE_VISUAL_FALLBACK:
        return "hybrid"
    return "structured_only"


def build_execution_capabilities() -> dict[str, Any]:
    """Return the discoverable skills, shortcuts, layers, and safety policy.

    The result is intentionally data rather than prompt text so it can be
    shown to either AI provider and recorded as evidence in an action log.
    """
    skills_by_category: dict[str, list[dict[str, str]]] = defaultdict(list)
    for name, entry in SKILL_REGISTRY.items():
        skills_by_category[str(entry.get("category") or "general")].append({
            "name": name,
            "description": str(entry.get("description") or ""),
        })
    for skills in skills_by_category.values():
        skills.sort(key=lambda item: item["name"])

    shortcut_modules = {
        module: [
            {
                "operation": operation,
                "keys": list(EXCEL_SHORTCUTS[operation]),
            }
            for operation in operations
            if operation in EXCEL_SHORTCUTS
        ]
        for module, operations in OPERATION_MODULES.items()
    }
    assigned_shortcuts = {
        entry["operation"]
        for entries in shortcut_modules.values()
        for entry in entries
    }
    ungrouped_shortcuts = [
        {"operation": operation, "keys": list(keys)}
        for operation, keys in sorted(EXCEL_SHORTCUTS.items())
        if operation not in assigned_shortcuts
    ]

    return {
        "verified": True,
        "execution_profile": _execution_profile(),
        "available_layers": {
            "skills_api": {
                "enabled": not config.VISUAL_ONLY_MODE,
                "skill_count": len(SKILL_REGISTRY),
                "categories": dict(sorted(skills_by_category.items())),
            },
            "code_generation": {
                "enabled": bool(config.ENABLE_CODEGEN_LAYER and not config.VISUAL_ONLY_MODE),
                "use_when": "No verified skill covers the required workbook operation.",
            },
            "name_box_and_shortcuts": {
                "enabled": bool(config.ENABLE_VISUAL_FALLBACK),
                "shortcut_modules": shortcut_modules,
                "ungrouped_shortcuts": ungrouped_shortcuts,
                "raw_standard_chords": "Validated conventional Ctrl/Shift/Alt chords are also accepted.",
            },
            "visible_ui": {
                "enabled": bool(config.ENABLE_VISUAL_FALLBACK),
                "methods": ["UI Automation", "native Excel dialogs", "OmniParser for unknown visible controls"],
            },
        },
        "selection_order": [
            "Inspect the workbook state before changing an unfamiliar workbook.",
            "Use a verified skill/API when it exactly covers the goal.",
            "Use focused code generation only when no skill covers the goal.",
            "Use Name Box navigation and a shortcut for a simple, safe visible command.",
            "Use UI Automation, then OmniParser, only for a required visible control or popup.",
            "Read the workbook or popup back after every important change.",
        ],
        "failure_policy": {
            "never": [
                "repeat an unverified action blindly",
                "invent click coordinates",
                "approve security, overwrite, protection, or link-update dialogs automatically",
                "claim completion without verification evidence",
            ],
            "require": [
                "inspect the returned failure evidence",
                "choose a compatible next layer",
                "stop and report when no safe verified route remains",
            ],
        },
    }


def workbook_state_summary(workbook_state: Any) -> dict[str, Any]:
    """Keep a useful, bounded workbook observation in the planner prompt."""
    if not isinstance(workbook_state, dict):
        return {"verified": False, "error": "No workbook state was collected."}
    if workbook_state.get("verified") is not True:
        return {
            "verified": False,
            "error": str(workbook_state.get("error") or "Workbook inspection was unavailable."),
        }

    sheet_reports = workbook_state.get("sheet_reports")
    if isinstance(sheet_reports, list):
        sheets = []
        for report in sheet_reports[:30]:
            if not isinstance(report, dict):
                continue
            sheets.append({
                "sheet": report.get("sheet"),
                "used_range": report.get("used_range"),
                "tables": report.get("existing_tables", []),
                "charts": report.get("existing_charts", []),
                "pivots": report.get("existing_pivot_tables", []),
                "formula_error_count": report.get("formula_error_count", 0),
            })
        return {
            "verified": True,
            "workbook_name": workbook_state.get("workbook_name"),
            "sheets": sheets,
            "formula_error_count": workbook_state.get("formula_error_count", 0),
        }

    # Visual-only state already contains a bounded sheet list and active sheet.
    return {
        key: workbook_state.get(key)
        for key in (
            "verified", "window_title", "workbook_name", "active_sheet", "sheet_names",
            "office_version", "application", "popup_status", "formula_error_count",
        )
        if key in workbook_state
    }


def planning_context(workbook_state: Any, excel_version_info: Any) -> str:
    """Format a compact, current decision context for the system prompt."""
    capabilities = build_execution_capabilities()
    skill_count = capabilities["available_layers"]["skills_api"]["skill_count"]
    shortcut_count = len(EXCEL_SHORTCUTS)
    state = workbook_state_summary(workbook_state)
    return (
        "\n\nRUNTIME EXECUTION CONTEXT (authoritative):\n"
        f"- Profile: {capabilities['execution_profile']}.\n"
        f"- Available: {skill_count} registered Excel skills/API operations, "
        f"{shortcut_count} named Excel shortcuts, controlled Name Box navigation, "
        "UI Automation, and OmniParser only for unknown visible controls.\n"
        f"- Excel capability evidence: {excel_version_info!r}\n"
        f"- Workbook-state evidence: {state!r}\n"
        "- Do not use a fixed workflow. Choose the smallest valid method from the "
        "live capability catalogue. Call get_execution_capabilities when you need "
        "the full named skill/shortcut list. After any verified failure, read the "
        "failure's recovery_options and choose a different compatible layer.\n"
    )


def recovery_options(tool_name: str, execution_layer: str | None, result: dict | None) -> dict[str, Any]:
    """Describe safe next choices without deciding the user's task for the AI."""
    detail = " ".join(
        str((result or {}).get(key) or "")
        for key in ("status", "error", "verification_note")
    ).lower()
    if any(marker in detail for marker in (
        "security", "overwrite", "protection", "link-update", "unsupported spreadsheet",
        "not microsoft excel", "window is no longer visible",
    )):
        return {
            "automatic_retry": False,
            "next_steps": ["Stop this operation and report the exact blocking condition."],
        }
    if execution_layer == "skill":
        return {
            "automatic_retry": False,
            "next_steps": [
                "Use focused code generation for the same verified workbook goal when permitted.",
                "If the operation is actually a visible Excel-only command, inspect the UI state and use a safe shortcut or UI Automation.",
                "Verify the workbook state before any alternate write.",
            ],
        }
    if execution_layer == "codegen":
        return {
            "automatic_retry": False,
            "next_steps": [
                "Inspect the workbook to determine whether the attempted change partially applied.",
                "Choose an existing verified skill if one covers the smaller remaining goal.",
                "Use visible UI only when the remaining goal is genuinely UI-only.",
            ],
        }
    if execution_layer in {"visual", "visual_popup_recovery", "popup_gate"}:
        return {
            "automatic_retry": False,
            "next_steps": [
                "Inspect the popup/window state; do not resend the same input blindly.",
                "Use a skill/API for structured workbook work when available.",
                "Use OmniParser only if UI Automation cannot identify a required visible control.",
            ],
        }
    return {
        "automatic_retry": False,
        "next_steps": [
            "Inspect the workbook and current UI state before selecting another supported layer.",
            f"Use get_execution_capabilities to review alternatives for {tool_name}.",
        ],
    }
