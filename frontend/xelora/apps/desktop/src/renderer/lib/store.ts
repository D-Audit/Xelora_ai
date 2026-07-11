import { create } from 'zustand';
import type {
  AppInfo,
  DesktopSettings,
  OpenWorkbookResult,
  RecentFile,
  SaveResult,
  SessionState,
  SpreadsheetCell,
  SpreadsheetWorkbook,
  WorkflowRun,
  WorkflowStep,
} from '../../shared/types';
import { cellRef, cloneWorkbook, createBlankCell, createSampleWorkbook, getActiveSheet, setCell } from '../../shared/workbook';
import { createBlankWorkbook, createWorkflowRun, createWorkflowSteps } from './mock';

export type AppScreen = 'welcome' | 'home' | 'workbook' | 'reports' | 'cleaning' | 'settings';
export type PanelMode = 'workflow' | 'ai' | 'reports' | 'cleaning';

interface DesktopState {
  appInfo: AppInfo | null;
  session: SessionState | null;
  settings: DesktopSettings | null;
  recentFiles: RecentFile[];
  workbook: SpreadsheetWorkbook | null;
  screen: AppScreen;
  activePanel: PanelMode;
  selectedCell: string;
  selectedRange: { start: string; end: string } | null;
  formulaInput: string;
  aiPrompt: string;
  aiContext: 'selected-cell' | 'selected-range' | 'worksheet' | 'workbook';
  isOffline: boolean;
  isLoading: boolean;
  dirty: boolean;
  statusMessage: string;
  undoStack: SpreadsheetWorkbook[];
  redoStack: SpreadsheetWorkbook[];
  workflowRun: WorkflowRun;
  workflowSteps: WorkflowStep[];
  lastSaveResult: SaveResult | null;
  setAppInfo: (info: AppInfo) => void;
  setSession: (session: SessionState | null) => void;
  setSettings: (settings: DesktopSettings) => void;
  setRecentFiles: (recentFiles: RecentFile[]) => void;
  setScreen: (screen: AppScreen) => void;
  setPanel: (panel: PanelMode) => void;
  setSelectedCell: (ref: string) => void;
  setSelectedRange: (range: { start: string; end: string } | null) => void;
  setFormulaInput: (value: string) => void;
  setAiPrompt: (value: string) => void;
  setAiContext: (value: DesktopState['aiContext']) => void;
  setOffline: (value: boolean) => void;
  setLoading: (value: boolean) => void;
  setStatusMessage: (value: string) => void;
  setWorkbook: (workbook: SpreadsheetWorkbook | null) => void;
  pushHistory: () => void;
  undo: () => void;
  redo: () => void;
  markDirty: (value: boolean) => Promise<void>;
  initializeFromMain: () => Promise<void>;
  openWorkbook: () => Promise<void>;
  openCsv: () => Promise<void>;
  openRecentFile: (filePath: string) => Promise<void>;
  createBlankWorkbook: () => void;
  createSampleWorkbook: () => void;
  editSelectedCell: (value: string, formula?: string) => Promise<void>;
  updateCellStyle: (patch: Partial<SpreadsheetCell['style']>) => void;
  addWorksheet: () => void;
  renameActiveWorksheet: (name: string) => void;
  duplicateActiveWorksheet: () => void;
  deleteActiveWorksheet: () => void;
  saveWorkbook: (saveAs?: boolean) => Promise<void>;
  createBackup: () => Promise<void>;
  loadSettings: () => Promise<void>;
  togglePanel: (panel: PanelMode) => void;
  runMockWorkflow: () => void;
  applyMockAiPrompt: (prompt: string) => void;
  useSampleWorkbook: () => void;
  selectNextCell: (deltaRow: number, deltaColumn: number) => void;
}

function setActiveCellValue(workbook: SpreadsheetWorkbook, ref: string, value: string, formula?: string): SpreadsheetWorkbook {
  const sheet = getActiveSheet(workbook);
  const nextSheet = setCell(sheet, ref, value, formula);
  return {
    ...workbook,
    sheets: workbook.sheets.map((item) => (item.id === sheet.id ? nextSheet : item)),
  };
}

function updateWorkbookSheet(workbook: SpreadsheetWorkbook, updater: (sheet: SpreadsheetWorkbook['sheets'][number]) => SpreadsheetWorkbook['sheets'][number]): SpreadsheetWorkbook {
  const sheet = getActiveSheet(workbook);
  return {
    ...workbook,
    sheets: workbook.sheets.map((item) => (item.id === sheet.id ? updater(item) : item)),
  };
}

function blankWorkbook(): SpreadsheetWorkbook {
  const sample = createBlankWorkbook();
  return cloneWorkbook(sample);
}

function selectCellAfterMove(ref: string, deltaRow: number, deltaColumn: number): string {
  const match = /^([A-Z]+)(\d+)$/.exec(ref);
  if (!match) {
    return 'A1';
  }

  const label = match[1];
  const rowIndex = Number(match[2]) - 1;
  const nextRow = Math.max(0, rowIndex + deltaRow);
  const nextColumn = Math.max(0, label.split('').reduce((index, char) => index * 26 + (char.charCodeAt(0) - 64), 0) - 1 + deltaColumn);
  return cellRef(nextRow, nextColumn);
}

export const useDesktopStore = create<DesktopState>((set, get) => ({
  appInfo: null,
  session: null,
  settings: null,
  recentFiles: [],
  workbook: null,
  screen: 'welcome',
  activePanel: 'workflow',
  selectedCell: 'A1',
  selectedRange: null,
  formulaInput: '',
  aiPrompt: '',
  aiContext: 'selected-range',
  isOffline: !navigator.onLine,
  isLoading: true,
  dirty: false,
  statusMessage: 'Ready',
  undoStack: [],
  redoStack: [],
  workflowRun: createWorkflowRun(),
  workflowSteps: createWorkflowSteps(),
  lastSaveResult: null,
  setAppInfo: (info) => set({ appInfo: info }),
  setSession: (session) => set({ session, screen: session ? 'home' : 'welcome' }),
  setSettings: (settings) => set({ settings }),
  setRecentFiles: (recentFiles) => set({ recentFiles }),
  setScreen: (screen) => set({ screen }),
  setPanel: (panel) => set({ activePanel: panel }),
  setSelectedCell: (ref) => set((state) => ({
    selectedCell: ref,
    formulaInput: state.workbook ? getActiveSheet(state.workbook).cells[ref]?.formula ?? getActiveSheet(state.workbook).cells[ref]?.value ?? '' : '',
  })),
  setSelectedRange: (range) => set({ selectedRange: range }),
  setFormulaInput: (value) => set({ formulaInput: value }),
  setAiPrompt: (value) => set({ aiPrompt: value }),
  setAiContext: (value) => set({ aiContext: value }),
  setOffline: (value) => set({ isOffline: value }),
  setLoading: (value) => set({ isLoading: value }),
  setStatusMessage: (value) => set({ statusMessage: value }),
  setWorkbook: (workbook) => set(() => ({
    workbook,
    selectedCell: 'A1',
    formulaInput: workbook ? getActiveSheet(workbook).cells.A1?.formula ?? getActiveSheet(workbook).cells.A1?.value ?? '' : '',
    dirty: false,
    undoStack: [],
    redoStack: [],
    screen: workbook ? 'workbook' : get().screen,
  })),
  pushHistory: () => set((state) => ({
    undoStack: state.workbook ? [...state.undoStack, cloneWorkbook(state.workbook)].slice(-20) : state.undoStack,
    redoStack: [],
  })),
  undo: () => set((state) => {
    if (state.undoStack.length === 0 || !state.workbook) {
      return state;
    }

    const previous = state.undoStack[state.undoStack.length - 1];
    return {
      workbook: previous,
      undoStack: state.undoStack.slice(0, -1),
      redoStack: [cloneWorkbook(state.workbook), ...state.redoStack].slice(0, 20),
      dirty: true,
    };
  }),
  redo: () => set((state) => {
    if (state.redoStack.length === 0 || !state.workbook) {
      return state;
    }

    const next = state.redoStack[0];
    return {
      workbook: next,
      redoStack: state.redoStack.slice(1),
      undoStack: [...state.undoStack, cloneWorkbook(state.workbook)].slice(-20),
      dirty: true,
    };
  }),
  markDirty: async (value) => {
    set({ dirty: value });
    await window.xelora.setUnsavedChanges(value);
  },
  initializeFromMain: async () => {
    const [info, session, settings, recentFiles] = await Promise.all([
      window.xelora.getAppInfo(),
      window.xelora.getSession(),
      window.xelora.getSettings(),
      window.xelora.getRecentFiles(),
    ]);

    set({
      appInfo: info,
      session,
      settings,
      recentFiles,
      isLoading: false,
      screen: session ? 'home' : 'welcome',
      aiContext: settings.ai.defaultContext,
    });
  },
  openWorkbook: async () => {
    const result = await window.xelora.openWorkbook();
    if (!result) {
      return;
    }

    get().setWorkbook(result.workbook);
    set({ recentFiles: [result.recentFile, ...get().recentFiles.filter((item) => item.filePath !== result.recentFile.filePath)] });
    await get().markDirty(false);
    set({ statusMessage: `Opened ${result.workbook.fileName}` });
  },
  openCsv: async () => {
    const result = await window.xelora.openCsv();
    if (!result) {
      return;
    }

    get().setWorkbook(result.workbook);
    set({ recentFiles: [result.recentFile, ...get().recentFiles.filter((item) => item.filePath !== result.recentFile.filePath)] });
    await get().markDirty(false);
    set({ statusMessage: `Opened ${result.workbook.fileName}` });
  },
  openRecentFile: async (filePath) => {
    const result = await window.xelora.openRecentFile(filePath);
    if (!result) {
      return;
    }

    get().setWorkbook(result.workbook);
    set({ recentFiles: [result.recentFile, ...get().recentFiles.filter((item) => item.filePath !== result.recentFile.filePath)] });
    await get().markDirty(false);
  },
  createBlankWorkbook: () => {
    set({ workbook: blankWorkbook(), screen: 'workbook', dirty: true, statusMessage: 'Created a new workbook' });
    void window.xelora.setUnsavedChanges(true);
  },
  createSampleWorkbook: () => {
    const workbook = createSampleWorkbook();
    set({ workbook, screen: 'workbook', dirty: false, statusMessage: 'Opened sample workbook' });
    void window.xelora.setUnsavedChanges(false);
  },
  editSelectedCell: async (value, formula) => {
    const state = get();
    if (!state.workbook) {
      return;
    }

    const snapshot = cloneWorkbook(state.workbook);
    const nextWorkbook = setActiveCellValue(state.workbook, state.selectedCell, value, formula);
    set({
      workbook: nextWorkbook,
      undoStack: [...state.undoStack, snapshot].slice(-20),
      redoStack: [],
      dirty: true,
      statusMessage: `Updated ${state.selectedCell}`,
      formulaInput: formula ?? value,
    });
    await window.xelora.setUnsavedChanges(true);
  },
  updateCellStyle: (patch) => {
    const state = get();
    if (!state.workbook) {
      return;
    }

    const sheet = getActiveSheet(state.workbook);
    const existing = sheet.cells[state.selectedCell] ?? createBlankCell('');
    const nextCell: SpreadsheetCell = {
      ...existing,
      style: {
        ...existing.style,
        ...patch,
      },
    };

    const nextWorkbook = updateWorkbookSheet(state.workbook, (currentSheet) => ({
      ...currentSheet,
      cells: {
        ...currentSheet.cells,
        [state.selectedCell]: nextCell,
      },
    }));

    set({
      workbook: nextWorkbook,
      dirty: true,
      undoStack: [...state.undoStack, cloneWorkbook(state.workbook)].slice(-20),
      redoStack: [],
    });
    void window.xelora.setUnsavedChanges(true);
  },
  addWorksheet: () => {
    const state = get();
    if (!state.workbook) {
      return;
    }

    const nextWorkbook = {
      ...state.workbook,
      sheets: [
        ...state.workbook.sheets,
        {
          id: crypto.randomUUID(),
          name: `Sheet ${state.workbook.sheets.length + 1}`,
          rowCount: 20,
          columnCount: 10,
          frozenRows: 1,
          cells: {},
        },
      ],
    };

    set({ workbook: nextWorkbook, dirty: true, undoStack: [...state.undoStack, cloneWorkbook(state.workbook)], redoStack: [] });
    void window.xelora.setUnsavedChanges(true);
  },
  renameActiveWorksheet: (name) => {
    const state = get();
    if (!state.workbook) {
      return;
    }

    const active = getActiveSheet(state.workbook);
    const nextWorkbook = {
      ...state.workbook,
      sheets: state.workbook.sheets.map((sheet) => (sheet.id === active.id ? { ...sheet, name } : sheet)),
    };

    set({ workbook: nextWorkbook, dirty: true, undoStack: [...state.undoStack, cloneWorkbook(state.workbook)], redoStack: [] });
    void window.xelora.setUnsavedChanges(true);
  },
  duplicateActiveWorksheet: () => {
    const state = get();
    if (!state.workbook) {
      return;
    }

    const active = getActiveSheet(state.workbook);
    const duplicate = {
      ...cloneWorkbook(state.workbook).sheets.find((sheet) => sheet.id === active.id)!,
      id: crypto.randomUUID(),
      name: `${active.name} Copy`,
    };
    const nextWorkbook = { ...state.workbook, sheets: [...state.workbook.sheets, duplicate] };
    set({ workbook: nextWorkbook, dirty: true, undoStack: [...state.undoStack, cloneWorkbook(state.workbook)], redoStack: [] });
    void window.xelora.setUnsavedChanges(true);
  },
  deleteActiveWorksheet: () => {
    const state = get();
    if (!state.workbook || state.workbook.sheets.length === 1) {
      return;
    }

    const active = getActiveSheet(state.workbook);
    const sheets = state.workbook.sheets.filter((sheet) => sheet.id !== active.id);
    const nextWorkbook = { ...state.workbook, sheets, activeSheetId: sheets[0].id };
    set({ workbook: nextWorkbook, selectedCell: 'A1', dirty: true, undoStack: [...state.undoStack, cloneWorkbook(state.workbook)], redoStack: [] });
    void window.xelora.setUnsavedChanges(true);
  },
  saveWorkbook: async (saveAs = false) => {
    const state = get();
    if (!state.workbook) {
      return;
    }

    const result = saveAs
      ? await window.xelora.saveWorkbookAs({ workbook: state.workbook, filePath: state.workbook.filePath })
      : await window.xelora.saveWorkbook({ workbook: state.workbook, filePath: state.workbook.filePath });

    if (!result) {
      return;
    }

    set({
      workbook: {
        ...state.workbook,
        filePath: result.filePath,
        fileName: result.fileName,
        lastSavedAt: result.savedAt,
      },
      dirty: false,
      lastSaveResult: result,
      statusMessage: `Saved ${result.fileName}`,
    });
    await window.xelora.setUnsavedChanges(false);
  },
  createBackup: async () => {
    const state = get();
    if (!state.workbook?.filePath) {
      return;
    }

    const result = await window.xelora.createBackup({
      sourceFilePath: state.workbook.filePath,
      workbookName: state.workbook.fileName,
    });
    set({ statusMessage: `Backup created at ${result.backupPath}` });
    await window.xelora.showNotification({
      title: 'Backup created',
      body: `Xelora saved a backup copy at ${result.backupPath}`,
    });
  },
  loadSettings: async () => {
    const settings = await window.xelora.getSettings();
    set({ settings, aiContext: settings.ai.defaultContext });
  },
  togglePanel: (panel) => set((state) => ({ activePanel: state.activePanel === panel ? 'workflow' : panel })),
  runMockWorkflow: () => {
    const state = get();
    set({
      workflowRun: {
        ...state.workflowRun,
        status: 'Running',
        currentStepIndex: 0,
        progress: 0,
        creditsUsed: 0,
      },
      activePanel: 'workflow',
    });
  },
  applyMockAiPrompt: (prompt) => set({ aiPrompt: prompt, activePanel: 'ai' }),
  useSampleWorkbook: () => {
    const workbook = createSampleWorkbook();
    set({ workbook, screen: 'workbook', dirty: false, statusMessage: 'Loaded sample workbook' });
    void window.xelora.setUnsavedChanges(false);
  },
  selectNextCell: (deltaRow, deltaColumn) => {
    const state = get();
    const nextRef = selectCellAfterMove(state.selectedCell, deltaRow, deltaColumn);
    set({ selectedCell: nextRef, formulaInput: state.workbook ? getActiveSheet(state.workbook).cells[nextRef]?.formula ?? getActiveSheet(state.workbook).cells[nextRef]?.value ?? '' : '' });
  },
}));
