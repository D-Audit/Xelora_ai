import { createSampleWorkbook } from '../../shared/workbook';
import type { SpreadsheetWorkbook, WorkflowRun, WorkflowStep } from '../../shared/types';

export function createBlankWorkbook(): SpreadsheetWorkbook {
  return {
    fileName: 'Untitled Workbook.xlsx',
    fileType: 'sample',
    sheets: createSampleWorkbook().sheets.slice(0, 1),
    activeSheetId: createSampleWorkbook().activeSheetId,
  };
}

export function createWorkflowSteps(): WorkflowStep[] {
  return [
    {
      id: 'analyse',
      label: 'Analyse the workbook',
      description: 'Inspect sheets, values, and headers.',
      status: 'Pending',
    },
    {
      id: 'columns',
      label: 'Confirm required columns',
      description: 'Make sure the target columns exist.',
      status: 'Pending',
    },
    {
      id: 'clean',
      label: 'Remove duplicate rows',
      description: 'Remove repeated rows from the selected range.',
      status: 'Pending',
      requiresApproval: true,
      affectedRows: 0,
      affectedCells: 0,
    },
    {
      id: 'standardize',
      label: 'Standardise text values',
      description: 'Trim spaces and normalise text casing.',
      status: 'Pending',
    },
    {
      id: 'formula',
      label: 'Add formulas',
      description: 'Insert calculated fields into the sheet.',
      status: 'Pending',
      requiresApproval: true,
    },
    {
      id: 'summary',
      label: 'Create summary sheet',
      description: 'Build a summary worksheet from the dataset.',
      status: 'Pending',
    },
    {
      id: 'chart',
      label: 'Generate chart',
      description: 'Create a report chart for management review.',
      status: 'Pending',
    },
    {
      id: 'export',
      label: 'Export cleaned workbook',
      description: 'Save the final workbook copy locally.',
      status: 'Pending',
      requiresApproval: true,
    },
  ];
}

export function createWorkflowRun(): WorkflowRun {
  const steps = createWorkflowSteps();
  return {
    id: crypto.randomUUID(),
    status: 'Pending',
    currentStepIndex: 0,
    progress: 0,
    creditsUsed: 0,
    rowsAffected: 0,
    cellsAffected: 0,
    steps,
  };
}

export function mockAiResponse(prompt: string): string {
  const normalized = prompt.trim().toLowerCase();

  if (normalized.includes('explain') && normalized.includes('formula')) {
    return 'Adds the values in column F when the corresponding value in column B is Kigali.';
  }

  if (normalized.includes('remove duplicate')) {
    return 'I would review the selected range, identify duplicate rows by the key columns, and keep the first unique entry.';
  }

  if (normalized.includes('summary')) {
    return 'I would generate a concise summary sheet with totals, averages, and a chart-ready dataset.';
  }

  if (normalized.includes('chart')) {
    return 'I can build a bar chart for totals by category and add a trend line if the data supports it.';
  }

  return 'I can help clean the workbook, explain formulas, generate summaries, and prepare mock workflows without sending data to the cloud.';
}
