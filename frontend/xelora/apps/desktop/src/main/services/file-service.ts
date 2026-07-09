import fs from 'node:fs/promises';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
import * as XLSX from 'xlsx';
import type {
  BackupResult,
  OpenWorkbookResult,
  RecentFile,
  SaveResult,
  SpreadsheetCell,
  SpreadsheetSheet,
  SpreadsheetWorkbook,
  SupportedWorkbookFileType,
} from '../../shared/types';
import { MAX_WORKBOOK_BYTES, cellRef, columnName, createBlankCell, supportedExtension } from '../../shared/workbook';

const MAX_UPLOAD_BYTES = MAX_WORKBOOK_BYTES;

function createRecentFile(filePath: string, fileType: string, sizeBytes: number): RecentFile {
  return {
    filePath,
    fileName: path.basename(filePath),
    fileType,
    sizeBytes,
    lastOpenedAt: new Date().toISOString(),
    exists: true,
  };
}

function sheetToModel(sheetName: string, sheetData: XLSX.WorkSheet): SpreadsheetSheet {
  const aoa = XLSX.utils.sheet_to_json(sheetData, { header: 1, blankrows: true, defval: '' }) as Array<Array<string | number | boolean>>;
  const rowCount = Math.max(aoa.length, 1);
  const columnCount = aoa.reduce((max, row) => Math.max(max, row.length), 0);
  const cells: Record<string, SpreadsheetCell> = {};

  aoa.forEach((row, rowIndex) => {
    row.forEach((value, columnIndex) => {
      const stringValue = value === null || value === undefined ? '' : String(value);
      if (stringValue.length === 0) {
        return;
      }

      cells[cellRef(rowIndex, columnIndex)] = createBlankCell(stringValue);
    });
  });

  return {
    id: randomUUID(),
    name: sheetName,
    rowCount,
    columnCount: Math.max(columnCount, 1),
    frozenRows: 1,
    cells,
  };
}

function modelToSheet(sheet: SpreadsheetSheet): XLSX.WorkSheet {
  const matrix: string[][] = Array.from({ length: sheet.rowCount }, () => Array.from({ length: sheet.columnCount }, () => ''));

  for (let rowIndex = 0; rowIndex < sheet.rowCount; rowIndex += 1) {
    for (let columnIndex = 0; columnIndex < sheet.columnCount; columnIndex += 1) {
      const ref = `${columnName(columnIndex)}${rowIndex + 1}`;
      const cell = sheet.cells[ref];
      matrix[rowIndex][columnIndex] = cell?.formula ? cell.value || `=${cell.formula}` : cell?.value ?? '';
    }
  }

  const worksheet = XLSX.utils.aoa_to_sheet(matrix);

  for (const [ref, cell] of Object.entries(sheet.cells)) {
    if (!cell.formula) {
      continue;
    }

    worksheet[ref] = {
      t: 'n',
      f: cell.formula,
      v: Number(cell.value) || 0,
    } as XLSX.CellObject;
  }

  return worksheet;
}

function detectWorkbookType(filePath: string): SupportedWorkbookFileType {
  const extension = supportedExtension(filePath);
  if (!extension) {
    throw new Error('Unsupported file type. Xelora only opens .xlsx and .csv files.');
  }
  return extension;
}

async function validateFileForOpen(filePath: string): Promise<{ sizeBytes: number; fileType: SupportedWorkbookFileType }> {
  const stats = await fs.stat(filePath);
  if (!stats.isFile()) {
    throw new Error('The selected item is not a file.');
  }

  if (stats.size > MAX_UPLOAD_BYTES) {
    throw new Error('This file is too large to open in Xelora.');
  }

  return {
    sizeBytes: stats.size,
    fileType: detectWorkbookType(filePath),
  };
}

export async function readSpreadsheet(filePath: string): Promise<OpenWorkbookResult> {
  const { sizeBytes, fileType } = await validateFileForOpen(filePath);

  try {
    const workbookData = fileType === 'csv'
      ? XLSX.read(await fs.readFile(filePath, 'utf-8'), { type: 'string' })
      : XLSX.readFile(filePath, { cellFormula: true });

    const sheets = workbookData.SheetNames.map((sheetName) => sheetToModel(sheetName, workbookData.Sheets[sheetName] as XLSX.WorkSheet));

    if (sheets.length === 0) {
      throw new Error('The workbook does not contain any worksheets.');
    }

    return {
      workbook: {
        filePath,
        fileName: path.basename(filePath),
        fileType,
        sheets,
        activeSheetId: sheets[0].id,
      },
      recentFile: createRecentFile(filePath, fileType, sizeBytes),
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unable to open the selected file.';

    if (/password/i.test(message)) {
      throw new Error('This workbook appears to be password-protected.');
    }

    if (/encrypted|unsupported zip/i.test(message)) {
      throw new Error('This workbook appears to be password-protected or encrypted.');
    }

    if (/Invalid|Parse|Corrupt|damaged/i.test(message)) {
      throw new Error('The workbook is damaged or could not be parsed.');
    }

    throw new Error(message);
  }
}

export async function saveSpreadsheet(
  workbook: SpreadsheetWorkbook,
  targetPath: string,
): Promise<SaveResult> {
  const type = detectWorkbookType(targetPath);
  const writer = XLSX.utils.book_new();

  for (const sheet of workbook.sheets) {
    XLSX.utils.book_append_sheet(writer, modelToSheet(sheet), sheet.name.slice(0, 31));
  }

  if (type === 'csv') {
    const firstSheet = workbook.sheets[0];
    const worksheet = modelToSheet(firstSheet);
    const csv = XLSX.utils.sheet_to_csv(worksheet);
    await fs.writeFile(targetPath, csv, 'utf-8');
  } else {
    XLSX.writeFile(writer, targetPath, { compression: true });
  }

  const stats = await fs.stat(targetPath);
  return {
    filePath: targetPath,
    fileName: path.basename(targetPath),
    savedAt: new Date().toISOString(),
    sizeBytes: stats.size,
  };
}

export async function createBackupCopy(sourceFilePath: string, workbookName: string): Promise<BackupResult> {
  const backupsDir = path.join(path.dirname(sourceFilePath), '.xelora-backups');
  await fs.mkdir(backupsDir, { recursive: true });
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  const backupPath = path.join(backupsDir, `${timestamp}-${workbookName}`);
  await fs.copyFile(sourceFilePath, backupPath);

  return {
    backupPath,
    createdAt: new Date().toISOString(),
  };
}

export async function fileExists(filePath: string): Promise<boolean> {
  try {
    const stats = await fs.stat(filePath);
    return stats.isFile();
  } catch {
    return false;
  }
}

export async function fileSize(filePath: string): Promise<number> {
  const stats = await fs.stat(filePath);
  return stats.size;
}
