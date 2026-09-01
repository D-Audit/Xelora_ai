"""Fast, idempotent worksheet creation for multi-sheet workbook requests."""

from skills.excel_shared import get_active_workbook


def run(sheet_names: list[str]):
    if not isinstance(sheet_names, list) or len(sheet_names) < 2:
        return {
            "error": "sheet_names must contain at least two worksheet names.",
            "verified": False,
            "status": "invalid_sheet_names",
        }

    normalized = []
    seen = set()
    for name in sheet_names:
        if not isinstance(name, str) or not name.strip():
            return {
                "error": "Every sheet name must be a non-empty string.",
                "verified": False,
                "status": "invalid_sheet_names",
            }
        cleaned = name.strip()
        if cleaned in seen:
            return {
                "error": f"Duplicate worksheet name requested: '{cleaned}'.",
                "verified": False,
                "status": "duplicate_sheet_name",
            }
        # Excel's native API raises a clear exception for illegal characters
        # and overlong names; the result below preserves it rather than
        # guessing a modified name the user did not request.
        normalized.append(cleaned)
        seen.add(cleaned)

    workbook = get_active_workbook()
    before = {sheet.name for sheet in workbook.sheets}
    created = []
    try:
        for name in normalized:
            if name not in before:
                workbook.sheets.add(name)
                created.append(name)
                before.add(name)
        # One checkpoint instead of one disk save per sheet substantially
        # reduces perceived delay while keeping the complete batch recoverable.
        workbook.save()
    except Exception as exc:
        present = [name for name in normalized if name in {sheet.name for sheet in workbook.sheets}]
        return {
            "error": str(exc),
            "created_sheet_names": created,
            "present_sheet_names": present,
            "verified": False,
            "status": "sheet_batch_create_failed",
        }

    final_names = {sheet.name for sheet in workbook.sheets}
    missing = [name for name in normalized if name not in final_names]
    return {
        "sheet_names": normalized,
        "created_sheet_names": created,
        "already_present_sheet_names": [name for name in normalized if name not in created],
        "verified": not missing,
        "status": "sheets_created" if not missing else "sheet_batch_verification_failed",
        "verification_note": (
            f"Confirmed all {len(normalized)} requested worksheet tabs exist after one saved Excel action."
            if not missing else f"Missing worksheet tabs after creation: {missing}"
        ),
    }
