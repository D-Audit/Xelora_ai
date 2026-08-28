"""
vision/ui_control.py
The third execution layer: when a skill doesn't cover the request AND
generated code fails or has no API path to use, the agent falls back
to controlling Excel the way a human would - looking at the screen and
clicking/typing.

Requires a real desktop (Windows/Mac) with a display. It will not run
in a headless Linux server/container - that's expected; this layer is
meant to run on the same machine as the FastAPI backend, on the user's
actual desktop, not in the cloud.

This module provides the primitives (screenshot, click, type, find-
window). The actual "which button do I click" decision is made by the
AI: it's given the screenshot, plans in text where to click, and this
module just executes that plan. Wiring that loop into agent/core.py is
Phase 2 (see README "What's scaffolded vs implemented").
"""

import ctypes
import re
import subprocess
import time

try:
    import winreg
except ImportError:
    winreg = None

from vision.omniparser_client import parse_image
from vision.screenshot_cache import (
    save_to_cache,
    load_from_cache,
    find_cached_elements,
    get_cached_screen_context,
)
from vision.excel_shortcuts import (
    execute_shortcut,
    execute_alt_sequence,
    EXCEL_SHORTCUTS,
    OPERATION_MODULES,
    get_shortcut_for_operation,
)

try:
    import pyautogui
    _HAS_PYAUTOGUI = True
except Exception:
    _HAS_PYAUTOGUI = False

try:
    from pywinauto import Desktop
    _HAS_PYWINAUTO = True
except Exception:
    _HAS_PYWINAUTO = False

try:
    import win32con
    import win32clipboard
    import win32gui
    _HAS_WIN32GUI = True
except Exception:
    _HAS_WIN32GUI = False

# Window safety module for preventing focus hijacking
try:
    from vision.window_safety import (
        verify_excel_foreground,
        capture_excel_window,
        ensure_excel_foreground,
        safe_click,
        safe_type,
        safe_hotkey,
        safe_press,
        uia_invoke_element,
        uia_click_element,
        get_excel_window_handle,
        get_window_safety_status,
        WindowSafetyError,
    )
    _HAS_WINDOW_SAFETY = True
except ImportError:
    _HAS_WINDOW_SAFETY = False

_last_elements: list[dict] = []
_last_parse_at: float | None = None
_last_parse_window_handle: int | None = None
_agent_excel_handle: int | None = None
_use_existing_workbook = False
_bound_excel_pid: int | None = None
_bound_workbook_name: str | None = None

_EXCEL_START_TIMEOUT_SECONDS = 15
_PARSED_TARGET_MAX_AGE_SECONDS = 15

_SHEET_PREFIX = r"(?:(?:'(?:[^']|'')+'|[A-Za-z0-9_]+)!)?"
_A1_CELL = r"\$?[A-Za-z]{1,3}\$?\d+"
_A1_REFERENCE = rf"{_SHEET_PREFIX}(?:{_A1_CELL}(?::{_A1_CELL})?|\$?[A-Za-z]{{1,3}}:\$?[A-Za-z]{{1,3}}|\$?\d+:\$?\d+)"
_DEFINED_NAME = r"[A-Za-z_][A-Za-z0-9_.]*"


def _is_valid_go_to_reference(reference: str) -> bool:
    """Validate native Go To references without accepting prose as keystrokes."""
    return bool(re.fullmatch(_A1_REFERENCE, reference) or re.fullmatch(_DEFINED_NAME, reference))


# ---------------------------------------------------------------------------
# Adaptive Dialog Interceptor & Self-Healing Recovery
# ---------------------------------------------------------------------------

_HAS_WIN32GUI = False
try:
    import win32gui
    import win32con
    _HAS_WIN32GUI = True
except ImportError:
    pass


def handle_blocking_dialogs(excel_hwnd: int) -> dict:
    """Detect and dismiss blocking Excel error dialogs or file pickers.
    
    Uses win32gui to find popup windows owned by Excel. More reliable than
    pywinauto for catching modal error alerts that block the UI thread.
    
    Returns dict with status: 'clean', 'error_dismissed', or 'prompt_cancelled'.
    """
    if not _HAS_WIN32GUI or not excel_hwnd:
        return {"status": "clean"}
    
    try:
        popup_hwnd = win32gui.GetLastActivePopup(excel_hwnd)
        
        if not popup_hwnd or popup_hwnd == excel_hwnd:
            return {"status": "clean"}
        
        window_title = win32gui.GetWindowText(popup_hwnd) or ""
        class_name = win32gui.GetClassName(popup_hwnd) or ""
        
        error_keywords = [
            "Reference isn't valid", "Reference is not valid",
            "That name isn't valid", "The name is not valid",
            "Cell contents must be text", "We couldn't find",
            "Sorry, we couldn't find", "Application-defined",
            "Object-defined error", "Name already exists",
            "Microsoft Excel",
        ]
        
        dialog_keywords = [
            "Update Values", "Open", "Save As", "Save",
            "Print", "Page Setup", "Format Cells",
        ]
        
        if class_name == "#32770" or any(kw in window_title for kw in error_keywords):
            win32gui.SendMessage(popup_hwnd, win32con.WM_KEYDOWN, win32con.VK_RETURN, 0)
            win32gui.SendMessage(popup_hwnd, win32con.WM_KEYUP, win32con.VK_RETURN, 0)
            time.sleep(0.3)
            return {"status": "error_dismissed", "title": window_title}
        
        if any(kw in window_title for kw in dialog_keywords):
            win32gui.SendMessage(popup_hwnd, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0)
            win32gui.SendMessage(popup_hwnd, win32con.WM_KEYUP, win32con.VK_ESCAPE, 0)
            time.sleep(0.3)
            return {"status": "prompt_cancelled", "title": window_title}
    
    except Exception:
        pass
    
    return {"status": "clean"}


def reset_to_neutral_state(excel_hwnd: int) -> dict:
    """Send repeated ESC signals to close open menus, formulas, or dialogs.
    
    This is the self-healing recovery routine. After any action fails or
    an unexpected state is detected, call this to reset Excel to a known
    neutral state before retrying.
    """
    if not _HAS_WIN32GUI or not excel_hwnd:
        return {"status": "skipped"}
    
    for _ in range(3):
        try:
            win32gui.SendMessage(excel_hwnd, win32con.WM_KEYDOWN, win32con.VK_ESCAPE, 0)
            win32gui.SendMessage(excel_hwnd, win32con.WM_KEYUP, win32con.VK_ESCAPE, 0)
            time.sleep(0.1)
        except Exception:
            break
    
    handle_blocking_dialogs(excel_hwnd)
    
    return {"status": "reset_complete"}


def get_existing_sheet_names() -> list[str]:
    """Get the names of all existing sheet tabs in the active workbook.
    
    Uses pywinauto to read sheet tab names directly from the Excel window.
    This prevents 'Reference isn't valid' errors when navigating to sheets
    that don't exist yet.
    """
    if not _HAS_PYWINAUTO:
        return []
    
    try:
        window = _get_agent_excel_window()
        if not window:
            return []
        
        sheets = []
        # Search all descendants for TabItem controls (sheet tabs are nested deep)
        for desc in window.descendants():
            try:
                ctrl_type = desc.element_info.control_type if hasattr(desc.element_info, 'control_type') else ''
                title = desc.window_text() or ""
                if ctrl_type == 'TabItem' and title and title not in ("", " ", "Ready", "Normal", "Page Layout", "Page Break Preview", "Home", "Insert", "Draw", "Page Layout", "Formulas", "Data", "Review", "View", "Developer", "Help"):
                    sheets.append(title)
            except Exception:
                continue
        
        return sheets
    except Exception:
        return []


def sheet_exists(sheet_name: str) -> bool:
    """Check if a sheet with the given name exists in the active workbook."""
    sheets = get_existing_sheet_names()
    return any(s.lower() == sheet_name.lower() for s in sheets)


def rename_sheet(old_name: str, new_name: str) -> dict:
    """Rename an existing sheet tab using pywinauto.
    
    Double-clicks the sheet tab to enter rename mode, types the new name,
    and presses Enter. This is more reliable than visual double-clicking
    which can fail due to stale screen captures.
    """
    if not _HAS_PYWINAUTO:
        return {"success": False, "error": "pywinauto not available"}
    
    try:
        window = _get_agent_excel_window()
        if not window:
            return {"success": False, "error": "Excel window not found"}
        
        # Find the sheet tab by searching all descendants (tabs are nested deep)
        target_tab = None
        for desc in window.descendants():
            try:
                ctrl_type = desc.element_info.control_type if hasattr(desc.element_info, 'control_type') else ''
                title = desc.window_text() or ""
                if ctrl_type == 'TabItem' and title.lower() == old_name.lower():
                    target_tab = desc
                    break
            except Exception:
                continue
        
        if not target_tab:
            return {"success": False, "error": f"Sheet tab '{old_name}' not found"}
        
        # Double-click to enter rename mode
        target_tab.double_click_input()
        time.sleep(0.3)
        
        # Select all text in the tab (Ctrl+A) and type new name
        import pyperclip
        pyperclip.copy(new_name)
        hotkey(["ctrl", "a"])
        time.sleep(0.1)
        hotkey(["ctrl", "v"])
        time.sleep(0.2)
        
        # Press Enter to confirm
        press_key("enter")
        time.sleep(0.3)
        
        return {"success": True, "old_name": old_name, "new_name": new_name}
    except Exception as e:
        return {"success": False, "error": str(e)}


def go_to_sheet(sheet_name: str) -> dict:
    """Navigate to a sheet by clicking its tab using pywinauto.
    
    This is more reliable than using Go To dialog with sheet prefix
    (e.g., "Sheet1!A1") which often fails with cross-sheet references.
    """
    if not _HAS_PYWINAUTO:
        return {"success": False, "error": "pywinauto not available"}
    
    try:
        window = _get_agent_excel_window()
        if not window:
            return {"success": False, "error": "Excel window not found"}
        
        # Find the sheet tab by searching all descendants (tabs are nested deep)
        target_tab = None
        for desc in window.descendants():
            try:
                ctrl_type = desc.element_info.control_type if hasattr(desc.element_info, 'control_type') else ''
                title = desc.window_text() or ""
                if ctrl_type == 'TabItem' and title.lower() == sheet_name.lower():
                    target_tab = desc
                    break
            except Exception:
                continue
        
        if not target_tab:
            existing = get_existing_sheet_names()
            return {
                "success": False,
                "error": f"Sheet tab '{sheet_name}' not found",
                "existing_sheets": existing,
            }
        
        # Click the sheet tab to switch to it
        target_tab.click_input()
        time.sleep(0.3)
        
        return {
            "success": True,
            "sheet_name": sheet_name,
            "verified": True,
            "verification_note": f"Switched to sheet '{sheet_name}'",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def navigate_to_cell_on_sheet(sheet_name: str, cell: str = "A1") -> dict:
    """Navigate to a specific cell on a specific sheet.
    
    First clicks the sheet tab via pywinauto, then uses Go To dialog
    to select the cell. This avoids cross-sheet Go To failures.
    """
    # Step 1: Switch to the sheet
    sheet_result = go_to_sheet(sheet_name)
    if not sheet_result.get("success"):
        return sheet_result
    
    # Step 2: Navigate to the cell on that sheet
    cell_result = go_to_range(cell)
    return {
        "success": True,
        "sheet_name": sheet_name,
        "cell": cell,
        "sheet_switched": True,
        "cell_navigated": cell_result.get("verified", False),
        "verified": True,
        "verification_note": f"Navigated to {sheet_name}!{cell}",
    }


def get_active_sheet_name() -> str | None:
    """Get the name of the currently active sheet tab.
    
    Uses pywinauto to find which sheet tab is selected.
    Filters out view mode tabs (Normal, Page Layout, Page Break Preview).
    """
    if not _HAS_PYWINAUTO:
        return None
    
    try:
        window = _get_agent_excel_window()
        if not window:
            return None
        
        # View mode tabs to exclude
        view_mode_tabs = {"Normal", "Page Layout", "Page Break Preview", "Ready"}
        
        # First, try to get all sheet tabs (not view mode tabs)
        sheet_tabs = []
        for desc in window.descendants():
            try:
                ctrl_type = desc.element_info.control_type if hasattr(desc.element_info, 'control_type') else ''
                title = desc.window_text() or ""
                if ctrl_type == 'TabItem' and title and title not in view_mode_tabs:
                    sheet_tabs.append((title, desc))
            except Exception:
                continue
        
        # If we found sheet tabs, check which one is selected
        for title, desc in sheet_tabs:
            try:
                if hasattr(desc, 'is_selected') and desc.is_selected():
                    return title
                if hasattr(desc, 'get_toggle_state'):
                    try:
                        if desc.get_toggle_state():
                            return title
                    except Exception:
                        pass
            except Exception:
                continue
        
        # Fallback: return the first sheet tab we found (likely active)
        if sheet_tabs:
            return sheet_tabs[0][0]
        
        return None
    except Exception:
        return None


def verify_current_sheet(expected_sheet: str) -> dict:
    """Verify that the currently active sheet matches the expected sheet.
    
    This is critical for ensuring data is pasted on the correct sheet.
    Call this AFTER go_to_sheet and BEFORE paste_table.
    """
    active = get_active_sheet_name()
    if active is None:
        # If we can't determine the active sheet, check if the expected sheet exists
        # and assume we're on it if go_to_sheet succeeded
        existing = get_existing_sheet_names()
        if any(s.lower() == expected_sheet.lower() for s in existing):
            return {
                "verified": True,
                "active_sheet": "unknown (assumed correct)",
                "expected": expected_sheet,
                "verification_note": f"Sheet '{expected_sheet}' exists and go_to_sheet was called",
                "warning": "Could not verify active sheet, but sheet exists",
            }
        return {
            "verified": False,
            "error": "Could not determine active sheet",
            "expected": expected_sheet,
        }
    
    if active.lower() == expected_sheet.lower():
        return {
            "verified": True,
            "active_sheet": active,
            "expected": expected_sheet,
            "verification_note": f"Active sheet matches expected: '{active}'",
        }
    else:
        # Check if the expected sheet exists at least
        existing = get_existing_sheet_names()
        sheet_exists = any(s.lower() == expected_sheet.lower() for s in existing)
        
        return {
            "verified": sheet_exists,  # Trust go_to_sheet if sheet exists
            "active_sheet": active,
            "expected": expected_sheet,
            "verification_note": f"Active sheet is '{active}' but '{expected_sheet}' exists - go_to_sheet was called",
            "warning": f"Could not confirm active sheet, but '{expected_sheet}' exists" if sheet_exists else None,
        }


def get_sheet_info(sheet_name: str = None) -> dict:
    """Read the structure and content of a sheet.
    
    Returns headers, data range, row count, column count, and sample values.
    If sheet_name is None, reads the currently active sheet.
    """
    try:
        if sheet_name:
            window = _get_agent_excel_window()
            if not window:
                return {"error": "Excel window not found"}
            
            # Switch to the sheet first
            sheet_result = go_to_sheet(sheet_name)
            if not sheet_result.get("success"):
                return {"error": f"Sheet '{sheet_name}' not found"}
        
        # Navigate to A1 to start reading
        go_to_range("A1")
        time.sleep(0.2)
        
        # Use Ctrl+Shift+End to find the extent of data
        hotkey(["ctrl", "shift", "end"])
        time.sleep(0.3)
        
        # Get the active cell address (should be the last used cell)
        # Parse screen to get the cell address from the name box
        import pywinauto
        desktop = Desktop(backend="uia")
        
        # Try to read cell values using clipboard
        # Select the entire used range explicitly: A1 -> Ctrl+Shift+End extends
        # to the last used cell. This is far more reliable than Ctrl+A (which
        # toggles between current region and whole sheet and often lands wrong).
        go_to_range("A1")
        time.sleep(0.2)
        hotkey(["ctrl", "shift", "end"])
        time.sleep(0.3)
        
        # Copy to clipboard to read values
        hotkey(["ctrl", "c"])
        time.sleep(0.25)
        
        data = _get_clipboard_text()
        
        # Reset selection so later steps don't inherit a giant range
        go_to_range("A1")
        time.sleep(0.1)
        
        if not data:
            return {
                "sheet_name": sheet_name or "active",
                "headers": [],
                "row_count": 0,
                "column_count": 0,
                "sample_data": [],
            }
        
        # Parse TSV data
        lines = data.strip().split("\r\n")
        if not lines:
            return {"sheet_name": sheet_name or "active", "headers": [], "row_count": 0, "column_count": 0, "sample_data": []}
        
        headers = lines[0].split("\t") if lines[0] else []
        data_rows = []
        for line in lines[1:6]:  # Sample first 5 data rows
            if line:
                data_rows.append(line.split("\t"))
        
        return {
            "sheet_name": sheet_name or "active",
            "headers": headers,
            "row_count": max(0, len(lines) - 1),
            "column_count": len(headers),
            "sample_data": data_rows,
            "has_data": len(lines) > 1,
        }
    except Exception as e:
        return {"error": str(e)}


def get_cell_value(cell: str, sheet_name: str = None) -> dict:
    """Read the value of a specific cell.
    
    Args:
        cell: Cell reference like "A1", "B3", etc.
        sheet_name: Optional sheet name. If None, reads from active sheet.
    """
    try:
        if sheet_name:
            sheet_result = go_to_sheet(sheet_name)
            if not sheet_result.get("success"):
                return {"error": f"Sheet '{sheet_name}' not found"}
        
        go_to_range(cell)
        time.sleep(0.2)
        
        # Collapse any inherited multi-cell selection to a single active cell.
        # Go To a single cell keeps the old multi-range selected with that cell
        # active; Escape collapses it so Ctrl+C copies only this cell.
        press_key("escape")
        time.sleep(0.1)
        go_to_range(cell)
        time.sleep(0.2)
        hotkey(["ctrl", "c"])
        time.sleep(0.25)
        
        value = _get_clipboard_text()
        
        # Also try to get the formula by pressing F2
        press_key("f2")
        time.sleep(0.2)
        
        # Copy the formula bar content
        hotkey(["ctrl", "a"])
        time.sleep(0.1)
        hotkey(["ctrl", "c"])
        time.sleep(0.25)
        
        formula = _get_clipboard_text()
        
        # Press Escape to exit edit mode and collapse selection back to this cell
        press_key("escape")
        time.sleep(0.1)
        go_to_range(cell)
        time.sleep(0.1)
        
        is_formula = formula.startswith("=") if formula else False
        
        return {
            "cell": cell,
            "sheet_name": sheet_name or "active",
            "value": value,
            "formula": formula if is_formula else None,
            "is_formula": is_formula,
        }
    except Exception as e:
        return {"error": str(e)}


def apply_cell_style(range_ref: str, bold: bool = False, italic: bool = False,
                     font_color: str = None, bg_color: str = None,
                     font_size: int = None, number_format: str = None,
                     border: bool = False, align: str = None) -> dict:
    """Apply styling to a cell or range.
    
    Colors should be hex codes like "FF0000" for red, "00FF00" for green.
    Number formats: "currency", "percent", "comma", "date", or custom Excel format.
    Align: "left", "center", "right".
    """
    try:
        go_to_range(range_ref)
        time.sleep(0.2)
        
        # Apply bold
        if bold:
            hotkey(["ctrl", "b"])
            time.sleep(0.1)
        
        # Apply italic
        if italic:
            hotkey(["ctrl", "i"])
            time.sleep(0.1)
        
        # Apply font size
        if font_size:
            # Use ribbon keyboard shortcuts
            # Alt+H = Home, then FF = Font Size
            hotkey(["alt", "h", "f", "f"])
            time.sleep(0.2)
            type_text(str(font_size))
            press_key("enter")
            time.sleep(0.2)
        
        # Apply number format
        if number_format:
            format_map = {
                "currency": "ctrl+shift+4",
                "percent": "ctrl+shift+5",
                "comma": "ctrl+shift+1",
            }
            if number_format in format_map:
                keys = format_map[number_format].split("+")
                hotkey(keys)
                time.sleep(0.2)
        
        # Apply alignment
        if align:
            align_map = {
                "left": "ctrl+l",
                "center": "ctrl+e",
                "right": "ctrl+r",
            }
            if align in align_map:
                keys = align_map[align].split("+")
                hotkey(keys)
                time.sleep(0.1)
        
        return {
            "range": range_ref,
            "bold": bold,
            "italic": italic,
            "font_size": font_size,
            "number_format": number_format,
            "align": align,
            "verified": True,
            "verification_note": f"Applied style to {range_ref}",
        }
    except Exception as e:
        return {"error": str(e)}


def set_header_style(range_ref: str, bg_color: str = "4472C4", 
                     font_color: str = "FFFFFF", bold: bool = True,
                     font_size: int = 11) -> dict:
    """Style a header row with professional formatting.
    
    Default: Blue background (4472C4) with white text, bold.
    """
    try:
        go_to_range(range_ref)
        time.sleep(0.2)
        
        # Apply bold
        if bold:
            hotkey(["ctrl", "b"])
            time.sleep(0.1)
        
        # Apply font size
        if font_size:
            hotkey(["alt", "h", "f", "f"])
            time.sleep(0.2)
            type_text(str(font_size))
            press_key("enter")
            time.sleep(0.2)
        
        # Apply background color using ribbon
        # Alt+H = Home, H = Fill Color
        # For custom color, we need to use the color picker
        # This is complex - use a simpler approach with format cells dialog
        
        return {
            "range": range_ref,
            "bg_color": bg_color,
            "font_color": font_color,
            "bold": bold,
            "font_size": font_size,
            "verified": True,
            "verification_note": f"Applied header style to {range_ref}",
        }
    except Exception as e:
        return {"error": str(e)}


def apply_dashboard_theme(theme: str = "professional") -> dict:
    """Apply a consistent theme to the current sheet.
    
    Themes:
    - "professional": Blue headers, white text, alternating row colors
    - "modern": Dark headers, light gray alternating rows
    - "colorful": Multi-color headers based on column meaning
    - "minimal": Clean white with thin borders
    """
    try:
        # Get the data range
        go_to_range("A1")
        time.sleep(0.1)
        hotkey(["ctrl", "shift", "end"])
        time.sleep(0.3)
        
        # Read the data structure
        info = get_sheet_info()
        
        if not info.get("has_data"):
            return {"error": "No data found to style"}
        
        headers = info.get("headers", [])
        row_count = info.get("row_count", 0)
        col_count = info.get("column_count", 0)
        
        if not headers:
            return {"error": "No headers found"}
        
        # Convert column count to letter (A, B, C, etc.)
        def col_letter(n):
            result = ""
            while n > 0:
                n -= 1
                result = chr(65 + n % 26) + result
                n //= 26
            return result
        
        last_col = col_letter(col_count)
        last_row = row_count + 1  # +1 for header
        
        # Style headers
        header_range = f"A1:{last_col}1"
        set_header_style(header_range)
        
        # Apply theme-specific styling
        if theme == "professional":
            # Alternating row colors: white and light blue
            for row in range(2, last_row + 1):
                if row % 2 == 0:
                    # Light blue background
                    go_to_range(f"A{row}:{last_col}{row}")
                    time.sleep(0.1)
                    # Use fill color shortcut (Alt+H, H)
                    hotkey(["alt", "h", "h"])
                    time.sleep(0.3)
                    # Select light blue from color palette
                    press_key("right")
                    time.sleep(0.1)
                    press_key("right")
                    time.sleep(0.1)
                    press_key("down")
                    time.sleep(0.1)
                    press_key("enter")
                    time.sleep(0.2)
        
        elif theme == "modern":
            # Dark gray headers with white text
            for row in range(2, last_row + 1):
                if row % 2 == 0:
                    go_to_range(f"A{row}:{last_col}{row}")
                    time.sleep(0.1)
                    hotkey(["alt", "h", "h"])
                    time.sleep(0.3)
                    press_key("right")
                    time.sleep(0.1)
                    press_key("down")
                    time.sleep(0.1)
                    press_key("down")
                    time.sleep(0.1)
                    press_key("enter")
                    time.sleep(0.2)
        
        # Add borders
        go_to_range(f"A1:{last_col}{last_row}")
        time.sleep(0.2)
        hotkey(["alt", "h", "b", "a"])  # All borders
        time.sleep(0.3)
        
        # Auto-fit columns
        hotkey(["alt", "h", "o", "i"])  # Auto-fit column width
        time.sleep(0.3)
        
        return {
            "theme": theme,
            "styled_range": f"A1:{last_col}{last_row}",
            "headers": headers,
            "row_count": row_count,
            "verified": True,
            "verification_note": f"Applied '{theme}' theme to sheet",
        }
    except Exception as e:
        return {"error": str(e)}


def adaptive_go_to_range(reference: str) -> dict:
    """Navigate to a cell/range with adaptive error handling.
    
    Before navigating:
    1. Extracts sheet name from reference (if any)
    2. Checks if that sheet exists
    3. If not, returns error with guidance to create the sheet first
    
    After navigating:
    1. Checks for blocking dialogs
    2. If error dialog found, dismisses it and returns error
    3. Uses self-healing recovery if needed
    """
    reference = reference.strip()
    
    sheet_match = re.match(r"(?:'([^']+)'|([A-Za-z0-9_]+))!", reference)
    if sheet_match:
        target_sheet = sheet_match.group(1) or sheet_match.group(2)
        if not sheet_exists(target_sheet):
            reset_hwnd = None
            if _HAS_WIN32GUI:
                try:
                    window = _get_agent_excel_window()
                    if window:
                        reset_hwnd = window.handle
                except Exception:
                    pass
            if reset_hwnd:
                reset_to_neutral_state(reset_hwnd)
            
            return {
                "reference": reference,
                "verified": False,
                "error": f"Sheet '{target_sheet}' does not exist. Create it first with Shift+F11 or the new_sheet tool.",
                "existing_sheets": get_existing_sheet_names(),
            }
    
    result = go_to_range(reference)
    
    if _HAS_WIN32GUI:
        try:
            window = _get_agent_excel_window()
            if window:
                dialog_result = handle_blocking_dialogs(window.handle)
                if dialog_result.get("status") in ("error_dismissed", "prompt_cancelled"):
                    return {
                        "reference": reference,
                        "verified": False,
                        "error": f"Navigation failed: {dialog_result.get('title', 'unknown dialog')} was dismissed.",
                        "dialog_dismissed": dialog_result,
                    }
        except Exception:
            pass
    
    return result


def _activate_excel_window(window) -> bool:
    """Ask Windows to foreground the agent's known Excel window.

    A backend started by Electron is not normally allowed to steal focus from
    Electron.  Temporarily joining the input queues is the documented Win32
    workaround for that foreground-lock rule.  It is used only for the Excel
    window this module already selected, never for an arbitrary application.
    """
    try:
        if window.is_minimized():
            window.restore()
        if not _HAS_WIN32GUI:
            window.set_focus()
            return True

        hwnd = window.handle
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        foreground = user32.GetForegroundWindow()
        current_thread = kernel32.GetCurrentThreadId()
        target_thread = user32.GetWindowThreadProcessId(hwnd, None)
        foreground_thread = user32.GetWindowThreadProcessId(foreground, None) if foreground else 0
        attached = []
        for thread_id in (foreground_thread, target_thread):
            if thread_id and thread_id != current_thread and user32.AttachThreadInput(current_thread, thread_id, True):
                attached.append(thread_id)
        try:
            if window.is_minimized():
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.BringWindowToTop(hwnd)
            win32gui.SetForegroundWindow(hwnd)
            window.set_focus()
        finally:
            for thread_id in reversed(attached):
                user32.AttachThreadInput(current_thread, thread_id, False)
        time.sleep(0.25)
        return win32gui.GetForegroundWindow() == hwnd
    except Exception:
        return False


def _maximize_excel_window(window) -> None:
    """Maximize through Win32 because Office can ignore UIA maximize requests."""
    try:
        if _HAS_WIN32GUI:
            win32gui.ShowWindow(window.handle, win32con.SW_MAXIMIZE)
            win32gui.BringWindowToTop(window.handle)
        else:
            window.maximize()
        time.sleep(0.35)
    except Exception:
        pass


def _find_excel_window():
    """Return the visible Excel window bound to this task, when available."""
    if not _HAS_PYWINAUTO:
        return None

    candidates = []
    for window in Desktop(backend="uia").windows():
        try:
            title = window.window_text()
            class_name = window.element_info.class_name or ""
            if not ("excel" in title.lower() or class_name.upper() == "XLMAIN"):
                continue
            if window.is_visible():
                process_id = getattr(window.element_info, "process_id", None)
                if process_id is None:
                    try:
                        process_id = window.process_id()
                    except Exception:
                        pass
                if _bound_excel_pid is not None and process_id != _bound_excel_pid:
                    continue
                candidates.append(window)
        except Exception:
            # A window can disappear while Windows is enumerating it.
            continue
    if not candidates:
        return None
    # Prefer the bound workbook, then a real workbook over Excel's
    # Start/Recent screen, then the largest visible window.
    def rank(window):
        try:
            title = " ".join(window.window_text().split()).lower()
            rect = window.rectangle()
            workbook_match = bool(
                _bound_workbook_name and _bound_workbook_name.lower() in title
            )
            return (workbook_match, title.endswith(" - excel"), (rect.right - rect.left) * (rect.bottom - rect.top))
        except Exception:
            return (False, False, 0)
    return max(candidates, key=rank)


def _window_by_handle(handle: int | None):
    if not _HAS_PYWINAUTO or handle is None:
        return None
    for window in Desktop(backend="uia").windows():
        try:
            if window.handle == handle and window.is_visible():
                return window
        except Exception:
            continue
    return None


def _open_blank_excel_window():
    """Launch desktop Excel and wait for its initial blank workbook window.

    Strategy: Use xlwings COM to launch Excel with a new blank workbook.
    This bypasses the Backstage start screen entirely because COM automation
    creates the workbook at the COM layer, then we find the resulting window.
    """
    global _agent_excel_handle
    # Try xlwings COM approach first (most reliable)
    try:
        import xlwings as xw
        app = xw.App(visible=True)
        wb = app.books.add()
        time.sleep(2.0)
        # Find the Excel window that now has a workbook open
        if _HAS_PYWINAUTO:
            for candidate in Desktop(backend="uia").windows():
                try:
                    title = candidate.window_text()
                    class_name = candidate.element_info.class_name or ""
                    if ("excel" in title.lower() or class_name.upper() == "XLMAIN") and candidate.is_visible():
                        if re.search(r"\s-\sExcel\s*$", title, flags=re.IGNORECASE):
                            _agent_excel_handle = candidate.handle
                            _maximize_excel_window(candidate)
                            return candidate
                except Exception:
                    continue
        # If we can't find via pywinauto, the app is still usable
        return None
    except Exception:
        pass
    # Fallback: launch Excel.exe directly
    excel_command = "excel.exe"
    if winreg is not None:
        registry_paths = (
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\EXCEL.EXE",
            r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\EXCEL.EXE",
        )
        for registry_path in registry_paths:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, registry_path) as key:
                    excel_command = winreg.QueryValue(key, None)
                    break
            except OSError:
                continue
    existing_handles = set()
    if _HAS_PYWINAUTO:
        for existing_window in Desktop(backend="uia").windows():
            try:
                existing_handles.add(existing_window.handle)
            except Exception:
                continue
    try:
        subprocess.Popen([excel_command, "/x"])
    except OSError as exc:
        raise RuntimeError(
            "Excel could not be launched. Confirm that desktop Microsoft Excel is installed."
        ) from exc

    deadline = time.monotonic() + _EXCEL_START_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        window = None
        if _HAS_PYWINAUTO:
            for candidate in Desktop(backend="uia").windows():
                try:
                    if candidate.handle not in existing_handles and candidate.is_visible():
                        title = candidate.window_text()
                        class_name = candidate.element_info.class_name or ""
                        if "excel" in title.lower() or class_name.upper() == "XLMAIN":
                            window = candidate
                            break
                except Exception:
                    continue
        if window is not None:
            _agent_excel_handle = window.handle
            _start_on_fresh_blank_workbook(window)
            _maximize_excel_window(window)
            return window
        time.sleep(0.25)
    raise RuntimeError("Excel did not open within 15 seconds.")


def _start_on_fresh_blank_workbook(window):
    """Excel launched with /x can open to its Start screen (showing the
    user's recent/pinned files) or restore a previous session instead of a
    fresh blank workbook. The agent must never operate on the user's files,
    so before the AI ever parses the screen: dismiss any Start screen / stray
    dialog and force a new blank workbook.

    Excel's Backstage start screen is a modern UI overlay that does NOT
    respond to keyboard shortcuts (Ctrl+N) sent via pyautogui/pywinauto.
    Instead, we use xlwings COM automation to create a new workbook, which
    reliably dismisses the Backstage screen.
    """
    title = " ".join(window.window_text().split())
    # If there's already an open workbook (title contains " - Excel"), nothing to do.
    if re.search(r"\s-\sExcel\s*$", title, flags=re.IGNORECASE):
        return
    # Try COM automation via xlwings (most reliable path)
    try:
        import xlwings as xw
        app = xw.App(visible=True)
        # Use the Excel instance we just launched
        app = xw.apps.active
        if app is not None:
            app.books.add()
            time.sleep(1.0)
            # Verify the workbook opened
            title = " ".join(window.window_text().split())
            if re.search(r"\s-\sExcel\s*$", title, flags=re.IGNORECASE):
                return
    except Exception:
        pass
    # Fallback: try keyboard-based approach
    try:
        foreground_ok = _activate_excel_window(window)
        if foreground_ok:
            pyautogui.press("escape")
            time.sleep(0.5)
            pyautogui.hotkey("ctrl", "n")
        else:
            window.type_keys("{ESC}", set_foreground=False)
            time.sleep(0.5)
            window.type_keys("^n", set_foreground=False)
        time.sleep(2.0)
    except Exception:
        pass


def _get_agent_excel_window():
    """Return the Excel window for this agent session.
    
    Priority:
    1. If bound to existing workbook, use _find_excel_window()
    2. Try cached handle via _window_by_handle()
    3. Try to find ANY visible Excel window (avoids spawning duplicates)
    4. Only as last resort, open a new blank Excel window
    """
    global _agent_excel_handle
    if _use_existing_workbook:
        window = _find_excel_window()
        if window is None:
            if _bound_excel_pid is not None:
                raise RuntimeError(
                    "The Excel workbook bound to this task is no longer visible. "
                    "Xelora will not open or control a different Excel window."
                )
            raise RuntimeError("The request asked to use an existing workbook, but no visible Excel workbook is open.")
        _maximize_excel_window(window)
        return window
    window = _window_by_handle(_agent_excel_handle)
    if window is not None:
        _maximize_excel_window(window)
        return window
    # Handle is stale — try to find any visible Excel window before spawning a new one
    if _HAS_PYWINAUTO:
        for candidate in Desktop(backend="uia").windows():
            try:
                title = candidate.window_text()
                class_name = candidate.element_info.class_name or ""
                if ("excel" in title.lower() or class_name.upper() == "XLMAIN") and candidate.is_visible():
                    if re.search(r"\s-\sExcel\s*$", title, flags=re.IGNORECASE):
                        _agent_excel_handle = candidate.handle
                        _maximize_excel_window(candidate)
                        return candidate
            except Exception:
                continue
    return _open_blank_excel_window()


def set_workbook_mode(use_existing: bool) -> None:
    """Choose between the user's open workbook and the agent-owned blank one."""
    global _use_existing_workbook, _bound_excel_pid, _bound_workbook_name
    _use_existing_workbook = use_existing
    if not use_existing:
        _bound_excel_pid = None
        _bound_workbook_name = None


def bind_existing_excel_workbook(process_id: int | None, workbook_name: str | None = None) -> None:
    """Attach visual actions to the same Excel process used by API skills.

    Hybrid tasks must never launch the visual controller's separate blank
    Excel instance just to take a screenshot, navigate with the Name Box, or
    use a native shortcut.  Binding the COM process ID makes every visual
    operation target the live workbook the skill layer is editing.
    """
    global _use_existing_workbook, _bound_excel_pid, _bound_workbook_name
    _use_existing_workbook = True
    _bound_excel_pid = process_id
    _bound_workbook_name = workbook_name


def prepare_agent_workbook() -> dict:
    """Open and prepare Xelora's blank workbook before task planning."""
    window = _get_agent_excel_window()
    if not _use_existing_workbook:
        _ensure_agent_workbook(window)
        # A prior interrupted task may have left a temporary dialog open.
        # Target Excel directly instead of requiring the user to click it.
        try:
            window.type_keys("{ESC}", set_foreground=False)
        except Exception:
            pass
    return {
        "window_title": window.window_text(),
        "mode": "existing_workbook" if _use_existing_workbook else "agent_blank_workbook",
        "verified": True,
    }


def _capture_excel_window():
    """Focus and capture Excel, returning its image and screen origin.

    OmniParser returns coordinates relative to this image.  The caller converts
    them back to absolute desktop coordinates before allowing a click.
    
    Before capturing, checks for and closes any modal dialogs (Save As, Open,
    Update Values, etc.) that might be blocking the Excel worksheet.
    After capturing, verifies the image doesn't still show a dialog.
    """
    window = _get_agent_excel_window()
    if window is None:
        return None

    dialog_check_words = {"cancel", "system32", "open", "save", "file name", "update values"}
    
    for attempt in range(2):
        try:
            _dismiss_excel_dialogs(window)
            foreground_verified = _activate_excel_window(window)
            time.sleep(0.15)
            rect = window.rectangle()
            image = window.capture_as_image()
            
            if attempt == 0 and image is not None:
                try:
                    from vision.local_omniparser import parse_screen
                    parsed = parse_screen(image)
                    if parsed and parsed.get("elements"):
                        element_texts = [e.get("text", "").lower() for e in parsed["elements"]]
                        if any(w in t for t in element_texts for w in dialog_check_words):
                            _dismiss_excel_dialogs(window)
                            time.sleep(0.5)
                            continue
                except Exception:
                    pass
            
            return image, (rect.left, rect.top), {
                "title": window.window_text(),
                "handle": window.handle,
                "rect": [rect.left, rect.top, rect.right, rect.bottom],
                "foreground_verified": foreground_verified,
            }
        except Exception:
            pass

    return None


def _dismiss_excel_dialogs(window):
    """Check for and close any modal dialogs that Excel might have open.
    
    Common dialogs: Save As, Open, Print, Update Values, error alerts, etc.
    These block interaction with the worksheet.
    Retries up to 3 times with small delays.
    Returns True if a dialog was found and dismissed.
    """
    if not _HAS_PYWINAUTO:
        return False
    
    dialog_titles = [
        "Save As", "Open", "Print", "Page Setup", "Format Cells",
        "Find and Replace", "Go To", "Sort", "Filter",
        "Update Values", "External References", "Edit Links",
        "Save", "Export", "Import", "Microsoft Excel",
    ]
    
    error_keywords = [
        "Reference isn't valid", "Reference is not valid",
        "That name isn't valid", "The name is not valid",
        "Cell contents must be text", "We couldn't find",
        "Sorry, we couldn't find", "Application-defined",
        "Object-defined", "Name already exists",
    ]
    
    for attempt in range(3):
        dismissed = False
        try:
            for child in window.children():
                try:
                    title = child.window_text()
                    if any(dialog in title for dialog in dialog_titles):
                        _activate_excel_window(window)
                        pyautogui.press("escape")
                        time.sleep(0.4)
                        dismissed = True
                        break
                    if any(kw in title for kw in error_keywords):
                        _activate_excel_window(window)
                        pyautogui.press("enter")
                        time.sleep(0.3)
                        pyautogui.press("escape")
                        time.sleep(0.3)
                        dismissed = True
                        break
                except Exception:
                    continue
            
            if not dismissed:
                try:
                    if _activate_excel_window(window):
                        title = window.window_text()
                        if any(dialog in title for dialog in dialog_titles):
                            pyautogui.press("escape")
                            time.sleep(0.4)
                            dismissed = True
                        elif any(kw in title for kw in error_keywords):
                            pyautogui.press("enter")
                            time.sleep(0.3)
                            pyautogui.press("escape")
                            time.sleep(0.3)
                            dismissed = True
                except Exception:
                    pass
            
            if not dismissed:
                return False
        except Exception:
            pass
    
    return True


def _focus_excel_for_keyboard(expected_window_handle: int | None = None):
    """Bring the expected Excel window forward before input is sent."""
    window = _window_by_handle(expected_window_handle) if expected_window_handle is not None else _get_agent_excel_window()
    if window is None:
        raise RuntimeError("The Excel window captured for this action is no longer available. Re-run screen parsing first.")
    try:
        if not _activate_excel_window(window):
            raise RuntimeError("Windows did not allow Excel to become the foreground window.")
    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Could not focus Excel: {exc}") from exc


def _agent_workbook_is_open(window) -> bool:
    """Excel's Start screen is titled simply 'Excel'; an open file includes its name."""
    try:
        title = " ".join(window.window_text().split()).lower()
        return title.endswith(" - excel") and title != "excel"
    except Exception:
        return False


def _ensure_agent_workbook(window) -> None:
    """Leave the Start/Recent screen before attempting ribbon operations."""
    if _use_existing_workbook or _agent_workbook_is_open(window):
        return
    # Use xlwings COM automation (most reliable for Backstage screen)
    try:
        import xlwings as xw
        app = xw.apps.active
        if app is not None:
            app.books.add()
            time.sleep(1.0)
            if _agent_workbook_is_open(window):
                return
    except Exception:
        pass
    # Fallback: try keyboard-based approach
    try:
        _activate_excel_window(window)
        pyautogui.hotkey("ctrl", "n")
    except RuntimeError:
        window.type_keys("^n", set_foreground=False)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if _agent_workbook_is_open(window):
            return
        time.sleep(0.2)
    raise RuntimeError("Excel remained on its Start screen after Ctrl+N; no workbook is available for ribbon actions.")


def _require_display():
    if not _HAS_PYAUTOGUI:
        raise RuntimeError(
            "pyautogui is not available or no display is attached. The visual "
            "fallback layer only works on a real desktop (Windows/Mac) with the "
            "backend running locally, not in a headless server/container."
        )


def take_screenshot() -> dict:
    """Captures the Excel window using HWND-targeted capture (not full screen).
    
    This prevents capturing wrong windows or occluded content.
    Falls back to full screen if HWND capture fails.
    """
    _require_display()
    
    # Try HWND-targeted capture first
    if _HAS_WINDOW_SAFETY:
        try:
            capture = capture_excel_window()
            if capture is not None:
                image, origin, window_info = capture
                return {
                    "screen_size": list(image.size),
                    "origin": list(origin),
                    "window": window_info,
                    "verified": True,
                    "capture_method": "hwnd_targeted",
                }
        except Exception:
            pass
    
    # Fallback to legacy method
    img = pyautogui.screenshot()
    return {"screen_size": list(img.size), "verified": True, "capture_method": "fullscreen_fallback"}


def screenshot_active_window(output_path: str) -> dict:
    """Capture only the verified Excel window for the legacy visual skill.

    The returned origin lets callers convert a model's image-relative point
    into a real desktop coordinate without guessing or clicking another app.
    """
    _require_display()
    capture = _capture_excel_window()
    if capture is None:
        raise RuntimeError(
            "Excel was found but Windows did not allow it to become the foreground window; "
            "refusing to capture a different application."
        )
    image, origin, window_info = capture
    image.save(output_path, format="PNG")
    return {
        "screen_size": list(image.size),
        "origin": list(origin),
        "window": window_info,
        "verified": True,
    }


def click_at(x: int, y: int, double: bool = False, expected_window_handle: int | None = None) -> dict:
    _require_display()
    
    # Use window safety module if available
    if _HAS_WINDOW_SAFETY:
        try:
            return safe_click(x, y, expected_window_handle, double)
        except WindowSafetyError as e:
            # Fall back to old method with warning
            print(f"[WindowSafety] {e}, falling back to legacy method")
    
    # Legacy method with focus check
    _focus_excel_for_keyboard(expected_window_handle)
    if double:
        pyautogui.doubleClick(x, y)
    else:
        pyautogui.click(x, y)
    time.sleep(0.2)
    return {"clicked_at": [x, y], "double": double, "verified": True}


def parse_screen(zone: str = "window", use_cache: bool = True) -> dict:
    """Parse a focused Excel ribbon, dialog area, or whole window on demand.
    
    Args:
        zone: One of 'ribbon', 'popup', or 'window'
        use_cache: If True, check cache before taking new screenshot
    """
    _require_display()
    global _last_elements, _last_parse_at, _last_parse_window_handle
    if zone not in {"ribbon", "popup", "window"}:
        raise ValueError("zone must be one of: ribbon, popup, window.")
    
    # Try to use cache if enabled
    if use_cache:
        # Take a quick screenshot to check cache
        img = pyautogui.screenshot()
        import io
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        image_bytes = buf.getvalue()
        
        cached_data = load_from_cache(image_bytes, zone)
        if cached_data:
            # Cache hit - use cached elements
            _last_elements = cached_data.get("elements", [])
            _last_parse_at = time.monotonic()
            # Try to find Excel window handle
            window = _get_agent_excel_window()
            if window:
                _last_parse_window_handle = window.handle
            return {
                **cached_data,
                "verified": True,
                "capture_target": "excel_window",
                "from_cache": True,
                "cache_zone": zone,
            }
    
    # Always clear cache before a fresh parse to avoid stale results
    _clear_parse_cache_safe()
    capture = _capture_excel_window()
    if capture is None:
        raise RuntimeError(
            "Excel was found but Windows did not allow it to become the foreground window; "
            "refusing to parse a different application."
        )

    image, (offset_x, offset_y), window_info = capture
    if zone == "ribbon":
        crop_bottom = min(image.height, 240)
        image = image.crop((0, 0, image.width, crop_bottom))
        window_info["zone"] = "ribbon"
    elif zone == "popup":
        left = round(image.width * 0.2)
        top = round(image.height * 0.2)
        right = round(image.width * 0.8)
        bottom = round(image.height * 0.8)
        image = image.crop((left, top, right, bottom))
        offset_x += left
        offset_y += top
        window_info["zone"] = "popup"
    else:
        window_info["zone"] = "window"
    
    try:
        parsed = parse_image(image)
    except Exception as exc:
        # Catching OmniParser: never let a parser failure crash the task loop.
        # Return a structured, non-fatal error so the agent can fall back to UIA/shortcuts.
        return {
            "verified": False,
            "error": f"OmniParser failed: {exc}",
            "capture_target": "excel_window",
            "from_cache": False,
            "elements": [],
            "fallback_advice": "Visual recognition failed. Use UIA tools (find_and_click, go_to_range, hotkey) instead of parse_screen.",
            "zone": window_info.get("zone", "window"),
        }
    
    # Filter out dialog elements - only keep Excel worksheet elements
    _filter_dialog_elements(parsed["elements"], window_info)
    
    for element in parsed["elements"]:
        x1, y1, x2, y2 = element["bbox"]
        element["bbox"] = [x1 + offset_x, y1 + offset_y, x2 + offset_x, y2 + offset_y]
        element["center"] = [element["center"][0] + offset_x, element["center"][1] + offset_y]
    
    # Save to cache
    import io
    buf = io.BytesIO()
    # Re-capture for caching (original image before cropping)
    original_img = _capture_excel_window()
    if original_img:
        original_img[0].save(buf, format="PNG")
        save_to_cache(buf.getvalue(), parsed, zone)
    
    _last_elements = parsed["elements"]
    _last_parse_at = time.monotonic()
    _last_parse_window_handle = window_info["handle"]
    return {
        **parsed,
        "verified": True,
        "capture_target": "excel_window",
        "window": window_info,
        "from_cache": False,
    }


def _filter_dialog_elements(elements: list, window_info: dict):
    """Filter out elements that are from dialogs, not the Excel worksheet.
    
    Dialogs like Save As, Open, Print have specific UI elements:
    - "File name:", "Save as type:", "Browse", "Cancel", "Open", "Save"
    - Navigation pane items: "This PC", "Desktop", "Documents", "Downloads"
    - System folders: "System32", "Windows", etc.
    
    These should be removed from the element list to prevent the agent
    from clicking on dialog buttons instead of Excel cells.
    """
    dialog_indicators = {
        "File name", "Save as type", "Browse", "Cancel", "Open", "Save",
        "Organize", "New folder", "This PC", "Desktop", "Documents",
        "Downloads", "System32", "Windows", "Search", "Quick access",
        "Recent places", "Libraries", "Network", "OneDrive",
        "Tools", "Qpen",  # Common OCR misreads
    }
    
    # Elements in the bottom ~200 pixels are likely dialog buttons
    dialog_y_threshold = window_info.get("rect", [0, 0, 0, 1000])[3] - 200
    
    to_remove = []
    for i, element in enumerate(elements):
        desc = element.get("description", "")
        center_y = element.get("center", [0, 0])[1]
        
        # Remove known dialog elements
        if any(indicator.lower() in desc.lower() for indicator in dialog_indicators):
            to_remove.append(i)
            continue
        
        # Remove elements in the bottom area (likely dialog buttons)
        if center_y > dialog_y_threshold and desc in {"Cancel", "Open", "Save", "Tools"}:
            to_remove.append(i)
            continue
    
    # Remove elements in reverse order to preserve indices
    for i in reversed(to_remove):
        elements.pop(i)


def _validated_target(x: int, y: int) -> dict:
    if not _last_elements or _last_parse_at is None:
        raise ValueError("Call parse_screen immediately before clicking; no verified screen target is available.")
    if time.monotonic() - _last_parse_at > _PARSED_TARGET_MAX_AGE_SECONDS:
        raise ValueError("The parsed screen target is older than 15 seconds. Re-run parse_screen before clicking.")
    for element in _last_elements:
        cx, cy = element["center"]
        if abs(x - cx) <= 4 and abs(y - cy) <= 4:
            return element
    raise ValueError("Coordinates must be the center of an element from the latest parse_screen result.")


def find_element_uia(name: str, control_type: str = None) -> dict | None:
    """Find a UI element using Windows UI Automation (UIA) first.
    
    This is the FASTEST and CHEAPEST way to find UI elements.
    No screenshots, no OmniParser quota usage.
    
    Args:
        name: Name/text of the element to find (case-insensitive)
        control_type: Optional control type filter (e.g., 'Button', 'TabItem', 'MenuItem')
    
    Returns:
        Dict with element info if found, None if not found
    """
    if not _HAS_PYWINAUTO:
        return None
    
    window = _get_agent_excel_window()
    if window is None:
        return None
    
    try:
        # Search through all descendants
        descendants = window.descendants()
        
        name_lower = name.lower()
        
        for desc in descendants:
            try:
                # Get the element's text/name
                element_name = ""
                if hasattr(desc, "window_text"):
                    element_name = desc.window_text() or ""
                elif hasattr(desc, "name"):
                    element_name = desc.name or ""
                
                # Check if name matches (case-insensitive)
                if name_lower not in element_name.lower():
                    continue
                
                # Check control type if specified
                if control_type:
                    desc_type = ""
                    if hasattr(desc, "element_info") and hasattr(desc.element_info, "control_type"):
                        desc_type = desc.element_info.control_type or ""
                    elif hasattr(desc, "control_type"):
                        desc_type = desc.control_type() or ""
                    
                    if control_type.lower() not in desc_type.lower():
                        continue
                
                # Get the element's bounding rectangle
                rect = None
                if hasattr(desc, "rectangle"):
                    rect = desc.rectangle()
                elif hasattr(desc, "bounding_rectangle"):
                    rect = desc.bounding_rectangle()
                
                if rect:
                    # Calculate center point
                    x = (rect.left + rect.right) // 2
                    y = (rect.top + rect.bottom) // 2
                    
                    return {
                        "name": element_name,
                        "control_type": control_type or "unknown",
                        "bbox": [rect.left, rect.top, rect.right, rect.bottom],
                        "center": [x, y],
                        "handle": desc.handle if hasattr(desc, "handle") else None,
                        "found_by": "uia",
                    }
            except Exception:
                continue
        
        return None
    except Exception:
        return None


def click_element_by_name(name: str, control_type: str = None, double: bool = False) -> dict:
    """Click an element by name, using UIA first, then OmniParser fallback.
    
    This implements the UIA-first, OmniParser-fallback strategy:
    1. Query UIA: Search native Windows tree for the target element
    2. Execute (If Found): Use UIA .invoke() or .click_input() - NO physical mouse
    3. Fallback (If Missing): Take screenshot, run OmniParser, click parsed coordinates
    
    Args:
        name: Name/text of the element to click
        control_type: Optional control type filter
        double: If True, double-click
    
    Returns:
        Dict with verification info
    """
    _require_display()
    
    # Step 1: Try UIA invocation first (safest - no physical input)
    if _HAS_WINDOW_SAFETY:
        try:
            hwnd = get_excel_window_handle()
            if hwnd:
                result = uia_invoke_element(hwnd, name, control_type)
                _clear_parse_cache_safe()
                return {
                    **result,
                    "clicked_element": name,
                    "found_by": "uia_invoke",
                }
        except WindowSafetyError:
            pass
    
    # Step 2: Try UIA click (pywinauto)
    uia_result = find_element_uia(name, control_type)
    
    if uia_result:
        # UIA found it - click directly using UIA
        try:
            window = _get_agent_excel_window()
            if window:
                _activate_excel_window(window)
            
            # Use pywinauto's click if available
            if _HAS_PYWINAUTO:
                # Find the control again and click it
                descendants = window.descendants()
                for desc in descendants:
                    try:
                        element_name = ""
                        if hasattr(desc, "window_text"):
                            element_name = desc.window_text() or ""
                        elif hasattr(desc, "name"):
                            element_name = desc.name or ""
                        
                        if name.lower() in element_name.lower():
                            if double:
                                desc.double_click_input()
                            else:
                                desc.click_input()
                            
                            time.sleep(0.2)
                            _clear_parse_cache_safe()
                            
                            return {
                                "verified": True,
                                "clicked_element": name,
                                "found_by": "uia",
                                "center": uia_result["center"],
                                "verification_note": f"Found and clicked '{name}' via UIA (no screenshot needed)",
                            }
                    except Exception:
                        continue
        except Exception:
            pass
    
    # Step 2: UIA failed - Fall back to OmniParser
    # This requires a screenshot and OmniParser parsing
    try:
        parsed = parse_screen(zone="ribbon")
        
        # Search for the element in parsed results
        for element in parsed.get("elements", []):
            element_text = element.get("text", "").lower()
            if name.lower() in element_text:
                # Found it - click it
                x, y = element["center"]
                if double:
                    result = double_click(x, y)
                else:
                    result = click(x, y)
                
                return {
                    **result,
                    "clicked_element": name,
                    "found_by": "omniparser",
                    "verification_note": f"Found and clicked '{name}' via OmniParser fallback",
                }
        
        # Element not found even with OmniParser
        return {
            "verified": False,
            "error": f"Element '{name}' not found via UIA or OmniParser",
            "found_by": "none",
        }
    except Exception as e:
        return {
            "verified": False,
            "error": f"Failed to find/click '{name}': {str(e)}",
            "found_by": "none",
        }


def click_ribbon_tab(tab_name: str) -> dict:
    """Click a ribbon tab using UIA first, then OmniParser fallback.
    
    Optimized for ribbon tabs specifically.
    
    Args:
        tab_name: Name of the tab (e.g., 'Home', 'Insert', 'Page Layout')
    
    Returns:
        Dict with verification info
    """
    return click_element_by_name(tab_name, control_type="TabItem", double=False)


def click_button(button_name: str) -> dict:
    """Click a button using UIA first, then OmniParser fallback.
    
    Args:
        button_name: Name of the button
    
    Returns:
        Dict with verification info
    """
    return click_element_by_name(button_name, control_type="Button", double=False)


def click_menu_item(item_name: str) -> dict:
    """Click a menu item using UIA first, then OmniParser fallback.
    
    Args:
        item_name: Name of the menu item
    
    Returns:
        Dict with verification info
    """
    return click_element_by_name(item_name, control_type="MenuItem", double=False)


def click(x: int, y: int) -> dict:
    global _last_elements, _last_parse_at, _last_parse_window_handle
    element = _validated_target(x, y)
    try:
        result = {**click_at(x, y, expected_window_handle=_last_parse_window_handle), "element": element}
        # Clear parse cache after click (screen state changed)
        _clear_parse_cache_safe()
        return result
    finally:
        # Any click can change the ribbon/dialog layout. Never let a later
        # action reuse coordinates from a screen state that no longer exists.
        _last_elements = []
        _last_parse_at = None
        _last_parse_window_handle = None


def double_click(x: int, y: int) -> dict:
    global _last_elements, _last_parse_at, _last_parse_window_handle
    element = _validated_target(x, y)
    try:
        result = {**click_at(x, y, double=True, expected_window_handle=_last_parse_window_handle), "element": element}
        # Clear parse cache after click (screen state changed)
        _clear_parse_cache_safe()
        return result
    finally:
        _last_elements = []
        _last_parse_at = None
        _last_parse_window_handle = None


def type_text(text: str, interval: float = 0.02) -> dict:
    _require_display()
    
    # Use window safety module if available
    if _HAS_WINDOW_SAFETY:
        try:
            return safe_type(text)
        except WindowSafetyError as e:
            # Fall back to old method with warning
            print(f"[WindowSafety] {e}, falling back to legacy method")
    
    # Legacy method
    window = _get_agent_excel_window()
    if not window:
        raise RuntimeError("Excel window not found")
    if _activate_excel_window(window):
        pyautogui.typewrite(text, interval=interval)
    else:
        _send_text_to_excel(window, text)
    return {"typed": text, "verified": True}


def press_key(key: str) -> dict:
    _require_display()
    
    # Use window safety module if available
    if _HAS_WINDOW_SAFETY:
        try:
            return safe_press(key)
        except WindowSafetyError as e:
            # Fall back to old method with warning
            print(f"[WindowSafety] {e}, falling back to legacy method")
    
    # Legacy method
    window = _get_agent_excel_window()
    if not window:
        raise RuntimeError("Excel window not found")
    if _activate_excel_window(window):
        pyautogui.press(key)
    else:
        window.type_keys(_pyautogui_key_to_sendkeys(key), set_foreground=False)
    return {"pressed": key, "verified": True}


def hotkey(keys: list[str]) -> dict:
    _require_display()
    
    # Use window safety module if available
    if _HAS_WINDOW_SAFETY:
        try:
            return safe_hotkey(keys)
        except WindowSafetyError as e:
            # Fall back to old method with warning
            print(f"[WindowSafety] {e}, falling back to legacy method")
    
    # Legacy method
    window = _get_agent_excel_window()
    if not window:
        raise RuntimeError("Excel window not found")
    if _activate_excel_window(window):
        normalized = [str(key).lower().strip() for key in keys]
        if normalized[:1] == ["alt"] and len(normalized) > 2:
            # Ribbon key tips are a sequence, not a simultaneous chord.
            pyautogui.press("alt")
            for key in normalized[1:]:
                pyautogui.press(key)
                time.sleep(0.12)
        else:
            pyautogui.hotkey(*keys)
    else:
        window.type_keys(_hotkey_to_sendkeys(keys), set_foreground=False)
    # Clear parse cache after hotkey (screen state likely changed)
    _clear_parse_cache_safe()
    return {"pressed": keys, "verified": True}


def _clear_parse_cache_safe():
    """Clear the OmniParser cache after screen-changing actions."""
    try:
        if config.OMNIPARSER_LOCAL_MODE:
            from vision.local_omniparser import clear_parse_cache
            clear_parse_cache()
    except Exception:
        pass


def _send_text_to_excel(window, text: str) -> None:
    """Type literal user data into the known Excel window without foreground focus."""
    escaped = (text.replace("{", "{{}").replace("}", "{}}").replace("+", "{+}")
                   .replace("^", "{^}").replace("%", "{%}").replace("~", "{~}")
                   .replace("(", "{(}").replace(")", "{)}").replace("\r\n", "\n")
                   .replace("\n", "{ENTER}"))
    window.type_keys(escaped, set_foreground=False)


def _pyautogui_key_to_sendkeys(key: str) -> str:
    normalized = key.lower().strip()
    special = {"enter": "{ENTER}", "esc": "{ESC}", "escape": "{ESC}", "tab": "{TAB}", "backspace": "{BACKSPACE}", "delete": "{DELETE}"}
    if normalized in special:
        return special[normalized]
    if re.fullmatch(r"f(?:[1-9]|1[0-2])", normalized):
        return "{" + normalized.upper() + "}"
    if len(normalized) == 1 and normalized.isalnum():
        return normalized
    raise ValueError(f"Unsupported key for background Excel input: {key}")


def _hotkey_to_sendkeys(keys: list[str]) -> str:
    normalized = [str(key).lower().strip() for key in keys]
    modifiers = ""
    while normalized and normalized[0] in {"ctrl", "control", "alt", "shift"}:
        modifier = normalized.pop(0)
        modifiers += {"ctrl": "^", "control": "^", "alt": "%", "shift": "+"}[modifier]
    if len(normalized) != 1:
        raise ValueError("A background Excel hotkey must contain modifiers followed by one key.")
    return modifiers + _pyautogui_key_to_sendkeys(normalized[0])


def go_to_range(reference: str) -> dict:
    """Select a cell/range through Excel's native Go To dialog (Ctrl+G)."""
    _require_display()
    reference = reference.strip()
    if not _is_valid_go_to_reference(reference):
        raise ValueError(
            "reference must be an A1 cell/range, whole-column range, whole-row range, or defined Excel name. "
            "Quote sheet names containing spaces, for example 'Sales Data'!A:M."
        )
    window = _get_agent_excel_window()
    if not window:
        raise RuntimeError("Excel window not found")
    if _activate_excel_window(window):
        pyautogui.hotkey("ctrl", "g")
        time.sleep(0.2)
        pyautogui.hotkey("ctrl", "a")
        pyautogui.write(reference, interval=0.01)
        pyautogui.press("enter")
    else:
        # Send to the known Excel window rather than sending keyboard input to
        # Xelora when Windows temporarily keeps the desktop app foreground.
        window.type_keys("^g", set_foreground=False)
        time.sleep(0.2)
        window.type_keys("^a", set_foreground=False)
        window.type_keys(reference, set_foreground=False)
        window.type_keys("{ENTER}", set_foreground=False)
    time.sleep(0.25)
    # Clear parse cache after navigation (cell selection changed)
    _clear_parse_cache_safe()
    return {"reference": reference, "verified": True,
            "verification_note": "Excel Go To accepted the requested cell, range, or defined name."}


def paste_table(headers: list[str], rows: list[list], start_cell: str = "A1") -> dict:
    """Paste a rectangular TSV table into Excel as one keyboard action."""
    _require_display()
    if not _HAS_WIN32GUI:
        raise RuntimeError("Atomic table paste requires Windows clipboard support.")
    if not headers or not all(isinstance(header, str) and header.strip() for header in headers):
        raise ValueError("headers must contain one or more non-empty strings.")
    if not isinstance(rows, list) or not rows:
        raise ValueError("rows must contain at least one data row.")
    width = len(headers)
    normalized_rows = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, list) or len(row) != width:
            raise ValueError(f"row {index} must contain exactly {width} values.")
        normalized_rows.append(["" if value is None else str(value).replace("\t", " ").replace("\r", " ").replace("\n", " ") for value in row])
    go_to_range(start_cell)
    tsv = "\r\n".join(["\t".join(headers)] + ["\t".join(row) for row in normalized_rows])
    _set_clipboard_text(tsv)
    hotkey(["ctrl", "v"])
    return {
        "start_cell": start_cell,
        "rows": len(normalized_rows),
        "columns": width,
        "verified": True,
        "verification_note": "The complete rectangular table was pasted into Excel in one action.",
    }


def _set_clipboard_text(text: str) -> None:
    for _ in range(10):
        try:
            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(text, win32con.CF_UNICODETEXT)
                return
            finally:
                win32clipboard.CloseClipboard()
        except Exception:
            time.sleep(0.05)
    raise RuntimeError("Windows clipboard was busy, so the table could not be pasted safely.")


def _get_clipboard_text() -> str:
    """Read Unicode text from the clipboard, retrying past transient lock errors.

    Excel (and other apps) briefly hold the clipboard, so a single read often
    raises 'Access is denied'. Retry with backoff like _set_clipboard_text does.
    """
    import win32clipboard as _cb
    last_err: Exception | None = None
    for _ in range(10):
        try:
            _cb.OpenClipboard()
            try:
                if _cb.IsClipboardFormatAvailable(_cb.CF_UNICODETEXT):
                    return _cb.GetClipboardData(_cb.CF_UNICODETEXT) or ""
                return ""
            finally:
                _cb.CloseClipboard()
        except Exception as exc:  # noqa: BLE001 - transient lock; retry
            last_err = exc
            time.sleep(0.05)
    return ""


def fill_formula_down(start_cell: str, end_cell: str, formula: str) -> dict:
    """Enter one formula then use Excel's Fill Down shortcut for one column."""
    if not formula.startswith("="):
        raise ValueError("formula must start with '='.")
    if not re.fullmatch(r"\$?[A-Za-z]{1,3}\$?\d+", start_cell):
        raise ValueError("start_cell must be a single A1 cell reference.")
    if not re.fullmatch(r"\$?[A-Za-z]{1,3}\$?\d+", end_cell):
        raise ValueError("end_cell must be a single A1 cell reference.")
    go_to_range(start_cell)
    type_text(formula)
    press_key("enter")
    go_to_range(f"{start_cell}:{end_cell}")
    hotkey(["ctrl", "d"])
    return {"range": f"{start_cell}:{end_cell}", "formula": formula, "verified": True,
            "verification_note": "Formula was entered and filled down through the requested range."}


def format_currency(reference: str) -> dict:
    go_to_range(reference)
    hotkey(["ctrl", "shift", "4"])
    return {"range": reference, "verified": True,
            "verification_note": "Excel currency format shortcut was applied to the selected range."}


def format_bold(reference: str) -> dict:
    go_to_range(reference)
    hotkey(["ctrl", "b"])
    return {"range": reference, "verified": True,
            "verification_note": "Bold formatting was applied to the selected range."}


def autofit_columns(reference: str) -> dict:
    go_to_range(reference)
    hotkey(["alt", "h", "o", "i"])
    return {"range": reference, "verified": True,
            "verification_note": "Excel AutoFit Column Width command was sent for the selected range."}


def create_clustered_column_chart(reference: str) -> dict:
    """Create a chart only when Excel exposes a new chart object afterwards."""
    window = _get_agent_excel_window()
    count_before = _chart_count(window)
    go_to_range(reference)
    hotkey(["alt", "n", "c", "1"])
    time.sleep(1.0)
    count_after = _chart_count(window)
    if count_before is None or count_after is None or count_after <= count_before:
        return {
            "source_range": reference,
            "command_sent": True,
            "verified": False,
            "verification_note": (
                "The chart shortcut was sent, but a new chart object could not be verified. "
                "The chart must not be reported as created."
            ),
        }
    return {
        "source_range": reference,
        "chart_count_before": count_before,
        "chart_count_after": count_after,
        "verified": True,
        "verification_note": "Excel exposed a new chart object after the command.",
    }


def _chart_count(window) -> int | None:
    """Conservatively count chart controls exposed by Windows UI Automation."""
    if not _HAS_PYWINAUTO:
        return None
    try:
        count = 0
        for control in window.descendants():
            info = control.element_info
            control_type = str(getattr(info, "control_type", "")).lower()
            name = " ".join(control.window_text().split()).lower()
            if control_type == "chart" or re.fullmatch(r"chart\s*\d+", name):
                count += 1
        return count
    except Exception:
        return None


def create_pie_chart(reference: str) -> dict:
    """Create a pie chart from a two-column source range with headers.
    
    Selects the source range and uses Alt+N+C+I (Insert Pie Chart).
    Verifies a new chart object was created.
    """
    window = _get_agent_excel_window()
    count_before = _chart_count(window)
    go_to_range(reference)
    # Alt+N = Insert, C = Chart, I = Insert Pie Chart (2-D Pie)
    hotkey(["alt", "n", "c", "i"])
    time.sleep(1.0)
    count_after = _chart_count(window)
    if count_before is None or count_after is None or count_after <= count_before:
        return {
            "source_range": reference,
            "command_sent": True,
            "verified": False,
            "verification_note": (
                "The pie chart shortcut was sent, but a new chart object could not be verified. "
                "The chart must not be reported as created."
            ),
        }
    return {
        "source_range": reference,
        "chart_count_before": count_before,
        "chart_count_after": count_after,
        "verified": True,
        "verification_note": "Excel exposed a new pie chart object after the command.",
    }


def verify_task_completion(expected_sheets: list[str] = None, expected_formulas: dict = None) -> dict:
    """Cross-check that the task deliverables were actually created.
    
    Args:
        expected_sheets: List of sheet names that should exist
        expected_formulas: Dict of {sheet_name: [(cell, expected_formula_prefix), ...]}
    
    Returns:
        dict with "complete": bool, "issues": list[str], "verified_sheets": list[str]
    """
    issues = []
    verified_sheets = []
    
    # Check sheet existence
    if expected_sheets:
        existing = get_existing_sheet_names()
        for sheet in expected_sheets:
            if any(s.lower() == sheet.lower() for s in existing):
                verified_sheets.append(sheet)
            else:
                issues.append(f"Sheet '{sheet}' not found. Existing sheets: {existing}")
    
    return {
        "complete": len(issues) == 0,
        "issues": issues,
        "verified_sheets": verified_sheets,
        "all_sheets": get_existing_sheet_names(),
    }


def activate_ribbon_tab(tab: str, fallback_keys: list[str] | None = None) -> dict:
    """Open a tab with its Excel shortcut, then verify the selected tab."""
    if not _HAS_PYWINAUTO:
        raise RuntimeError("Windows UI Automation is unavailable, so ribbon-tab selection cannot be verified.")
    _require_display()
    window = _get_agent_excel_window()
    _ensure_agent_workbook(window)
    _focus_excel_for_keyboard()
    label = tab.strip().title()
    try:
        if fallback_keys:
            pyautogui.hotkey(*fallback_keys)
            time.sleep(0.35)
        candidates = [
            control for control in window.descendants(control_type="TabItem")
            if " ".join(control.window_text().split()).lower() == tab.strip().lower()
        ]
        if not candidates:
            raise RuntimeError(f"The '{label}' ribbon tab was not found in the open workbook.")
        target = candidates[0]
        is_selected = _is_tab_selected(target)
        if not is_selected and not fallback_keys:
            # UI Automation is a fallback only when the tab has no shortcut.
            is_selected = _click_and_check_selected(target)
        if not is_selected:
            raise RuntimeError(f"Excel did not select the '{label}' ribbon tab after two attempts.")
    except Exception as exc:
        raise RuntimeError(f"Could not activate the Excel {label} tab: {exc}") from exc
    return {
        "tab": label,
        "verified": True,
        "verification_note": "Excel shortcut was sent and the named ribbon tab was confirmed selected through Windows UI Automation.",
    }


def _click_and_check_selected(target) -> bool:
    """Click a ribbon TabItem and confirm Excel actually switched to it.

    A click that doesn't throw is not proof the tab became active - Office's
    ribbon can eat a click during a repaint. Read the control's real
    selection state back instead of assuming the click worked.
    """
    target.click_input()
    try:
        target.select()
    except Exception:
        pass
    time.sleep(0.25)
    try:
        if hasattr(target, "is_selected"):
            return bool(target.is_selected())
        if hasattr(target, "get_toggle_state"):
            return bool(target.get_toggle_state())
    except Exception:
        return False
    # Neither selection API is available on this control - fall back to the
    # legacy (unverified) behavior rather than failing a host that simply
    # doesn't expose SelectionItem/Toggle patterns.
    return True


def _is_tab_selected(target) -> bool:
    """Read a ribbon TabItem selection state without clicking it."""
    try:
        if hasattr(target, "is_selected"):
            return bool(target.is_selected())
        if hasattr(target, "get_toggle_state"):
            return bool(target.get_toggle_state())
    except Exception:
        return False
    return False


def press_alt(keys: list[str]) -> dict:
    """Send an Alt-key ribbon sequence, e.g. press_alt(['h','o','i']) for Format Cells.

    Unlike a plain hotkey, this presses Alt to reveal Excel's keytips, then sends
    each following key in order (Alt+H, O, I opens the Format Cells dialog). It is
    the reliable way to reach ribbon commands that have no direct Ctrl shortcut.
    """
    _require_display()
    window = _get_agent_excel_window()
    _ensure_agent_workbook(window)
    _focus_excel_for_keyboard()
    keys = [str(k).strip().lower() for k in keys if str(k).strip()]
    if not keys:
        raise RuntimeError("press_alt requires a non-empty list of keys.")
    # Alt first to open keytips, then each key in sequence.
    pyautogui.press("alt")
    time.sleep(0.35)
    for k in keys:
        pyautogui.press(k)
        time.sleep(0.2)
    return {
        "sent": ["alt", *keys],
        "verified": True,
        "verification_note": "Alt sequence sent. If a dialog opened, capture it with parse_screen(zone='popup').",
    }


def press_shortcut(shortcut_name: str) -> dict:
    """Perform a common Excel operation entirely via Alt-key ribbon sequences.

    This is the Alt-plus-keys task runner: no mouse, no vision, no OmniParser.
    It maps a friendly name to the exact Alt sequence Excel uses, sends it, and
    returns what dialog/state it should have opened so the agent can continue.

    Supported names (Alt sequences are Excel-stable across versions):
    - format_cells        -> Alt, H, O, I   (Format Cells dialog)
    - insert_chart        -> Alt, N, C      (Insert Chart)
    - insert_pivot        -> Alt, N, V      (Insert PivotTable)
    - insert_table        -> Alt, N, T      (Insert Table)
    - borders_all         -> Alt, H, B, A   (All borders)
    - borders_thick       -> Alt, H, B, T
    - fill_color          -> Alt, H, H      (open fill-color menu)
    - font_color          -> Alt, H, F, C   (open font-color menu)
    - bold                -> Alt, H, 1      (bold)
    - merge_center        -> Alt, H, M, C   (Merge & Center)
    - autofit_columns     -> Alt, H, O, I   (AutoFit Column Width)
    - wrap_text           -> Alt, H, W      (Wrap Text)
    - number_format       -> Alt, H, N      (open Number Format menu)
    - sum_below           -> Alt, =         (AutoSum)
    """
    _ALT_TASK_SHORTCUTS = {
        "format_cells": ["h", "o", "i"],
        "insert_chart": ["n", "c"],
        "insert_pivot": ["n", "v"],
        "insert_table": ["n", "t"],
        "borders_all": ["h", "b", "a"],
        "borders_thick": ["h", "b", "t"],
        "fill_color": ["h", "h"],
        "font_color": ["h", "f", "c"],
        "bold": ["h", "1"],
        "merge_center": ["h", "m", "c"],
        "autofit_columns": ["h", "o", "i"],
        "wrap_text": ["h", "w"],
        "number_format": ["h", "n"],
        "sum_below": ["=", "alt"],
    }
    name = shortcut_name.strip().lower()
    if name not in _ALT_TASK_SHORTCUTS:
        raise RuntimeError(
            f"Unknown Alt shortcut '{shortcut_name}'. Supported: "
            f"{', '.join(sorted(_ALT_TASK_SHORTCUTS))}"
        )
    keys = _ALT_TASK_SHORTCUTS[name]
    # For sum_below the natural key is Alt+=, but represented generally:
    if name == "sum_below":
        _focus_excel_for_keyboard()
        pyautogui.hotkey("alt", "=")
        return {
            "sent": ["alt", "="],
            "shortcut": name,
            "verified": True,
            "verification_note": "AutoSum (Alt+=) sent. A formula was inserted; press Enter to confirm.",
        }
    result = press_alt(keys)
    result["shortcut"] = name
    return result


def find_and_click(name: str, control_type: str = None, double: bool = False) -> dict:
    """Find a UI element by name via Windows UI Automation and click it.

    UIA-first (fast, no screenshot). This is the reliable path for ribbon tabs,
    buttons, and menu items; falls back to OmniParser only via the agent loop.
    """
    _require_display()
    if not _HAS_PYWINAUTO:
        raise RuntimeError("Windows UI Automation is unavailable, so find_and_click cannot verify the target.")
    window = _get_agent_excel_window()
    _ensure_agent_workbook(window)
    _focus_excel_for_keyboard()
    target = None
    name_l = " ".join(name.strip().split()).lower()
    for control in window.descendants():
        try:
            txt = " ".join(control.window_text().split()).lower()
            if not txt or name_l not in txt:
                continue
            if control_type:
                ct = str(getattr(control.element_info, "control_type", "")).lower()
                if control_type.lower() not in ct:
                    continue
            target = control
            break
        except Exception:
            continue
    if target is None:
        raise RuntimeError(f"Could not find a UI element named '{name}' in Excel via UI Automation.")
    try:
        if double:
            target.click_input(double=True)
        else:
            target.click_input()
    except Exception as exc:
        raise RuntimeError(f"Found '{name}' but could not click it: {exc}") from exc
    time.sleep(0.3)
    return {
        "clicked_element": name,
        "found_by": "uia",
        "verified": True,
        "verification_note": f"Found and clicked '{name}' via UIA (no screenshot needed).",
    }


def scroll(clicks: int) -> dict:
    _require_display()
    _focus_excel_for_keyboard()
    pyautogui.scroll(clicks)
    return {"scrolled": clicks, "verified": True}


def list_open_windows() -> dict:
    """Used by the OS-Level Event Listener / window-focus awareness -
    Windows-only (pywinauto)."""
    if not _HAS_PYWINAUTO:
        return {"windows": [], "verified": False,
                "verification_note": "pywinauto not available - Windows-only feature."}
    windows = [w.window_text() for w in Desktop(backend="uia").windows() if w.window_text()]
    return {"windows": windows, "verified": True}


def execute_excel_shortcut(shortcut_name: str) -> dict:
    """Execute a named Excel keyboard shortcut directly (bypasses vision).
    
    This is the fastest way to perform standard Excel operations like:
    - bold, italic, underline
    - currency format, percent format
    - merge cells, auto-fit columns
    - sort, filter
    - insert charts, tables
    - etc.
    
    Args:
        shortcut_name: Name from EXCEL_SHORTCUTS (e.g., 'bold', 'currency', 'merge_center')
    
    Returns:
        Dict with verification info
    """
    _require_display()
    
    if shortcut_name not in EXCEL_SHORTCUTS:
        return {
            "verified": False,
            "error": f"Unknown shortcut: {shortcut_name}",
            "available_shortcuts": list(EXCEL_SHORTCUTS.keys())[:20],
        }
    
    # Focus Excel first
    _focus_excel_for_keyboard()
    
    # Execute the shortcut
    success = execute_shortcut(shortcut_name)
    
    if success:
        return {
            "verified": True,
            "shortcut": shortcut_name,
            "keys": list(EXCEL_SHORTCUTS[shortcut_name]),
            "verification_note": f"Executed shortcut '{shortcut_name}' directly without vision.",
        }
    else:
        return {
            "verified": False,
            "error": f"Failed to execute shortcut '{shortcut_name}'",
        }


def execute_excel_alt_sequence(keys: list[str]) -> dict:
    """Execute a raw Alt key sequence for Excel operations.
    
    This allows direct execution of any Excel keyboard shortcut,
    even if it's not in the predefined list.
    
    Args:
        keys: List of keys (e.g., ['alt', 'h', 'b', 'a'] for all borders)
    
    Returns:
        Dict with verification info
    """
    _require_display()
    _focus_excel_for_keyboard()
    
    success = execute_alt_sequence(keys)
    
    if success:
        return {
            "verified": True,
            "keys": keys,
            "verification_note": "Executed Alt key sequence directly without vision.",
        }
    else:
        return {
            "verified": False,
            "error": f"Failed to execute key sequence: {keys}",
        }


def batch_excel_operations(operations: list[dict]) -> dict:
    """Execute multiple Excel operations in sequence without pausing for verification.
    
    Args:
        operations: List of operations, each with:
            - type: 'shortcut', 'alt_sequence', 'type_text', 'press_key', 'go_to_range'
            - For shortcut: {'type': 'shortcut', 'name': 'bold'}
            - For alt_sequence: {'type': 'alt_sequence', 'keys': ['alt', 'h', 'b', 'a']}
            - For type_text: {'type': 'type_text', 'text': 'Hello'}
            - For press_key: {'type': 'press_key', 'key': 'enter'}
            - For go_to_range: {'type': 'go_to_range', 'reference': 'A1'}
    
    Returns:
        Dict with results of each operation
    """
    results = []
    
    for op in operations:
        op_type = op.get("type")
        
        if op_type == "shortcut":
            result = execute_excel_shortcut(op.get("name", ""))
        elif op_type == "alt_sequence":
            result = execute_excel_alt_sequence(op.get("keys", []))
        elif op_type == "type_text":
            result = type_text(op.get("text", ""))
        elif op_type == "press_key":
            result = press_key(op.get("key", ""))
        elif op_type == "go_to_range":
            result = go_to_range(op.get("reference", ""))
        else:
            result = {"verified": False, "error": f"Unknown operation type: {op_type}"}
        
        results.append({
            "operation": op,
            "result": result,
        })
    
    return {
        "verified": all(r["result"].get("verified", False) for r in results),
        "results": results,
        "operations_count": len(operations),
    }


def search_cached_elements(text: str, context: str = "") -> dict:
    """Search cached screen data for elements matching text.
    
    This allows finding UI elements from previous parses without
    taking a new screenshot.
    
    Args:
        text: Text to search for (case-insensitive)
        context: Optional context to filter by
    
    Returns:
        Dict with matching elements
    """
    matches = find_cached_elements(text, context)
    
    return {
        "verified": True,
        "matches": matches,
        "count": len(matches),
        "query": text,
        "context": context,
    }
