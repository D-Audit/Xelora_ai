"""
skills/table_style.py
Professional default styling for a block of data written by a skill.

A user who asks Xelora to "put this data in Excel" expects a finished sheet,
not raw values: a clear header, readable number formats, sensible column
widths, and a header row that stays visible while scrolling.  Styling runs
after the data has been written and verified, and every step is best-effort
so a cosmetic failure never turns a correct write into a failed one.
"""

import re
from datetime import date, datetime

HEADER_FILL = (31, 78, 121)      # deep blue
HEADER_FONT = (255, 255, 255)
BORDER_COLOR = (191, 191, 191)
MAX_COLUMN_WIDTH = 50
MIN_COLUMN_WIDTH = 9
SAMPLE_ROWS = 500

DATE_FORMAT = "dd mmm yyyy"
DATETIME_FORMAT = "dd mmm yyyy hh:mm"
MONEY_FORMAT = "#,##0.00"
INTEGER_FORMAT = "#,##0"
DECIMAL_FORMAT = "#,##0.00"
PERCENT_FORMAT = "0.0%"
PLAIN_NUMBER_FORMAT = "0"

_PERCENT_WORDS = re.compile(r"%|percent|pct|rate|margin|share|growth|ratio|conversion|discount", re.I)
_MONEY_WORDS = re.compile(
    r"price|cost|revenue|sales|amount|total|profit|salary|wage|budget|income|expense|fee|"
    r"balance|spend|payment|value|tax|usd|eur|gbp|kes|rwf|ugx|tzs|ngn|zar|\$|€|£",
    re.I,
)
_COUNT_WORDS = re.compile(r"qty|quantity|units|count|orders|items|stock|headcount|visits|clicks", re.I)
_PLAIN_NUMBER_WORDS = re.compile(r"\b(id|year|code|zip|postal|phone|no|number|#|rank|week|month|day)\b", re.I)
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2})?)?$")

# Excel constants.
_XL_CENTER = -4108
_XL_CONTINUOUS = 1
_XL_THIN = 2
_EDGES_AND_INSIDES = (7, 8, 9, 10, 11, 12)  # left, top, bottom, right, inside vertical, inside horizontal


def _bgr(rgb) -> int:
    red, green, blue = rgb
    return red + green * 256 + blue * 65536


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _words(header: str) -> str:
    # "UnitPrice" / "unit_price" -> "Unit Price" so keyword boundaries work.
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", str(header))
    return spaced.replace("_", " ")


def infer_number_format(header: str, values: list) -> str | None:
    """Choose an Excel number format for one column, or None to leave it."""
    present = [value for value in values if value not in (None, "")]
    if not present:
        return None
    if all(isinstance(value, (datetime, date)) or (isinstance(value, str) and _ISO_DATE.match(value))
           for value in present):
        has_time = any(
            (isinstance(value, datetime) and (value.hour or value.minute))
            or (isinstance(value, str) and len(value) > 10)
            for value in present
        )
        return DATETIME_FORMAT if has_time else DATE_FORMAT
    if not all(_is_number(value) for value in present):
        return None
    words = _words(header)
    if _PLAIN_NUMBER_WORDS.search(words) and not _MONEY_WORDS.search(words):
        return PLAIN_NUMBER_FORMAT
    if _PERCENT_WORDS.search(words) and all(abs(value) <= 1.5 for value in present):
        return PERCENT_FORMAT
    if _COUNT_WORDS.search(words) and all(float(value).is_integer() for value in present):
        return INTEGER_FORMAT
    if _MONEY_WORDS.search(words):
        return MONEY_FORMAT
    if all(float(value).is_integer() for value in present):
        return INTEGER_FORMAT
    return DECIMAL_FORMAT


def _try(applied: list, label: str, action) -> None:
    try:
        action()
        applied.append(label)
    except Exception:
        pass


def _set_borders(rng) -> None:
    for index in _EDGES_AND_INSIDES:
        border = rng.api.Borders(index)
        border.LineStyle = _XL_CONTINUOUS
        border.Weight = _XL_THIN
        border.Color = _bgr(BORDER_COLOR)


def _fit_columns(block) -> None:
    block.columns.autofit()
    for column in block.columns:
        width = column.column_width
        if width > MAX_COLUMN_WIDTH:
            column.column_width = MAX_COLUMN_WIDTH
            column.api.WrapText = True
        elif width < MIN_COLUMN_WIDTH:
            column.column_width = MIN_COLUMN_WIDTH


def _freeze_header(sheet, header_row: int) -> None:
    window = sheet.book.app.api.ActiveWindow
    if window.FreezePanes or header_row > 5:
        return
    window.SplitColumn = 0
    window.SplitRow = header_row
    window.FreezePanes = True


def style_data_block(sheet, start, headers: list, rows: list, row_count: int, *, is_table: bool) -> dict:
    """Format a header + data block professionally and report what was done.

    ``rows`` are the written values used to infer number formats; pass an
    empty list when the data was already in the sheet and it is read back
    here instead.  A native Excel Table already has a banded style, so only
    the plain-range case gets an explicit header fill and borders.
    """
    column_count = len(headers)
    applied: list[str] = []
    header = start.resize(1, column_count)
    block = start.resize(1 + row_count, column_count)

    if row_count and not rows:
        try:
            sample = start.offset(1, 0).resize(min(row_count, SAMPLE_ROWS), column_count).value
            rows = sample if isinstance(sample, list) and sample and isinstance(sample[0], list) else [sample]
        except Exception:
            rows = []

    number_formats = {}
    for index, name in enumerate(headers):
        fmt = infer_number_format(name, [row[index] for row in rows[:SAMPLE_ROWS] if index < len(row)])
        if fmt is None or not row_count:
            continue
        column = start.offset(1, index).resize(row_count, 1)
        try:
            column.number_format = fmt
            number_formats[name] = fmt
        except Exception:
            pass
    if number_formats:
        applied.append("number_formats")

    def _header_style():
        header.font.bold = True
        header.api.VerticalAlignment = _XL_CENTER
        if not is_table:
            header.color = HEADER_FILL
            header.font.color = HEADER_FONT
            header.api.HorizontalAlignment = _XL_CENTER
        header.row_height = max(header.row_height or 0, 22)

    _try(applied, "header_style", _header_style)
    if not is_table and row_count:
        _try(applied, "borders", lambda: _set_borders(block))
    _try(applied, "column_widths", lambda: _fit_columns(block))
    _try(applied, "frozen_header", lambda: _freeze_header(sheet, header.row))

    return {"applied": applied, "number_formats": number_formats}
