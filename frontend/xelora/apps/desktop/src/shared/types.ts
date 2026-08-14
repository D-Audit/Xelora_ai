export type SupportedWorkbookFileType = 'xlsx' | 'csv' | 'sample';

export interface AppInfo {
  name: string;
  productName: string;
  version: string;
  executableName: string;
  appId: string;
  userDataPath: string;
  releaseChannel: string;
  updateServerUrl: string;
}

export interface DesktopNotification {
  title: string;
  body: string;
  silent?: boolean;
}

export interface RecentFile {
  filePath: string;
  fileName: string;
  fileType: string;
  sizeBytes: number;
  lastOpenedAt: string;
  exists: boolean;
}

export interface CellStyle {
  bold: boolean;
  italic: boolean;
  underline: boolean;
  align: 'left' | 'center' | 'right';
  wrap: boolean;
  backgroundColor: string;
  textColor: string;
  numberFormat: 'general' | 'currency' | 'percentage' | 'date' | 'decimal';
}

export interface SpreadsheetCell {
  value: string;
  formula?: string;
  style: CellStyle;
}

export interface SpreadsheetSheet {
  id: string;
  name: string;
  rowCount: number;
  columnCount: number;
  frozenRows: number;
  cells: Record<string, SpreadsheetCell>;
}

export interface SpreadsheetWorkbook {
  filePath?: string;
  fileName: string;
  fileType: SupportedWorkbookFileType;
  sheets: SpreadsheetSheet[];
  activeSheetId: string;
  lastSavedAt?: string;
}

export interface OpenWorkbookResult {
  workbook: SpreadsheetWorkbook;
  recentFile: RecentFile;
}

export interface SaveWorkbookRequest {
  workbook: SpreadsheetWorkbook;
  filePath?: string;
  overwrite?: boolean;
}

export interface SaveResult {
  filePath: string;
  fileName: string;
  savedAt: string;
  sizeBytes: number;
}

export interface BackupRequest {
  sourceFilePath: string;
  workbookName: string;
}

export interface BackupResult {
  backupPath: string;
  createdAt: string;
}

export interface UserProfile {
  id: string;
  name: string;
  email: string;
  role: string;
}

export interface SessionState {
  user: UserProfile | null;
  rememberMe: boolean;
  token: string;
  createdAt: string;
  expiresAt: string;
}

export interface LoginRequest {
  email: string;
  password: string;
  rememberMe: boolean;
}

export interface LoginResult {
  user: UserProfile;
  token: string;
  rememberMe: boolean;
}

export interface GeneralSettings {
  language: string;
  theme: 'light' | 'system';
  startPage: 'welcome' | 'dashboard' | 'last-workbook';
  restorePreviousSession: boolean;
  defaultSaveFolder: string;
}

export interface FileSettings {
  autoSave: boolean;
  autoSaveIntervalMinutes: number;
  createBackupBeforeAutomation: boolean;
  recentFilesLimit: number;
}

export interface AiSettings {
  explanationLevel: 'brief' | 'balanced' | 'detailed';
  approvalLevel: 'low' | 'medium' | 'high';
  defaultContext: 'selected-cell' | 'selected-range' | 'worksheet' | 'workbook';
  destructiveActionConfirmation: boolean;
}

export interface PrivacySettings {
  localProcessingPreference: boolean;
  cloudProcessingPlaceholder: boolean;
  clearRecentFilesOnSignOut: boolean;
  clearLocalHistoryOnSignOut: boolean;
}

export interface ApplicationSettings {
  version: string;
  checkForUpdates: boolean;
  releaseChannel: 'stable' | 'beta';
  showLogsPath: boolean;
  resetApplication: boolean;
}

export type WorkflowStatus =
  | 'Pending'
  | 'Running'
  | 'Completed'
  | 'Needs approval'
  | 'Warning'
  | 'Failed'
  | 'Skipped'
  | 'Cancelled';

export interface WorkflowStep {
  id: string;
  label: string;
  description: string;
  status: WorkflowStatus;
  requiresApproval?: boolean;
  affectedRows?: number;
  affectedCells?: number;
}

export interface WorkflowRun {
  id: string;
  status: WorkflowStatus;
  currentStepIndex: number;
  progress: number;
  creditsUsed: number;
  rowsAffected: number;
  cellsAffected: number;
  steps: WorkflowStep[];
}

export interface DesktopSettings {
  general: GeneralSettings;
  files: FileSettings;
  ai: AiSettings;
  privacy: PrivacySettings;
  application: ApplicationSettings;
}

export const defaultDesktopSettings: DesktopSettings = {
  general: {
    language: 'English',
    theme: 'light',
    startPage: 'dashboard',
    restorePreviousSession: true,
    defaultSaveFolder: '',
  },
  files: {
    autoSave: true,
    autoSaveIntervalMinutes: 2,
    createBackupBeforeAutomation: true,
    recentFilesLimit: 12,
  },
  ai: {
    explanationLevel: 'balanced',
    approvalLevel: 'medium',
    defaultContext: 'selected-range',
    destructiveActionConfirmation: true,
  },
  privacy: {
    localProcessingPreference: true,
    cloudProcessingPlaceholder: true,
    clearRecentFilesOnSignOut: false,
    clearLocalHistoryOnSignOut: false,
  },
  application: {
    version: '0.1.0',
    checkForUpdates: true,
    releaseChannel: 'stable',
    showLogsPath: false,
    resetApplication: false,
  },
};

export interface XeloraDesktopAPI {
  openWorkbook(): Promise<OpenWorkbookResult | null>;
  openCsv(): Promise<OpenWorkbookResult | null>;
  saveWorkbook(request: SaveWorkbookRequest): Promise<SaveResult | null>;
  saveWorkbookAs(request: SaveWorkbookRequest): Promise<SaveResult | null>;
  createBackup(request: BackupRequest): Promise<BackupResult>;
  getRecentFiles(): Promise<RecentFile[]>;
  removeRecentFile(filePath: string): Promise<void>;
  getSettings(): Promise<DesktopSettings>;
  updateSettings(settings: Partial<DesktopSettings>): Promise<DesktopSettings>;
  getAppInfo(): Promise<AppInfo>;
  showNotification(notification: DesktopNotification): Promise<void>;
  openExternalUrl(url: string): Promise<void>;
  onMenuAction(callback: (action: string) => void): () => void;
  onCloseSaveRequest(callback: () => void): () => void;
  onProtocolCallback(callback: (url: string) => void): () => void;
  setUnsavedChanges(isDirty: boolean): Promise<void>;
  confirmCloseAfterSave(): Promise<void>;
  login(request: LoginRequest): Promise<LoginResult>;
  getSession(): Promise<SessionState | null>;
  logout(): Promise<void>;
  openRecentFile(filePath: string): Promise<OpenWorkbookResult | null>;
  setFloatingMode(enabled: boolean): Promise<boolean>;
  getFloatingMode(): Promise<boolean>;
  onFloatingModeChange(callback: (enabled: boolean) => void): () => void;
}

declare global {
  interface Window {
    xelora: XeloraDesktopAPI;
  }
}
