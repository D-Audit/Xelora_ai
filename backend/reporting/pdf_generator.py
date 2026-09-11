"""
reporting/pdf_generator.py
Crewlyze-inspired PDF report generation.

Creates professional PDF reports with:
- Task summary and status
- Data quality profiles
- Charts (as images)
- Action logs
- Recommendations

Uses fpdf2 (must be installed: pip install fpdf2)
"""

import time
import json
import os
import re
from pathlib import Path
from typing import Optional

REPORTS_DIR = Path(__file__).parent.parent / "storage" / "reports"


def _report_directory(user_id: int | None = None) -> Path:
    scope = "anonymous" if user_id is None else str(user_id)
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", scope):
        raise ValueError("user_id contains unsupported characters")
    directory = REPORTS_DIR / scope
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def generate_task_report(
    instruction: str,
    actions: list,
    outcome: str,
    success: bool,
    profile: dict = None,
    filename: str = None,
    user_id: int | None = None,
) -> str:
    """Generate a PDF report for a completed task.

    Returns the path to the generated PDF file.
    """
    reports_dir = _report_directory(user_id)

    if not filename:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"report_{timestamp}.pdf"

    filename = Path(filename).name
    if not filename.lower().endswith(".pdf"):
        filename = f"{filename}.pdf"
    filepath = reports_dir / filename

    try:
        from fpdf import FPDF
    except ImportError:
        # Fallback: generate a text report if fpdf2 not installed
        return _generate_text_report(filepath.with_suffix(".txt"), instruction, actions, outcome, success, profile)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    # Title page
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 24)
    pdf.cell(0, 20, "Task Report", ln=True, align="C")
    pdf.set_font("Helvetica", "", 12)
    pdf.cell(0, 10, f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}", ln=True, align="C")
    pdf.ln(10)

    # Status badge
    pdf.set_font("Helvetica", "B", 14)
    status_text = "SUCCESS" if success else "FAILED"
    pdf.cell(0, 10, f"Status: {status_text}", ln=True, align="C")
    pdf.ln(10)

    # Task section
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Task Instruction", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 6, instruction)
    pdf.ln(5)

    # Actions section
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Actions Taken", ln=True)
    pdf.set_font("Helvetica", "", 10)

    for i, action in enumerate(actions, 1):
        name = action.get("name", "unknown")
        result = action.get("result", {})
        status = "OK" if result.get("result") else "FAIL"
        pdf.cell(0, 6, f"{i}. {name} [{status}]", ln=True)

        if result.get("error"):
            pdf.set_font("Helvetica", "I", 9)
            pdf.cell(0, 5, f"   Error: {result['error']}", ln=True)
            pdf.set_font("Helvetica", "", 10)

    pdf.ln(5)

    # Data quality section
    if profile and profile.get("status") != "empty":
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "Data Quality", ln=True)
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(0, 6, f"Quality Score: {profile.get('quality_score', 'N/A')}/100", ln=True)
        pdf.cell(0, 6, f"Rows: {profile.get('rows', 0)}, Columns: {profile.get('columns', 0)}", ln=True)

        if profile.get("issues"):
            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 8, "Issues Found:", ln=True)
            pdf.set_font("Helvetica", "", 10)
            for issue in profile["issues"]:
                pdf.cell(0, 6, f"  - {issue}", ln=True)

    # Outcome section
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Outcome", ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 6, outcome or "No outcome recorded")

    # Save
    pdf.output(str(filepath))
    return str(filepath)


def _generate_text_report(filepath, instruction, actions, outcome, success, profile):
    """Fallback text report when fpdf2 is not available."""
    lines = [
        "=" * 60,
        "TASK REPORT",
        "=" * 60,
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Status: {'SUCCESS' if success else 'FAILED'}",
        "",
        "TASK INSTRUCTION:",
        instruction,
        "",
        "ACTIONS TAKEN:",
    ]

    for i, action in enumerate(actions, 1):
        name = action.get("name", "unknown")
        result = action.get("result", {})
        status = "OK" if result.get("result") else "FAIL"
        lines.append(f"  {i}. {name} [{status}]")
        if result.get("error"):
            lines.append(f"     Error: {result['error']}")

    if profile and profile.get("status") != "empty":
        lines.extend([
            "",
            "DATA QUALITY:",
            f"  Score: {profile.get('quality_score', 'N/A')}/100",
            f"  Rows: {profile.get('rows', 0)}, Columns: {profile.get('columns', 0)}",
        ])
        for issue in profile.get("issues", []):
            lines.append(f"  - {issue}")

    lines.extend([
        "",
        "OUTCOME:",
        outcome or "No outcome recorded",
        "",
        "=" * 60,
    ])

    filepath.write_text("\n".join(lines), encoding="utf-8")
    return str(filepath)


def get_report_path(filename: str, user_id: int | None = None) -> Optional[str]:
    """Get the full path to a report file."""
    filepath = _report_directory(user_id) / Path(filename).name
    if filepath.exists():
        return str(filepath)
    return None


def list_reports(user_id: int | None = None) -> list:
    """List all generated reports."""
    reports_dir = _report_directory(user_id)
    return sorted([f.name for f in reports_dir.glob("*.pdf")] + [f.name for f in reports_dir.glob("*.txt")])
