"""
skills/library/add_sparkline/impl.py
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401


def run(sheet_name: str, cell: str, data_range: str, sparkline_type: str = "line"):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    type_map = {"line": 1, "column": 2, "win_loss": 3}
    code = type_map.get(sparkline_type.lower(), 1)
    group = sheet.api.SparklineGroups.Add(code, sheet.range(data_range).api.Address)
    group.Item(1).SourceData = sheet.range(data_range).api.Address
    group.Item(1).Location = sheet.range(cell).api.Address
    wb.save()
    return {"sheet": sheet_name, "cell": cell, "data_range": data_range,
            "sparkline_type": sparkline_type, "status": "sparkline_added", "verified": True}
