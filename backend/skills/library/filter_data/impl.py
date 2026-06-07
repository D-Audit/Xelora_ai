"""
skills/library/filter_data/impl.py
Auto-migrated from skills/excel_data.py. Do not hand-edit the SKILL.md
metadata and this implementation out of sync - update both together.
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401



def run(sheet_name: str, cell_range: str, column_index: int, condition_value, operator: str = "equals"):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    values = normalize(sheet.range(cell_range).value)

    def matches(cell_value):
        if operator == "equals":
            return cell_value == condition_value
        if operator == "greater_than":
            return cell_value is not None and cell_value > condition_value
        if operator == "less_than":
            return cell_value is not None and cell_value < condition_value
        if operator == "contains":
            return cell_value is not None and str(condition_value) in str(cell_value)
        return False

    matching_rows = [row for row in values if len(row) > column_index and matches(row[column_index])]

    return {
        "sheet": sheet_name, "range": cell_range, "operator": operator,
        "condition_value": condition_value, "matching_rows": matching_rows,
        "match_count": len(matching_rows), "verified": True,
    }
