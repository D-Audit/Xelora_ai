"""Fast, ordered, idempotent worksheet creation for multi-sheet requests."""

from skills.excel_shared import get_active_workbook, normalize, use_task_bootstrap_workbook


def _is_blank_startup_sheet(sheet) -> bool:
    """Return whether a new workbook's only default sheet has no contents."""
    try:
        values = normalize(sheet.used_range.value)
    except Exception:
        return False
    return all(value in (None, "") for row in values for value in row)


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
    reused_default_sheet = None
    try:
        # A new Xelora-owned workbook begins as one empty Sheet1. Renaming it
        # to the first requested name avoids a stray blank tab and lets every
        # later insertion preserve the user's requested left-to-right order.
        previous_sheet = None
        if (
            use_task_bootstrap_workbook()
            and len(workbook.sheets) == 1
            and _is_blank_startup_sheet(workbook.sheets[0])
            and normalized[0] not in before
        ):
            previous_sheet = workbook.sheets[0]
            default_sheet_name = previous_sheet.name
            previous_sheet.name = normalized[0]
            reused_default_sheet = normalized[0]
            created.append(normalized[0])
            before.remove(default_sheet_name)
            before.add(normalized[0])

        for name in normalized:
            if name not in before:
                previous_sheet = workbook.sheets.add(name, after=previous_sheet)
                created.append(name)
                before.add(name)
            elif previous_sheet is None:
                previous_sheet = workbook.sheets[name]
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

    final_sheet_names = [sheet.name for sheet in workbook.sheets]
    final_names = set(final_sheet_names)
    missing = [name for name in normalized if name not in final_names]
    requested_order_verified = (
        [name for name in final_sheet_names if name in set(normalized)] == normalized
    )
    return {
        "sheet_names": normalized,
        "created_sheet_names": created,
        "reused_default_sheet": reused_default_sheet,
        "already_present_sheet_names": [name for name in normalized if name not in created],
        "final_sheet_names": final_sheet_names,
        "requested_order_verified": requested_order_verified,
        "verified": not missing and requested_order_verified,
        "status": "sheets_created" if not missing and requested_order_verified else "sheet_batch_verification_failed",
        "verification_note": (
            f"Confirmed all {len(normalized)} requested worksheet tabs exist in the requested order after one saved Excel action."
            if not missing and requested_order_verified
            else (
                f"Missing worksheet tabs after creation: {missing}"
                if missing else "Worksheet tabs exist but their order could not be verified."
            )
        ),
    }
