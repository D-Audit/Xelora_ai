"""
skills/library/add_dropdown_control/impl.py
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401


def run(sheet_name: str, control_type: str, cell: str, options: list = None,
        linked_cell: str = None, label: str = None):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    anchor = sheet.range(cell)

    if control_type.lower() == "dropdown":
        if not options:
            return {"error": "options is required for control_type=dropdown", "verified": False}
        control = sheet.api.DropDowns().Add(anchor.left, anchor.top, 100, 20)
        control.List = options
        if linked_cell:
            control.LinkedCell = sheet.range(linked_cell).api.Address
        note = f"Dropdown with {len(options)} options added."
    elif control_type.lower() == "checkbox":
        control = sheet.api.CheckBoxes().Add(anchor.left, anchor.top, 100, 20)
        if label:
            control.Text = label
        if linked_cell:
            control.LinkedCell = sheet.range(linked_cell).api.Address
        note = "Checkbox added."
    else:
        return {"error": f"Unknown control_type '{control_type}' - use 'dropdown' or 'checkbox'", "verified": False}

    wb.save()
    return {"sheet": sheet_name, "control_type": control_type, "cell": cell,
            "status": "control_added", "verified": True, "verification_note": note}
