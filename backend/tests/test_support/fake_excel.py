"""A tiny in-memory stand-in for the xlwings objects some skills/tools use.

Only for unit tests on machines without Excel. It models values, formulas and
number formats on a grid; it does not calculate formulas or emulate COM.
"""
from __future__ import annotations

import re
from datetime import datetime


def _col_number(letters: str) -> int:
    number = 0
    for ch in letters:
        number = number * 26 + ord(ch.upper()) - 64
    return number


def _col_letters(number: int) -> str:
    letters = ""
    while number:
        number, rem = divmod(number - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def _parse(ref: str) -> tuple[int, int, int, int]:
    parts = ref.replace("$", "").upper().split(":")
    coords = []
    for part in parts:
        match = re.fullmatch(r"([A-Z]+)(\d+)", part)
        coords.append((int(match.group(2)), _col_number(match.group(1))))
    (r1, c1), (r2, c2) = coords[0], coords[-1]
    return r1, c1, r2 - r1 + 1, c2 - c1 + 1


class _Cells:
    def __init__(self):
        self.values: dict[tuple[int, int], object] = {}
        self.formulas: dict[tuple[int, int], str] = {}
        self.formats: dict[tuple[int, int], str] = {}


class FakeRange:
    def __init__(self, sheet, row, col, rows=1, cols=1, ndim=None):
        self.sheet, self.row, self.column, self._rows, self._cols, self._ndim = sheet, row, col, rows, cols, ndim

    # geometry
    @property
    def shape(self):
        return (self._rows, self._cols)

    @property
    def address(self):
        start = f"${_col_letters(self.column)}${self.row}"
        if self.shape == (1, 1):
            return start
        return f"{start}:${_col_letters(self.column + self._cols - 1)}${self.row + self._rows - 1}"

    @property
    def last_cell(self):
        return FakeRange(self.sheet, self.row + self._rows - 1, self.column + self._cols - 1)

    def resize(self, rows, cols):
        return FakeRange(self.sheet, self.row, self.column, rows, cols)

    def offset(self, rows, cols):
        return FakeRange(self.sheet, self.row + rows, self.column + cols, self._rows, self._cols)

    def options(self, ndim=None, **_kwargs):
        return FakeRange(self.sheet, self.row, self.column, self._rows, self._cols, ndim)

    def __getitem__(self, key):
        r, c = key
        return FakeRange(self.sheet, self.row + r, self.column + c)

    # data
    def _grid(self, store):
        grid = [[store.get((self.row + r, self.column + c)) for c in range(self._cols)] for r in range(self._rows)]
        if self._ndim == 2:
            return grid
        if self._rows == 1 and self._cols == 1:
            return grid[0][0]
        if self._rows == 1:
            return grid[0]
        if self._cols == 1:
            return [row[0] for row in grid]
        return grid

    @property
    def value(self):
        return self._grid(self.sheet.cells.values)

    @value.setter
    def value(self, data):
        if not isinstance(data, list):
            data = [[data]]
        elif data and not isinstance(data[0], list):
            data = [data]
        for r, row in enumerate(data):
            for c, value in enumerate(row):
                key = (self.row + r, self.column + c)
                if isinstance(value, str) and value.startswith("'"):
                    value = value[1:]  # Excel's text prefix is not part of the value
                self.sheet.cells.values[key] = value
                self.sheet.cells.formulas.pop(key, None)

    @property
    def formula(self):
        grid = [[self.sheet.cells.formulas.get((self.row + r, self.column + c),
                                              self.sheet.cells.values.get((self.row + r, self.column + c)))
                 for c in range(self._cols)] for r in range(self._rows)]
        return grid if self._ndim == 2 or self._rows > 1 or self._cols > 1 else grid[0][0]

    @property
    def number_format(self):
        return self.sheet.cells.formats.get((self.row, self.column), "General")

    def clear(self):
        for r in range(self._rows):
            for c in range(self._cols):
                key = (self.row + r, self.column + c)
                self.sheet.cells.values.pop(key, None)
                self.sheet.cells.formulas.pop(key, None)
                self.sheet.cells.formats.pop(key, None)


class FakeSheet:
    def __init__(self, name):
        self.name, self.cells = name, _Cells()

    def range(self, ref):
        return FakeRange(self, *_parse(ref))


class _Sheets(list):
    def __getitem__(self, key):
        if isinstance(key, str):
            for sheet in self:
                if sheet.name == key:
                    return sheet
            raise KeyError(key)
        return list.__getitem__(self, key)

    def add(self, name, after=None):
        sheet = FakeSheet(name)
        self.append(sheet)
        return sheet


class FakeBook:
    def __init__(self, *sheet_names):
        self.name = "Book1"
        self.sheets = _Sheets(FakeSheet(name) for name in (sheet_names or ("Sheet1",)))
        self.saves = 0

    def save(self):
        self.saves += 1


__all__ = ["FakeBook", "datetime"]
