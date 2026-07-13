import type {
  CellStyle,
  SpreadsheetCell,
  SpreadsheetSheet,
  SpreadsheetWorkbook,
  SupportedWorkbookFileType,
} from './types';

export const MAX_WORKBOOK_BYTES = 50 * 1024 * 1024;

export function createDefaultCellStyle(): CellStyle {
  return {
    bold: false,
    italic: false,
    underline: false,
    align: 'left',
    wrap: false,
    backgroundColor: '#FFFFFF',
    textColor: '#001E2B',
    numberFormat: 'general',
  };
}

export function createBlankCell(value = ''): SpreadsheetCell {
  return {
    value,
    style: createDefaultCellStyle(),
  };
}

export function columnName(index: number): string {
  let current = index + 1;
  let result = '';

  while (current > 0) {
    const remainder = (current - 1) % 26;
    result = String.fromCharCode(65 + remainder) + result;
    current = Math.floor((current - 1) / 26);
  }

  return result;
}

export function cellRef(rowIndex: number, columnIndex: number): string {
  return `${columnName(columnIndex)}${rowIndex + 1}`;
}

export function createSheet(
  name: string,
  rows: number,
  columns: number,
  cells?: Record<string, SpreadsheetCell>,
): SpreadsheetSheet {
  return {
    id: crypto.randomUUID(),
    name,
    rowCount: rows,
    columnCount: columns,
    frozenRows: 1,
    cells: cells ?? {},
  };
}

export function createSampleWorkbook(): SpreadsheetWorkbook {
  const sheets = [
    createSheet(
      'Sales',
      14,
      6,
      {
        A1: createBlankCell('Region'),
        B1: createBlankCell('Rep'),
        C1: createBlankCell('Product'),
        D1: createBlankCell('Units'),
        E1: createBlankCell('Unit Price'),
        F1: createBlankCell('Revenue'),
        A2: createBlankCell('Kigali'),
        B2: createBlankCell('Aline'),
        C2: createBlankCell('Starter'),
        D2: createBlankCell('24'),
        E2: createBlankCell('42'),
        F2: createBlankCell('1008'),
        A3: createBlankCell('Kigali'),
        B3: createBlankCell('Blaise'),
        C3: createBlankCell('Growth'),
        D3: createBlankCell('30'),
        E3: createBlankCell('64'),
        F3: createBlankCell('1920'),
        A4: createBlankCell('Nairobi'),
        B4: createBlankCell('Lilian'),
        C4: createBlankCell('Growth'),
        D4: createBlankCell('18'),
        E4: createBlankCell('64'),
        F4: createBlankCell('1152'),
        A5: createBlankCell('Mombasa'),
        B5: createBlankCell('Yves'),
        C5: createBlankCell('Enterprise'),
        D5: createBlankCell('8'),
        E5: createBlankCell('140'),
        F5: createBlankCell('1120'),
        A6: createBlankCell('Kampala'),
        B6: createBlankCell('Mina'),
        C6: createBlankCell('Starter'),
        D6: createBlankCell('41'),
        E6: createBlankCell('42'),
        F6: createBlankCell('1722'),
      },
    ),
    createSheet(
      'Customers',
      12,
      5,
      {
        A1: createBlankCell('Customer'),
        B1: createBlankCell('District'),
        C1: createBlankCell('Plan'),
        D1: createBlankCell('Last Order'),
        E1: createBlankCell('Status'),
        A2: createBlankCell('Acme Ltd'),
        B2: createBlankCell('Kigali'),
        C2: createBlankCell('Growth'),
        D2: createBlankCell('2026-07-01'),
        E2: createBlankCell('Active'),
      },
    ),
  ];

  return {
    fileName: 'sample-workbook.xlsx',
    fileType: 'sample',
    sheets,
    activeSheetId: sheets[0].id,
  };
}

export function getActiveSheet(workbook: SpreadsheetWorkbook): SpreadsheetSheet {
  const sheet = workbook.sheets.find((item) => item.id === workbook.activeSheetId);
  return sheet ?? workbook.sheets[0];
}

export function countFilledCells(sheet: SpreadsheetSheet): number {
  return Object.values(sheet.cells).filter((cell) => cell.value.trim().length > 0 || cell.formula).length;
}

export function getCell(sheet: SpreadsheetSheet, ref: string): SpreadsheetCell {
  return sheet.cells[ref] ?? createBlankCell();
}

export function setCell(
  sheet: SpreadsheetSheet,
  ref: string,
  nextValue: string,
  formula?: string,
): SpreadsheetSheet {
  const cells = { ...sheet.cells };
  cells[ref] = {
    value: nextValue,
    formula: formula?.trim() ? formula.trim() : undefined,
    style: cells[ref]?.style ?? createDefaultCellStyle(),
  };

  const columnMatch = /([A-Z]+)(\d+)/.exec(ref);
  const rowIndex = columnMatch ? Number(columnMatch[2]) : sheet.rowCount;
  const columnLabel = columnMatch ? columnMatch[1] : 'A';
  const updatedRowCount = Math.max(sheet.rowCount, rowIndex);
  const updatedColumnCount = Math.max(sheet.columnCount, columnIndexFromLabel(columnLabel) + 1);

  return {
    ...sheet,
    rowCount: updatedRowCount,
    columnCount: updatedColumnCount,
    cells,
  };
}

export function columnIndexFromLabel(label: string): number {
  return label.split('').reduce((index, char) => index * 26 + (char.charCodeAt(0) - 64), 0) - 1;
}

export function cloneWorkbook(workbook: SpreadsheetWorkbook): SpreadsheetWorkbook {
  return {
    ...workbook,
    sheets: workbook.sheets.map((sheet) => ({
      ...sheet,
      cells: Object.fromEntries(
        Object.entries(sheet.cells).map(([ref, cell]) => [ref, { ...cell, style: { ...cell.style } }]),
      ),
    })),
  };
}

export function workbookLabel(fileName: string): string {
  return fileName.replace(/\.(xlsx|csv)$/i, '');
}

export function supportedExtension(filePath: string): SupportedWorkbookFileType | null {
  if (/\.xlsx$/i.test(filePath)) {
    return 'xlsx';
  }

  if (/\.csv$/i.test(filePath)) {
    return 'csv';
  }

  return null;
}
