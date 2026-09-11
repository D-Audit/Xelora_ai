"""
reporting/data_profiler.py
Crewlyze-inspired data profiling. Analyzes spreadsheet data for
quality issues, patterns, and statistics before generating reports.

Checks: nulls, duplicates, type consistency, outliers, data distribution.
"""

import time
import json
from typing import Optional


def profile_current_sheet() -> dict:
    """Profile the active sheet's data and return quality metrics."""
    try:
        from skills.excel_shared import get_active_workbook, normalize

        workbook = get_active_workbook()
        sheet = workbook.sheets.active
        raw_values = sheet.used_range.value
        values = [] if raw_values in (None, "") else normalize(raw_values)
        sheet_name = str(sheet.name)
        headers = values[0] if values else []
        data = values[1:] if values else []
    except Exception:
        # Retain the visual path as a fallback for installations running in
        # UI-only mode without the Excel object model.
        from vision.ui_control import get_sheet_info, get_active_sheet_name

        active_sheet = get_active_sheet_name()
        sheet_name = active_sheet.get("sheet_name") if isinstance(active_sheet, dict) else active_sheet
        sheet_name = sheet_name or "active worksheet"
        info = get_sheet_info()
        headers = info.get("headers", [])
        data = info.get("data", [])

    if not data or not headers:
        return {
            "sheet": sheet_name,
            "status": "empty",
            "rows": 0,
            "columns": len(headers),
            "quality_score": 0,
        }

    profile = {
        "sheet": sheet_name,
        "rows": len(data),
        "columns": len(headers),
        "headers": headers,
        "column_profiles": [],
        "quality_score": 100,
        "issues": [],
    }

    for col_idx, header in enumerate(headers):
        col_data = [row[col_idx] if col_idx < len(row) else None for row in data]
        col_profile = _profile_column(header, col_idx, col_data)
        profile["column_profiles"].append(col_profile)
        profile["quality_score"] -= col_profile["penalty"]
        profile["issues"].extend(col_profile["issues"])

    profile["quality_score"] = max(0, profile["quality_score"])
    return profile


def _profile_column(header: str, col_idx: int, values: list) -> dict:
    """Profile a single column for data quality."""
    total = len(values)
    nulls = sum(1 for v in values if v is None or str(v).strip() == "")
    non_nulls = [v for v in values if v is not None and str(v).strip() != ""]

    # Type detection
    numeric_count = 0
    date_count = 0
    text_count = 0
    for v in non_nulls:
        s = str(v).strip()
        try:
            float(s)
            numeric_count += 1
            continue
        except ValueError:
            pass
        if _looks_like_date(s):
            date_count += 1
        else:
            text_count += 1

    # Duplicates
    unique_vals = set(str(v).strip().lower() for v in non_nulls)
    duplicates = total - nulls - len(unique_vals)

    # Outlier detection for numeric columns
    outliers = []
    if numeric_count > len(non_nulls) * 0.7:
        nums = []
        for v in non_nulls:
            try:
                nums.append(float(str(v).strip()))
            except ValueError:
                pass
        if len(nums) > 3:
            mean = sum(nums) / len(nums)
            std = (sum((x - mean) ** 2 for x in nums) / len(nums)) ** 0.5
            if std > 0:
                outliers = [i for i, n in enumerate(nums) if abs(n - mean) > 2 * std]

    penalty = 0
    issues = []

    null_pct = nulls / max(total, 1) * 100
    if null_pct > 10:
        penalty += min(20, null_pct)
        issues.append(f"{header}: {null_pct:.0f}% null values")

    if duplicates > 0 and duplicates / max(total, 1) > 0.1:
        penalty += 5
        issues.append(f"{header}: {duplicates} duplicate values")

    if len(outliers) > 0 and len(outliers) / max(total, 1) < 0.05:
        penalty += 2
        issues.append(f"{header}: {len(outliers)} potential outliers")

    dominant_type = "text"
    if numeric_count > len(non_nulls) * 0.7:
        dominant_type = "numeric"
    elif date_count > len(non_nulls) * 0.7:
        dominant_type = "date"

    return {
        "header": header,
        "col_index": col_idx,
        "total_values": total,
        "null_count": nulls,
        "null_percentage": round(null_pct, 1),
        "duplicate_count": duplicates,
        "dominant_type": dominant_type,
        "outlier_count": len(outliers),
        "unique_count": len(unique_vals),
        "penalty": penalty,
        "issues": issues,
    }


def _looks_like_date(s: str) -> bool:
    """Simple heuristic to detect date-like strings."""
    date_seps = ["/", "-", "."]
    for sep in date_seps:
        if sep in s:
            parts = s.split(sep)
            if len(parts) == 3 and all(p.isdigit() for p in parts):
                return True
    return False


def generate_profile_report(profile: dict) -> str:
    """Generate a human-readable summary of the profile."""
    if profile.get("status") == "empty":
        return f"Sheet '{profile['sheet']}' is empty."

    lines = [
        f"Data Profile: {profile['sheet']}",
        f"  Rows: {profile['rows']}, Columns: {profile['columns']}",
        f"  Quality Score: {profile['quality_score']}/100",
    ]

    if profile.get("issues"):
        lines.append("  Issues:")
        for issue in profile["issues"]:
            lines.append(f"    - {issue}")

    lines.append("  Column Details:")
    for col in profile.get("column_profiles", []):
        lines.append(
            f"    {col['header']}: {col['dominant_type']}, "
            f"{col['null_count']} nulls, {col['unique_count']} unique"
        )

    return "\n".join(lines)
