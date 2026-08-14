"""
skills/library/get_excel_version/impl.py
Detects the real Excel version on the user's machine so the AI can
stop guessing whether modern dynamic-array functions (UNIQUE, SORT,
FILTER, XLOOKUP, LET) are safe to use, or whether it needs to fall
back to legacy-compatible formulas (VLOOKUP, INDEX/MATCH, SUMIFS)
from the very first formula it writes - not discover it the hard way
after a #NAME? error three steps in.
"""

from skills.excel_shared import get_active_workbook


def run():
    wb = get_active_workbook()
    app = wb.app

    try:
        full_version = app.api.Version  # e.g. "16.0"
        build = app.api.Build  # internal build number, distinguishes 365 from perpetual 2019/2021
    except Exception as e:
        return {
            "status": "detection_failed", "verified": False,
            "error": str(e),
            "verification_note": "Could not read Excel's version via COM. Assume a legacy/conservative feature set.",
        }

    major = full_version.split(".")[0]

    supports_dynamic_arrays = major == "16" and build >= 10000

    if major == "16" and not supports_dynamic_arrays:
        label = "Excel 2016/2019 (perpetual license, no dynamic arrays)"
    elif major == "16":
        label = "Excel 365 or 2021+ (full dynamic-array support)"
    elif major == "15":
        label = "Excel 2013 (no dynamic arrays, no XLOOKUP)"
    elif major == "14":
        label = "Excel 2010 (no dynamic arrays, no XLOOKUP, limited conditional formatting)"
    else:
        label = f"Excel version {full_version} (unrecognised - treat as legacy/conservative)"

    return {
        "raw_version": full_version, "build": build, "label": label,
        "supports_dynamic_arrays": supports_dynamic_arrays,
        "supports_xlookup": supports_dynamic_arrays,
        "status": "detected", "verified": True,
    }