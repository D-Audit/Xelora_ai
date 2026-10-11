import type { DesktopTask, WorkbookItem } from '@/components/desktop/types';

export const mockDesktopTasks: DesktopTask[] = [
  {
    id: 'dt-1',
    title: 'July Sales Cleanup',
    workbook: 'Sales_Q3_2026.xlsx',
    status: 'running',
    createdAt: '2026-07-24T08:00:00Z',
    updatedAt: '2026-07-24T08:22:00Z',
    isPinned: true,
    currentStepIndex: 2,
    messages: [
      {
        id: 'm1',
        role: 'user',
        content: 'Clean this sales workbook and create a report by district.',
        timestamp: '2026-07-24T08:00:00Z',
      },
      {
        id: 'm2',
        role: 'xelora',
        content: 'I inspected the workbook and found 1,248 rows across three worksheets.',
        timestamp: '2026-07-24T08:00:30Z',
        steps: [
          { id: 's1', order: 1, name: 'Analyse workbook', description: 'Verify sheets, headers and data types.', status: 'done', requiresApproval: false, details: ['3 worksheets found', 'Required columns confirmed', '1,248 total rows'] },
          { id: 's2', order: 2, name: 'Remove duplicates', description: 'Seven probable duplicate rows detected.', status: 'done', requiresApproval: true, details: ['7 duplicate rows removed', 'Keyed on Date + Region + Product'] },
          { id: 's3', order: 3, name: 'Standardise district names', description: 'Unify spelling and capitalisation.', status: 'running', requiresApproval: false, progress: { current: 860, total: 1248, label: 'Processing rows' } },
          { id: 's4', order: 4, name: 'Add Total Sales', description: 'Formula: Units Sold × Unit Price', status: 'pending', requiresApproval: false },
          { id: 's5', order: 5, name: 'Create summary sheet', description: 'Group sales by district.', status: 'pending', requiresApproval: true },
          { id: 's6', order: 6, name: 'Generate chart', description: 'Compare district totals.', status: 'pending', requiresApproval: false },
        ],
      },
    ],
  },
  {
    id: 'dt-2',
    title: 'Payroll Report',
    workbook: 'Payroll_June_2026.xlsx',
    status: 'awaiting_approval',
    createdAt: '2026-07-23T14:00:00Z',
    updatedAt: '2026-07-23T14:18:00Z',
    currentStepIndex: 1,
    messages: [
      { id: 'm3', role: 'user', content: 'Validate payroll entries and flag anomalies.', timestamp: '2026-07-23T14:00:00Z' },
      {
        id: 'm4',
        role: 'xelora',
        content: 'Step 2 requires your approval before continuing.',
        timestamp: '2026-07-23T14:18:00Z',
        approvalRequest: {
          heading: 'Review 2 salary anomalies before continuing',
          reason: 'Two salary values exceed 3× the department average. Confirm they are correct before the net-pay formula runs.',
          worksheet: 'Payroll',
          affectedRows: 2,
          preview: [
            { before: 'Row 48 — Base Salary: $12,000', after: 'Flag as anomaly — awaiting review' },
            { before: 'Row 91 — Base Salary: $18,500', after: 'Flag as anomaly — awaiting review' },
          ],
          safetyNote: 'Approving will continue without changing these values. Xelora will note them in the output.',
        },
        steps: [
          { id: 's7', order: 1, name: 'Analyse payroll structure', description: '312 records, 18 columns found.', status: 'done', requiresApproval: false },
          { id: 's8', order: 2, name: 'Check salary anomalies', description: '2 anomalies found.', status: 'running', requiresApproval: true },
          { id: 's9', order: 3, name: 'Calculate net pay', description: 'Formula: Base Salary − Deductions', status: 'pending', requiresApproval: false },
          { id: 's10', order: 4, name: 'Export reviewed file', description: 'Save as XLSX.', status: 'pending', requiresApproval: false },
        ],
      },
    ],
  },
  {
    id: 'dt-3',
    title: 'Expense Summary',
    workbook: 'Expenses_Q2.xlsx',
    status: 'completed',
    createdAt: '2026-07-22T10:00:00Z',
    updatedAt: '2026-07-22T10:34:00Z',
    messages: [
      { id: 'm5', role: 'user', content: 'Summarise expenses by category and export.', timestamp: '2026-07-22T10:00:00Z' },
      { id: 'm6', role: 'xelora', content: 'All 5 steps completed. The summary sheet and chart are ready.', timestamp: '2026-07-22T10:34:00Z', resultSummary: '890 rows processed · 12 categories · Summary sheet created · Chart exported' },
    ],
  },
];

export const mockDesktopWorkbooks: WorkbookItem[] = [
  { id: 'wb-1', name: 'Sales_Q3_2026.xlsx', path: 'C:/Users/Liliane/Documents/Sales_Q3_2026.xlsx', lastOpened: '2026-07-24T08:00:00Z', rows: 1248, sheets: ['Sales', 'Returns', 'Targets'], isPinned: true, source: 'local' },
  { id: 'wb-2', name: 'Payroll_June_2026.xlsx', path: 'C:/Users/Liliane/Documents/Payroll_June_2026.xlsx', lastOpened: '2026-07-23T14:00:00Z', rows: 312, sheets: ['Payroll', 'Deductions'], source: 'local' },
  { id: 'wb-3', name: 'Expenses_Q2.xlsx', path: 'C:/Users/Liliane/Documents/Expenses_Q2.xlsx', lastOpened: '2026-07-22T10:00:00Z', rows: 890, sheets: ['Expenses'], source: 'local' },
  { id: 'wb-4', name: 'Customer_Data_EU.xlsx', path: 'xelora-cloud://files/Customer_Data_EU.xlsx', lastOpened: '2026-07-20T11:00:00Z', rows: 8921, sheets: ['Customers', 'Orders'], source: 'cloud' },
];
