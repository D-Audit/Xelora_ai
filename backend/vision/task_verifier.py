"""Low-risk end-state evidence for visual-only Excel tasks.

This module intentionally does not claim that a screenshot proves workbook
math.  In OmniParser-only mode it verifies the live visual session is still
usable, reports any popup that would invalidate later input, and records the
visible workbook/sheet evidence for the task log.
"""

from __future__ import annotations

from vision.screenshot_cache import get_cached_screen_context


def verify_excel_task(instruction: str) -> dict:
    """Collect visual-session evidence without modifying Excel."""
    from vision import ui_control

    try:
        context = ui_control.get_visual_excel_context()
        popup = ui_control.inspect_popup()
        sheets = ui_control.get_existing_sheet_names()
        active_sheet_result = ui_control.get_active_sheet_name()
        active_sheet = active_sheet_result.get("sheet_name")
    except Exception as exc:  # noqa: BLE001 - report evidence failure to the agent
        return {
            "overall_status": "unavailable",
            "verified": False,
            "retry_suggestion": f"Visual end-state evidence could not be collected: {exc}",
        }

    if popup.get("status") != "clean":
        return {
            "overall_status": "needs_attention",
            "verified": False,
            "popup": popup,
            "retry_suggestion": "A classified Excel popup remains open. Inspect and resolve it before more input.",
        }

    return {
        "overall_status": "verified",
        "verified": True,
        "instruction": instruction,
        "workbook": {
            "window_title": context.get("window_title"),
            "office_version": context.get("office_version"),
            "active_sheet": active_sheet,
            "sheet_names": sheets,
        },
        "cached_screen": get_cached_screen_context(),
        "verification_note": (
            "The visible Excel session is responsive and free of blocking popups. "
            "This visual check is supplementary; individual task actions retain their own verification evidence."
        ),
    }
