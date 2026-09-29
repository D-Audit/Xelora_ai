"""
skills/library/copy_range/impl.py
Copy / move / paste-values / transpose a range with read-back verification.
"""

from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401

_XL_PASTE_ALL = -4104
_XL_PASTE_VALUES = -4163
_XL_PASTE_FORMATS = -4122
_ERROR_TEXT = {"#NAME?", "#REF!", "#VALUE!", "#DIV/0!", "#N/A", "#NULL!", "#NUM!", "#SPILL!", "#CALC!"}


def _grid(rng, attribute: str = "value"):
    view = rng.options(ndim=2, err_to_str=True) if attribute == "value" else rng.options(ndim=2)
    data = getattr(view, attribute)
    return [list(row) for row in (data or [])]


def _transposed(grid):
    return [list(column) for column in zip(*grid)] if grid else []


def _overlaps(a, b) -> bool:
    return not (
        a.last_cell.row < b.row or b.last_cell.row < a.row
        or a.last_cell.column < b.column or b.last_cell.column < a.column
    )


def run(source_sheet: str, source_range: str, target_sheet: str, target_cell: str,
        mode: str = "all", transpose: bool = False, move: bool = False):
    mode = (mode or "all").strip().lower()
    if mode not in {"all", "values", "formats"}:
        return {"status": "invalid_mode", "verified": False,
                "error": "mode must be 'all', 'values', or 'formats'."}
    if move and mode != "all":
        return {"status": "invalid_arguments", "verified": False,
                "error": "move requires mode 'all' so nothing is lost from the source."}

    wb = get_active_workbook()
    names = [sheet.name for sheet in wb.sheets]
    for label, name in (("source_sheet", source_sheet), ("target_sheet", target_sheet)):
        if name not in names:
            return {"status": "sheet_not_found", "verified": False,
                    "error": f"{label} '{name}' does not exist. Sheets: {names}."}

    src = wb.sheets[source_sheet].range(source_range)
    rows, cols = src.shape
    out_rows, out_cols = (cols, rows) if transpose else (rows, cols)
    dest = wb.sheets[target_sheet].range(target_cell).resize(out_rows, out_cols)
    if source_sheet == target_sheet and _overlaps(src, dest):
        return {"status": "ranges_overlap", "verified": False,
                "error": f"Destination {dest.address} overlaps source {src.address}; choose a free area."}

    source_values = _grid(src)
    source_formulas = _grid(src, "formula")
    expected = _transposed(source_values) if transpose else source_values
    expected_formulas = _transposed(source_formulas) if transpose else source_formulas

    if mode == "values":
        dest.value = expected
    else:
        paste = _XL_PASTE_ALL if mode == "all" else _XL_PASTE_FORMATS
        src.api.Copy()
        try:
            dest[0, 0].api.PasteSpecial(Paste=paste, Transpose=bool(transpose))
        finally:
            wb.app.api.CutCopyMode = False

    actual = _grid(dest)
    mismatches = []
    if mode in {"all", "values"}:
        for r in range(out_rows):
            for c in range(out_cols):
                formula = str(expected_formulas[r][c] or "")
                got = actual[r][c] if r < len(actual) and c < len(actual[r]) else None
                if mode == "all" and formula.startswith("="):
                    # Relative references legitimately shift; only an error is a failure.
                    if isinstance(got, str) and got.strip() in _ERROR_TEXT:
                        mismatches.append({"cell": dest[r, c].address, "problem": got})
                elif got != expected[r][c]:
                    mismatches.append({"cell": dest[r, c].address, "expected": expected[r][c], "found": got})
                if len(mismatches) >= 10:
                    break
    else:
        if src[0, 0].number_format != dest[0, 0].number_format:
            mismatches.append({"cell": dest[0, 0].address, "problem": "number format differs"})

    verified = not mismatches
    source_cleared = None
    if move and verified:
        src.clear()
        source_cleared = all(value is None for row in _grid(src) for value in row)
        verified = source_cleared
    wb.save()

    return {
        "source": f"'{source_sheet}'!{src.address}", "destination": f"'{target_sheet}'!{dest.address}",
        "mode": mode, "transposed": bool(transpose), "moved": bool(move) and bool(source_cleared),
        "rows": out_rows, "columns": out_cols, "status": "copied" if verified else "copy_mismatch",
        "verified": verified, "mismatches": mismatches,
        "verification_note": (
            "Read back the destination and compared it with the source"
            + (" and confirmed the source is empty." if move and verified else ".")
            if verified else "Destination does not match the source; inspect before continuing."
        ),
    }
