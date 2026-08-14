"""
skills/library/apply_formatting/impl.py
Auto-migrated from skills/excel_format.py. Do not hand-edit the SKILL.md
metadata and this implementation out of sync - update both together.

FIXED: Excel's custom number format syntax requires any literal text
(e.g. a currency code like "KES") to be wrapped in double quotes -
'KES #,##0.00' is invalid and Excel's COM API rejects it outright.
Rather than relying on the AI to always remember to quote literal text,
this now detects unquoted letter sequences in a number_format and quotes
them automatically before sending it to Excel.
"""

import re
from skills.excel_shared import get_active_workbook, normalize, hex_to_rgb  # noqa: F401

_FORMAT_TOKENS = {
    "E", "e", "AM/PM", "am/pm", "A/P", "a/p",
    "YYYY", "YY", "MMMM", "MMM", "MM", "M", "DDDD", "DDD", "DD", "D",
    "HH", "H", "SS", "S", "GENERAL",
}


def _auto_quote_literal_text(number_format: str) -> str:
    """Finds runs of letters not already inside quotes and not a known
    date/time/format token, and wraps them in double quotes."""
    if '"' in number_format:
        return number_format  # already has quoting somewhere - don't guess, leave it

    def _wrap(match):
        word = match.group(0)
        if word.upper() in {t.upper() for t in _FORMAT_TOKENS}:
            return word
        return f'"{word}"'

    return re.sub(r"[A-Za-z]+", _wrap, number_format)


def run(sheet_name: str, cell_range: str, bold: bool = False,
        number_format: str = None, fill_color: str = None):
    wb = get_active_workbook()
    sheet = wb.sheets[sheet_name]
    rng = sheet.range(cell_range)

    if bold:
        rng.font.bold = True

    format_error = None
    if number_format:
        fixed_format = _auto_quote_literal_text(number_format)
        try:
            rng.number_format = fixed_format
            number_format = fixed_format  # reflect what was actually applied
        except Exception as e:
            format_error = str(e)

    if fill_color:
        rng.color = hex_to_rgb(fill_color)
    wb.save()

    verified, notes = True, []
    if bold and not rng.font.bold:
        verified, notes = False, notes + ["bold did not apply"]
    if number_format:
        if format_error:
            verified, notes = False, notes + [f"number format rejected by Excel even after auto-quoting: {format_error}"]
        elif rng.number_format != number_format:
            verified, notes = False, notes + ["number format did not apply as expected"]

    return {
        "sheet": sheet_name, "range": cell_range, "bold": bold,
        "number_format": number_format, "fill_color": fill_color,
        "status": "formatted", "verified": verified,
        "verification_note": "Confirmed formatting applied." if verified else f"WARNING: {', '.join(notes)}",
    }
