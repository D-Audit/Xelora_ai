"""Keyboard shortcuts used by the optional visible Excel control layer."""

from __future__ import annotations

from typing import Iterable


# Standard Excel shortcuts are preferred where they exist.  This is a
# deliberately named, tested registry for actions the agent can request by
# intent; it is not a claim that Excel has a fixed shortcut for every command.
# For commands that differ by Office build or have no direct shortcut, callers
# can use ``execute_alt_sequence`` with Excel's live Ribbon KeyTips.
#
# Alt sequences are sent one key at a time because Excel's ribbon key tips are
# sequential, not a simultaneous chord.
EXCEL_SHORTCUTS: dict[str, tuple[str, ...]] = {
    # File and task navigation
    "save": ("ctrl", "s"),
    "save_as": ("f12",),
    "open": ("ctrl", "o"),
    "new_workbook": ("ctrl", "n"),
    "close_workbook": ("ctrl", "w"),
    "print": ("ctrl", "p"),
    "undo": ("ctrl", "z"),
    "redo": ("ctrl", "y"),
    "find": ("ctrl", "f"),
    "replace": ("ctrl", "h"),
    "go_to": ("ctrl", "g"),
    "select_all": ("ctrl", "a"),
    "edit_cell": ("f2",),
    "repeat_last_action": ("f4",),
    "new_worksheet": ("shift", "f11"),
    "next_worksheet": ("ctrl", "pagedown"),
    "previous_worksheet": ("ctrl", "pageup"),

    # Editing and filling
    "fill_down": ("ctrl", "d"),
    "fill_right": ("ctrl", "r"),
    "autosum": ("alt", "="),
    "bold": ("ctrl", "b"),
    "italic": ("ctrl", "i"),
    "underline": ("ctrl", "u"),
    "format_cells": ("ctrl", "1"),
    "currency": ("ctrl", "shift", "4"),
    "percent": ("ctrl", "shift", "5"),
    "comma": ("ctrl", "shift", "1"),
    "center_align": ("alt", "h", "a", "c"),
    "left_align": ("alt", "h", "a", "l"),
    "right_align": ("alt", "h", "a", "r"),
    "all_borders": ("alt", "h", "b", "a"),
    "no_borders": ("alt", "h", "b", "n"),
    "merge_center": ("alt", "h", "m", "c"),
    "unmerge": ("alt", "h", "m", "u"),
    "auto_fit_column": ("alt", "h", "o", "i"),
    "auto_fit_row": ("alt", "h", "o", "a"),
    "sort_ascending": ("alt", "a", "s", "a"),
    "sort_descending": ("alt", "a", "s", "d"),
    "filter": ("ctrl", "shift", "l"),
    "insert_table": ("ctrl", "t"),
    "default_chart": ("alt", "f1"),
    "chart_sheet": ("f11",),
    "insert_column_chart": ("alt", "n", "c"),
    "insert_pie_chart": ("alt", "n", "q"),
    "freeze_panes": ("alt", "w", "f", "f"),
    "copy": ("ctrl", "c"),
    "cut": ("ctrl", "x"),
    "paste": ("ctrl", "v"),
    "paste_values": ("alt", "h", "v", "v"),
    "format_painter": ("alt", "h", "f", "p"),
}

OPERATION_MODULES = {
    "file": ("save", "save_as", "open", "new_workbook", "close_workbook", "print"),
    "navigation": ("go_to", "next_worksheet", "previous_worksheet", "select_all"),
    "editing": ("undo", "redo", "find", "replace", "edit_cell", "fill_down", "fill_right", "autosum"),
    "format": ("bold", "italic", "underline", "currency", "percent", "comma"),
    "alignment": ("center_align", "left_align", "right_align"),
    "borders": ("all_borders", "no_borders"),
    "data": ("sort_ascending", "sort_descending", "filter", "insert_table"),
    "chart": ("default_chart", "chart_sheet", "insert_column_chart", "insert_pie_chart"),
}


_MODIFIER_ALIASES = {"ctrl": "ctrl", "control": "ctrl", "alt": "alt", "shift": "shift"}
_STANDARD_KEYS = {
    "backspace", "tab", "enter", "esc", "escape", "space", "pageup", "pagedown",
    "home", "end", "left", "right", "up", "down", "insert", "delete", "plus",
    "minus", "=", "+", "-", ",", ".", "/", ";", "[", "]", "\\", "'", "`",
    *(chr(code) for code in range(ord("a"), ord("z") + 1)),
    *(str(number) for number in range(10)),
    *(f"f{number}" for number in range(1, 13)),
}


def get_shortcut_for_operation(operation: str) -> tuple[str, ...] | None:
    """Return the configured shortcut for a friendly operation name."""
    return EXCEL_SHORTCUTS.get(str(operation).strip().lower())


def resolve_shortcut(shortcut: str) -> tuple[tuple[str, ...], str] | None:
    """Resolve a named operation or a standard shortcut expression.

    A hard-coded catalog can never cover every Excel edition, add-in, and
    localized Ribbon command.  This resolver keeps the friendly names while
    allowing the agent to send any conventional Excel chord directly, for
    example ``ctrl+shift+l``, ``ctrl+alt+v``, ``f4``, or ``alt+f1``.  Ribbon
    KeyTips remain a separate sequential action via ``execute_alt_sequence``.
    """
    normalized = str(shortcut).strip().lower()
    named = get_shortcut_for_operation(normalized)
    if named:
        return named, "named"
    if not normalized or "+" not in normalized:
        if normalized in _STANDARD_KEYS:
            return (normalized,), "raw_chord"
        return None

    keys = tuple(part.strip() for part in normalized.split("+") if part.strip())
    if len(keys) < 2:
        return None
    normalized_keys = tuple(_MODIFIER_ALIASES.get(key, key) for key in keys)
    modifiers = normalized_keys[:-1]
    final_key = normalized_keys[-1]
    if (
        not modifiers
        or any(key not in {"ctrl", "alt", "shift"} for key in modifiers)
        or final_key not in _STANDARD_KEYS
    ):
        return None
    return normalized_keys, "raw_chord"


def _normalized_keys(keys: Iterable[str]) -> tuple[str, ...]:
    return tuple(str(key).strip().lower() for key in keys if str(key).strip())


def execute_alt_sequence(keys: Iterable[str]) -> bool:
    """Open Excel ribbon key tips and send each follow-up key in order."""
    normalized = _normalized_keys(keys)
    if not normalized:
        return False
    try:
        import pyautogui

        sequence = normalized[1:] if normalized[0] == "alt" else normalized
        pyautogui.press("alt")
        for key in sequence:
            pyautogui.press(key)
        return True
    except Exception:
        return False


def execute_shortcut(shortcut_name: str) -> bool:
    """Execute a named operation or validated standard chord."""
    resolved = resolve_shortcut(shortcut_name)
    if not resolved:
        return False
    keys, shortcut_kind = resolved
    if shortcut_kind == "named" and keys[0] == "alt":
        # These are simultaneous keyboard chords, not Ribbon KeyTips.
        # Sending Alt and F1 (or =) sequentially would leave Excel in its
        # KeyTip mode instead of invoking the native shortcut.
        if len(keys) == 2 and keys[1] in {"f1", "="}:
            try:
                import pyautogui

                pyautogui.hotkey(*keys)
                return True
            except Exception:
                return False
        return execute_alt_sequence(keys)
    try:
        import pyautogui

        pyautogui.hotkey(*keys)
        return True
    except Exception:
        return False
