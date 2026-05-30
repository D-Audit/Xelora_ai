"""
skills/library/create_power_query_connection/impl.py
Auto-migrated from skills/excel_extended.py. Do not hand-edit the SKILL.md
metadata and this implementation out of sync - update both together.
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401



def run(connection_name: str, connection_string: str, command_text: str,
                                   dest_sheet_name: str, dest_cell: str = "A1"):
    wb = get_active_workbook()
    if dest_sheet_name not in [s.name for s in wb.sheets]:
        wb.sheets.add(dest_sheet_name)
    dest_sheet = wb.sheets[dest_sheet_name]
    dest_range = dest_sheet.range(dest_cell).api

    try:
        connection = wb.api.Connections.Add2(
            connection_name, "", connection_string, command_text, 2,  # 2 = xlCmdSql
        )
        list_object = dest_sheet.api.ListObjects.Add(
            0, connection, dest_range, True, 1,  # 0 = xlSrcExternal
        )
        list_object.Refresh()
        wb.save()
        return {"connection_name": connection_name, "dest_sheet": dest_sheet_name,
                "status": "connection_created", "verified": True}
    except Exception as e:
        return {"connection_name": connection_name, "status": "failed", "verified": False,
                "error": str(e), "verification_note": (
                    "Power Query/external-data connections are the least reliable part of "
                    "the Excel automation surface - this connection string/command may need "
                    "manual adjustment, or may require the driver to be installed on this machine."
                )}
