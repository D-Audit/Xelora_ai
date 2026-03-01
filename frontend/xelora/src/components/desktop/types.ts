export type DesktopView =
  | 'home'
  | 'workbooks'
  | 'tasks'
  | 'workflows'
  | 'reports'
  | 'history'
  | 'templates'
  | 'notifications'
  | 'settings';

export type TaskStatus =
  | 'draft'
  | 'running'
  | 'awaiting_approval'
  | 'paused'
  | 'completed'
  | 'completed_with_warnings'
  | 'failed'
  | 'cancelled';

export type WorkspaceMode =
  | 'welcome'
  | 'task_thread'
  | 'workflow_review'
  | 'approval_review'
  | 'spreadsheet'
  | 'data_clean_compare'
  | 'report_result'
  | 'settings_panel';

export interface TaskStep {
  id: string;
  order: number;
  name: string;
  description: string;
  status: 'pending' | 'running' | 'done' | 'skipped' | 'failed';
  requiresApproval: boolean;
  details?: string[];
  progress?: { current: number; total: number; label: string };
}

export interface TaskMessage {
  id: string;
  role: 'user' | 'xelora' | 'system';
  content: string;
  timestamp: string;
  steps?: TaskStep[];
  approvalRequest?: ApprovalRequest;
  resultSummary?: string;
}

export interface ApprovalRequest {
  heading: string;
  reason: string;
  worksheet: string;
  affectedRows: number;
  preview: { before: string; after: string }[];
  safetyNote: string;
}

export interface DesktopTask {
  id: string;
  title: string;
  workbook: string;
  status: TaskStatus;
  createdAt: string;
  updatedAt: string;
  messages: TaskMessage[];
  isPinned?: boolean;
  currentStepIndex?: number;
}

export interface WorkbookItem {
  id: string;
  name: string;
  path: string;
  lastOpened: string;
  rows?: number;
  sheets?: string[];
  isPinned?: boolean;
  source: 'local' | 'cloud';
}
