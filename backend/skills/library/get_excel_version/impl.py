"""
skills/library/get_excel_version/impl.py
Detects the real Excel version on the user's machine so the AI can
stop guessing whether modern dynamic-array functions (UNIQUE, SORT,
FILTER, XLOOKUP, LET) are safe to use, or whether it needs to fall
back to legacy-compatible formulas (VLOOKUP, INDEX/MATCH, SUMIFS)
from the very first formula it writes - not discover it the hard way
after a #NAME? error three steps in.
"""

from skills.excel_shared import get_active_workbook, get_excel_capabilities


LEGACY_FUNCTIONS = [
    "VLOOKUP", "INDEX/MATCH", "SUMIFS", "COUNTIFS", "IFERROR", "TEXT",
    "DATE", "YEAR", "MONTH", "QUARTER",
]
MODERN_FUNCTIONS = [
    "XLOOKUP", "UNIQUE", "SORT", "FILTER", "SEQUENCE", "LET",
]
UNSUPPORTED_IN_LEGACY = [
    "XLOOKUP", "LET", "UNIQUE", "SORT", "FILTER", "SEQUENCE", "RANDARRAY",
    "HSTACK", "VSTACK",
]


def run():
    wb = get_active_workbook()
    app = wb.app

    try:
        # This is executed before the model's first action. Do not write a
        # dynamic-array probe formula here: a slow or modal Excel UI must not
        # delay the entire task or trigger an Excel restart. Legacy formulas
        # work on every supported Excel version, including Excel 2016.
        capabilities = get_excel_capabilities(wb, probe_dynamic_arrays=False)
        full_version = capabilities.get("application_version") or str(app.api.Version)
        build = capabilities.get("application_build") or str(app.api.Build)
    except Exception as e:
        return {
            "status": "detection_failed", "verified": False,
            "error": str(e),
            "verification_note": "Could not read Excel's version via COM. Assume a legacy/conservative feature set.",
        }

    major = str(full_version).split(".")[0]
    supports_dynamic_arrays = bool(capabilities["dynamic_arrays"])

    if supports_dynamic_arrays:
        label = "Excel with confirmed modern dynamic-array support"
    elif major == "16":
        label = "Excel version 16 without dynamic-array support"
    elif major == "15":
        label = "Excel 2013 (no dynamic arrays, no XLOOKUP)"
    elif major == "14":
        label = "Excel 2010 (no dynamic arrays, no XLOOKUP, limited conditional formatting)"
    else:
        label = f"Excel version {full_version} (unrecognised - treat as legacy/conservative)"

    approved_functions = LEGACY_FUNCTIONS + MODERN_FUNCTIONS if supports_dynamic_arrays else LEGACY_FUNCTIONS
    blocked_functions = [] if supports_dynamic_arrays else UNSUPPORTED_IN_LEGACY

    return {
        "raw_version": full_version, "build": build, "label": label,
        "supports_dynamic_arrays": supports_dynamic_arrays,
        "supports_xlookup": supports_dynamic_arrays,
        "approved_functions": approved_functions,
        "blocked_functions": blocked_functions,
        "formula_mode": capabilities["formula_mode"],
        "planning_rule": capabilities["planning_rule"],
        "status": "detected", "verified": True,
    }
