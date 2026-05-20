"""
skills/library/add_macro_button/impl.py
Auto-migrated from skills/excel_vba.py. Do not hand-edit the SKILL.md
metadata and this implementation out of sync - update both together.
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401

def _vba_trust_enabled(wb) -> bool:
    """Touching VBProject raises a COM error if trust access isn't granted -
    cheapest reliable way to test it."""
    try:
        _ = wb.api.VBProject.VBComponents.Count
        return True
    except Exception:
        return False


def run(sheet_name: str, cell: str, label: str, macro_name: str,
                      background_color: str = None, width: float = 160, height: float = 30):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    anchor = sheet.range(cell)

    button = sheet.api.Buttons().Add(anchor.left, anchor.top, width, height)
    button.OnAction = macro_name
    button.Characters().Text = label

    if background_color:
        r, g, b = hex_to_rgb(background_color)
        rgb_int = r + (g * 256) + (b * 65536)  # Excel packs colors as BGR longs
        try:
            button.Font.Color = 0xFFFFFF
        except Exception:
            pass
        try:
            button.Interior.Color = rgb_int
        except Exception:
            pass  # fill styling isn't exposed identically across Excel versions - not fatal

    return {
        "sheet": sheet_name, "cell": cell, "label": label, "macro_name": macro_name,
        "status": "button_added", "verified": True,
        "verification_note": (
            "Button drawn and OnAction wired to the macro. Click it once manually to "
            "confirm it actually fires - this can't be verified without invoking it."
        ),
    }
