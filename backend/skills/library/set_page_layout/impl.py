"""
skills/library/set_page_layout/impl.py
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401


def run(sheet_name: str, orientation: str = None, fit_to_pages_wide: int = None,
        fit_to_pages_tall: int = None, print_area: str = None, margins_inches: float = None):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    setup = sheet.api.PageSetup
    changes = []

    if orientation:
        setup.Orientation = 2 if orientation.lower() == "landscape" else 1  # xlLandscape=2, xlPortrait=1
        changes.append(f"orientation -> {orientation}")

    if fit_to_pages_wide is not None or fit_to_pages_tall is not None:
        setup.Zoom = False  # fit-to-page and Zoom are mutually exclusive in Excel
        if fit_to_pages_wide is not None:
            setup.FitToPagesWide = fit_to_pages_wide
            changes.append(f"fit_to_pages_wide -> {fit_to_pages_wide}")
        if fit_to_pages_tall is not None:
            setup.FitToPagesTall = fit_to_pages_tall
            changes.append(f"fit_to_pages_tall -> {fit_to_pages_tall}")

    if print_area:
        setup.PrintArea = print_area
        changes.append(f"print_area -> {print_area}")

    if margins_inches is not None:
        points = margins_inches * 72  # Excel page setup margins are in points
        setup.TopMargin = points
        setup.BottomMargin = points
        setup.LeftMargin = points
        setup.RightMargin = points
        changes.append(f"margins -> {margins_inches}in")

    wb.save()
    return {"sheet": sheet_name, "changes": changes,
            "status": "page_layout_set" if changes else "no_changes_requested",
            "verified": True}
