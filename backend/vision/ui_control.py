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

import time

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


def _require_display():
    if not _HAS_PYAUTOGUI:
        raise RuntimeError(
            "pyautogui is not available or no display is attached. The visual "
            "fallback layer only works on a real desktop (Windows/Mac) with the "
            "backend running locally, not in a headless server/container."
        )


def screenshot_active_window(save_path: str) -> dict:
    """Captures the current screen (Intelligent Window Capture, simplified
    to whole-screen for portability - swap in pywinauto's per-window
    capture on Windows for the 'window-specific screenshot' variant)."""
    _require_display()
    img = pyautogui.screenshot()
    img.save(save_path)
    return {"path": save_path, "size": img.size, "verified": True}


def click_at(x: int, y: int, double: bool = False) -> dict:
    _require_display()
    if double:
        pyautogui.doubleClick(x, y)
    else:
        pyautogui.click(x, y)
    time.sleep(0.2)
    return {"clicked_at": [x, y], "double": double, "verified": True}


def type_text(text: str, interval: float = 0.02) -> dict:
    _require_display()
    pyautogui.typewrite(text, interval=interval)
    return {"typed": text, "verified": True}


def press_key(key: str) -> dict:
    _require_display()
    pyautogui.press(key)
    return {"pressed": key, "verified": True}


def list_open_windows() -> dict:
    """Used by the OS-Level Event Listener / window-focus awareness -
    Windows-only (pywinauto)."""
    if not _HAS_PYWINAUTO:
        return {"windows": [], "verified": False,
                "verification_note": "pywinauto not available - Windows-only feature."}
    windows = [w.window_text() for w in Desktop(backend="uia").windows() if w.window_text()]
    return {"windows": windows, "verified": True}
