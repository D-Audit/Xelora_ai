import { useEffect, useMemo, useState } from 'react';
import { z } from 'zod';
import { useForm, type UseFormReturn } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import {
  AlertTriangle,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  Bell,
  BarChart3,
  BookOpen,
  BrainCircuit,
  Calculator,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  CircleAlert,
  CircleUserRound,
  CloudOff,
  Copy,
  Download,
  FileSpreadsheet,
  FolderOpen,
  Filter,
  GitBranch,
  HardDriveDownload,
  HelpCircle,
  Home,
  LayoutDashboard,
  LayoutGrid,
  ListTodo,
  Maximize2,
  Menu,
  Minus,
  PackageOpen,
  Pause,
  Pencil,
  Plus,
  RefreshCw,
  RotateCcw,
  RotateCw,
  Save,
  Search,
  PanelLeftClose,
  Settings2,
  Shuffle,
  Sparkles,
  Table2,
  Upload,
  Clock3,
  Zap,
  X,
} from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { useDesktopStore } from '../lib/store';
import { createBlankCell, createSampleWorkbook, getActiveSheet, cellRef, columnName, countFilledCells, cloneWorkbook, setCell } from '../../shared/workbook';
import type { DesktopSettings, SpreadsheetCell, SpreadsheetWorkbook, WorkflowStep } from '../../shared/types';
import { mockAiResponse } from '../lib/mock';

const loginSchema = z.object({
  email: z.string().email('Enter a valid email address.'),
  password: z.string().min(1, 'Enter your password.'),
  rememberMe: z.boolean().default(true),
});

type LoginFormValues = z.infer<typeof loginSchema>;
type LoginFormInput = z.input<typeof loginSchema>;

const settingsSchema = z.object({
  general: z.object({
    language: z.string().min(1),
    theme: z.enum(['light', 'system']),
    startPage: z.enum(['welcome', 'dashboard', 'last-workbook']),
    restorePreviousSession: z.boolean(),
    defaultSaveFolder: z.string(),
  }),
  files: z.object({
    autoSave: z.boolean(),
    autoSaveIntervalMinutes: z.coerce.number().min(1).max(30),
    createBackupBeforeAutomation: z.boolean(),
    recentFilesLimit: z.coerce.number().min(3).max(50),
  }),
  ai: z.object({
    explanationLevel: z.enum(['brief', 'balanced', 'detailed']),
    approvalLevel: z.enum(['low', 'medium', 'high']),
    defaultContext: z.enum(['selected-cell', 'selected-range', 'worksheet', 'workbook']),
    destructiveActionConfirmation: z.boolean(),
  }),
  privacy: z.object({
    localProcessingPreference: z.boolean(),
    cloudProcessingPlaceholder: z.boolean(),
    clearRecentFilesOnSignOut: z.boolean(),
    clearLocalHistoryOnSignOut: z.boolean(),
  }),
  application: z.object({
    version: z.string(),
    checkForUpdates: z.boolean(),
    releaseChannel: z.enum(['stable', 'beta']),
    showLogsPath: z.boolean(),
    resetApplication: z.boolean(),
  }),
});

type SettingsFormValues = z.infer<typeof settingsSchema>;
type SettingsFormInput = z.input<typeof settingsSchema>;

function formatBytes(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function cellMatchesFormula(cell?: SpreadsheetCell): string {
  if (!cell) {
    return '';
  }
  return cell.formula ? `=${cell.formula}` : cell.value;
}

function getWorkbookStats(workbook: SpreadsheetWorkbook | null) {
  const sheet = workbook ? getActiveSheet(workbook) : null;
  const values = sheet ? Object.values(sheet.cells) : [];
  const numericValues = values
    .map((cell) => Number(cell.value))
    .filter((value) => Number.isFinite(value));
  const total = numericValues.reduce((sum, value) => sum + value, 0);
  const average = numericValues.length > 0 ? total / numericValues.length : 0;
  return {
    total,
    average,
    cells: sheet ? countFilledCells(sheet) : 0,
    rows: sheet?.rowCount ?? 0,
    columns: sheet?.columnCount ?? 0,
  };
}

function createMetrics(workbook: SpreadsheetWorkbook | null) {
  const stats = getWorkbookStats(workbook);
  return [
    { label: 'Total sales', value: `$${stats.total.toLocaleString()}`, delta: '+12.8%' },
    { label: 'Transactions', value: `${Math.max(stats.cells * 4, 128)}`, delta: '+4.1%' },
    { label: 'Average order value', value: `$${stats.average.toFixed(2)}`, delta: '+2.3%' },
    { label: 'Rows in view', value: `${stats.rows}`, delta: 'Live' },
  ];
}

function App() {
  const store = useDesktopStore();
  const [loginError, setLoginError] = useState<string | null>(null);
  const [selectedSuggestion, setSelectedSuggestion] = useState('Explain this formula');
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [workflowSteps, setWorkflowSteps] = useState<WorkflowStep[]>(createSampleWorkbook().sheets.length > 0 ? [
    { id: 'analyse', label: 'Analyse the workbook', description: 'Inspect the imported workbook.', status: 'Pending' },
    { id: 'columns', label: 'Confirm required columns', description: 'Check required input columns.', status: 'Pending' },
    { id: 'clean', label: 'Remove duplicate rows', description: 'Remove repeated entries.', status: 'Needs approval', requiresApproval: true },
    { id: 'standardize', label: 'Standardise text values', description: 'Trim spaces and fix casing.', status: 'Pending' },
    { id: 'formula', label: 'Add formulas', description: 'Insert summary formulas.', status: 'Pending', requiresApproval: true },
    { id: 'summary', label: 'Create summary sheet', description: 'Build a report sheet.', status: 'Pending' },
    { id: 'chart', label: 'Generate chart', description: 'Create a chart from workbook data.', status: 'Pending' },
  ] : []);
  const [workflowProgress, setWorkflowProgress] = useState(0);

  const loginForm = useForm<LoginFormInput, unknown, LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: 'liliane@xelora.app',
      password: 'Demo123!',
      rememberMe: true,
    },
  });

  const settingsForm = useForm<SettingsFormInput, unknown, SettingsFormValues>({
    resolver: zodResolver(settingsSchema),
  });

  useEffect(() => {
    void store.initializeFromMain();
  }, []);

  useEffect(() => {
    if (store.settings) {
      settingsForm.reset(store.settings);
    }
  }, [store.settings, settingsForm]);

  useEffect(() => {
    const menuDispose = window.xelora.onMenuAction((action) => {
      switch (action) {
        case 'new-workbook':
          store.createBlankWorkbook();
          break;
        case 'open-workbook':
          void store.openWorkbook();
          break;
        case 'open-csv':
          void store.openCsv();
          break;
        case 'save-workbook':
          void store.saveWorkbook(false);
          break;
        case 'save-workbook-as':
        case 'export-copy':
          void store.saveWorkbook(true);
          break;
        case 'undo':
          store.undo();
          break;
        case 'redo':
          store.redo();
          break;
        case 'run-workflow':
          setWorkflowProgress(0);
          setWorkflowSteps((steps) => steps.map((step, index) => ({ ...step, status: index === 0 ? 'Running' : 'Pending' })));
          break;
        case 'pause-workflow':
          setWorkflowSteps((steps) => steps.map((step, index) => (index === 0 ? { ...step, status: 'Warning' } : step)));
          break;
        case 'toggle-workflow-panel':
          store.togglePanel('workflow');
          break;
        case 'toggle-ai-panel':
          store.togglePanel('ai');
          break;
        case 'clean-data':
          store.setScreen('cleaning');
          store.setPanel('cleaning');
          break;
        case 'about':
          store.setStatusMessage('Xelora Desktop 0.1.0');
          break;
        case 'find':
          store.setStatusMessage('Find is ready. Use the toolbar or Ctrl+F.');
          break;
        case 'replace':
          store.setStatusMessage('Replace is ready. Use the toolbar or Ctrl+H.');
          break;
        default:
          break;
      }
    });

    const closeDispose = window.xelora.onCloseSaveRequest(() => {
      const workbook = useDesktopStore.getState().workbook;
      if (!workbook) {
        void window.xelora.confirmCloseAfterSave();
        return;
      }
      void store.saveWorkbook(false).then(() => window.xelora.confirmCloseAfterSave());
    });

    const protocolDispose = window.xelora.onProtocolCallback((url) => {
      store.setStatusMessage(`Protocol callback received: ${url}`);
    });

    const handleOnline = () => store.setOffline(false);
    const handleOffline = () => store.setOffline(true);
    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      menuDispose();
      closeDispose();
      protocolDispose();
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  useEffect(() => {
    if (store.workflowRun.status !== 'Running') {
      return;
    }

    const timer = window.setInterval(() => {
      setWorkflowProgress((progress) => {
        const next = Math.min(progress + 14, 100);
        if (next >= 100) {
          setWorkflowSteps((steps) => steps.map((step) => ({ ...step, status: 'Completed' })));
          window.clearInterval(timer);
          store.setStatusMessage('Workflow completed locally.');
          window.xelora.showNotification({
            title: 'Workflow completed',
            body: 'Xelora finished the simulated workflow locally.',
          });
        }
        return next;
      });
    }, 500);

    return () => window.clearInterval(timer);
  }, [store.workflowRun.status]);

  const currentWorkbook = store.workbook;
  const activeSheet = currentWorkbook ? getActiveSheet(currentWorkbook) : null;
  const activeCell = currentWorkbook ? activeSheet?.cells[store.selectedCell] : undefined;
  const metrics = createMetrics(currentWorkbook);
  const chartRows = useMemo(() => {
    const source = currentWorkbook ? getActiveSheet(currentWorkbook) : createSampleWorkbook().sheets[0];
    const rowCount = Math.min(source.rowCount, 6);
    return Array.from({ length: rowCount }, (_, index) => {
      const revenue = Number(source.cells[`F${index + 2}`]?.value ?? 0) || (index + 1) * 1000;
      return {
        name: source.cells[`A${index + 2}`]?.value || `Row ${index + 1}`,
        revenue,
      };
    });
  }, [currentWorkbook]);

  if (store.isLoading) {
    return <LoadingScreen />;
  }

  if (!store.session) {
    return (
      <WelcomeScreen
        loginError={loginError}
        onSubmit={async (values) => {
          setLoginError(null);
          try {
            await window.xelora.login(values);
            const session = await window.xelora.getSession();
            store.setSession(session);
            await store.loadSettings();
            await store.setRecentFiles(await window.xelora.getRecentFiles());
            store.setStatusMessage('Welcome back to Xelora.');
          } catch (error) {
            setLoginError(error instanceof Error ? error.message : 'Unable to sign in.');
          }
        }}
        form={loginForm}
      />
    );
  }

  if (store.screen === 'settings') {
    return (
      <SettingsScreen
        form={settingsForm}
        onSave={async (values) => {
          const settings = await window.xelora.updateSettings(values);
          store.setSettings(settings);
          store.setScreen(currentWorkbook ? 'workbook' : 'home');
          setSettingsOpen(false);
          store.setStatusMessage('Settings saved locally.');
        }}
        onClose={() => {
          store.setScreen(currentWorkbook ? 'workbook' : 'home');
          setSettingsOpen(false);
        }}
      />
    );
  }

  if (store.screen === 'home') {
    return (
      <DesktopPreviewScreen
        metrics={metrics}
        recentFiles={store.recentFiles}
        version={store.appInfo?.version ?? '0.1.0'}
        onOpenFile={store.openWorkbook}
        onImportCsv={store.openCsv}
        onNewWorkbook={store.createBlankWorkbook}
        onOpenCloudFile={() => store.setStatusMessage('Cloud files will connect through Xelora Cloud in a future release.')}
        onOpenReports={() => store.setScreen('reports')}
        onOpenSettings={() => {
          store.setScreen('settings');
          setSettingsOpen(true);
        }}
        onRunWorkflow={() => store.runMockWorkflow()}
        onSampleWorkbook={store.useSampleWorkbook}
        onOpenRecentFile={store.openRecentFile}
        sessionName={store.session.user?.name ?? 'Liliane'}
      />
    );
  }

  return (
    <div className="flex h-full flex-col text-[14px] text-[#001E2B]">
      {store.isOffline ? (
        <div className="border-b border-[#DDE5E2] bg-[#FFF4D6] px-4 py-2 text-sm text-[#7A4B00]">
          You are offline. Local spreadsheet editing remains available, but cloud and AI services require an internet connection.
        </div>
      ) : null}

      <TopBar
        workbook={currentWorkbook}
        sessionName={store.session.user?.name ?? 'Liliane'}
        dirty={store.dirty}
        onOpen={store.openWorkbook}
        onOpenCsv={store.openCsv}
        onNew={store.createBlankWorkbook}
        onSample={store.useSampleWorkbook}
        onSave={() => store.saveWorkbook(false)}
        onSaveAs={() => store.saveWorkbook(true)}
        onUndo={store.undo}
        onRedo={store.redo}
        onSettings={() => {
          store.setScreen('settings');
          setSettingsOpen(true);
        }}
        onReports={() => store.setScreen('reports')}
        onCleaning={() => store.setScreen('cleaning')}
        onHome={() => store.setScreen('home')}
      />

      <div className="grid min-h-0 flex-1 grid-cols-[280px_minmax(0,1fr)_360px] gap-0 overflow-hidden">
        <LeftRail
          active={store.activePanel}
          onChange={(panel) => store.setPanel(panel)}
          workflowSteps={workflowSteps}
          progress={workflowProgress}
          onUpdateStep={(index, next) => {
            setWorkflowSteps((steps) => steps.map((step, stepIndex) => (stepIndex === index ? next : step)));
          }}
          onAddStep={() => {
            const label = window.prompt('Add a workflow step');
            if (!label) {
              return;
            }
            setWorkflowSteps((steps) => [
              ...steps,
              { id: crypto.randomUUID(), label, description: 'Custom step added by the user.', status: 'Pending' },
            ]);
          }}
          onRemoveStep={(index) => {
            setWorkflowSteps((steps) => steps.filter((_, stepIndex) => stepIndex !== index));
          }}
          onMoveStep={(index, direction) => {
            setWorkflowSteps((steps) => {
              const next = [...steps];
              const target = index + direction;
              if (target < 0 || target >= next.length) {
                return next;
              }
              [next[index], next[target]] = [next[target], next[index]];
              return next;
            });
          }}
          onApproveAll={() => {
            setWorkflowSteps((steps) => steps.map((step) => ({ ...step, status: 'Completed' })));
            setWorkflowProgress(100);
          }}
          onRun={() => {
            store.runMockWorkflow();
            setWorkflowProgress(0);
          }}
        />

        <main className="min-h-0 overflow-hidden bg-[#F7F9F8]">
          {store.screen === 'reports' ? (
            <ReportsScreen
              workbook={currentWorkbook}
              chartRows={chartRows}
              onReturn={() => store.setScreen(currentWorkbook ? 'workbook' : 'home')}
            />
          ) : store.screen === 'cleaning' ? (
            <CleaningScreen
              workbook={currentWorkbook}
              onReturn={() => store.setScreen(currentWorkbook ? 'workbook' : 'home')}
              onCleanTrim={() => {
                if (!currentWorkbook) return;
                const next = cloneWorkbook(currentWorkbook);
                const sheet = getActiveSheet(next);
                Object.keys(sheet.cells).forEach((ref) => {
                  const cell = sheet.cells[ref];
                  sheet.cells[ref] = { ...cell, value: cell.value.trim() };
                });
                store.setWorkbook(next);
              }}
              onFillMissing={() => {
                if (!currentWorkbook) return;
                const next = cloneWorkbook(currentWorkbook);
                const sheet = getActiveSheet(next);
                Object.keys(sheet.cells).forEach((ref) => {
                  if (sheet.cells[ref].value.trim().length === 0) {
                    sheet.cells[ref] = createBlankCell('N/A');
                  }
                });
                store.setWorkbook(next);
              }}
            />
          ) : currentWorkbook ? (
            <WorkbookScreen
              workbook={currentWorkbook}
              selectedCell={store.selectedCell}
              formulaInput={store.formulaInput}
              onSelectCell={store.setSelectedCell}
              onFormulaChange={store.setFormulaInput}
              onApplyFormula={async () => {
                const value = store.formulaInput;
                const formula = value.startsWith('=') ? value.slice(1) : undefined;
                await store.editSelectedCell(value, formula);
              }}
              onStyle={(patch) => store.updateCellStyle(patch)}
              onAddSheet={store.addWorksheet}
              onRenameSheet={store.renameActiveWorksheet}
              onDuplicateSheet={store.duplicateActiveWorksheet}
              onDeleteSheet={store.deleteActiveWorksheet}
              onCellMove={store.selectNextCell}
              onOpenReports={() => store.setScreen('reports')}
              onOpenCleaning={() => store.setScreen('cleaning')}
              onAskAi={(prompt) => {
                store.applyMockAiPrompt(prompt);
                store.setPanel('ai');
              }}
              onOpenSettings={() => {
                store.setScreen('settings');
                setSettingsOpen(true);
              }}
              activeCell={activeCell}
              statusMessage={store.statusMessage}
              dirty={store.dirty}
            />
          ) : (
            <DesktopPreviewScreen
              metrics={metrics}
              recentFiles={store.recentFiles}
              version={store.appInfo?.version ?? '0.1.0'}
              onOpenFile={store.openWorkbook}
              onImportCsv={store.openCsv}
              onNewWorkbook={store.createBlankWorkbook}
              onOpenCloudFile={() => store.setStatusMessage('Cloud files will connect through Xelora Cloud in a future release.')}
              onOpenReports={() => store.setScreen('reports')}
              onOpenSettings={() => {
                store.setScreen('settings');
                setSettingsOpen(true);
              }}
              onRunWorkflow={() => store.runMockWorkflow()}
              onSampleWorkbook={store.useSampleWorkbook}
              onOpenRecentFile={store.openRecentFile}
              sessionName={store.session.user?.name ?? 'Liliane'}
            />
          )}
        </main>

        <RightRail
          active={store.activePanel}
          workbook={currentWorkbook}
          prompt={store.aiPrompt}
          onPromptChange={store.setAiPrompt}
          onAsk={() => {
            store.setPanel('ai');
            store.setStatusMessage(mockAiResponse(store.aiPrompt));
          }}
          onSuggestion={(suggestion) => {
            setSelectedSuggestion(suggestion);
            store.applyMockAiPrompt(suggestion);
          }}
          selectedSuggestion={selectedSuggestion}
          onOpenReports={() => store.setScreen('reports')}
          onOpenSettings={() => {
            store.setScreen('settings');
            setSettingsOpen(true);
          }}
          onLogout={async () => {
            await window.xelora.logout();
            store.setSession(null);
          }}
          onOpenExternal={async () => {
            await window.xelora.openExternalUrl('https://xelora.app');
          }}
          onSaveBackup={store.createBackup}
        />
      </div>

      <FooterBar
        workbook={currentWorkbook}
        selectedCell={store.selectedCell}
        statusMessage={store.statusMessage}
        version={store.appInfo?.version ?? '0.1.0'}
        dirty={store.dirty}
        offline={store.isOffline}
      />

      {settingsOpen ? null : null}
    </div>
  );
}

function LoadingScreen() {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="rounded-2xl border border-[#DDE5E2] bg-white px-8 py-6 shadow-sm">
        <div className="mb-3 text-sm font-medium text-[#5C6C75]">Starting Xelora Desktop</div>
        <div className="h-2 w-80 overflow-hidden rounded-full bg-[#F1F5F3]">
          <div className="h-full w-2/3 rounded-full bg-[#00ED64]" />
        </div>
      </div>
    </div>
  );
}

function WelcomeScreen({ form, onSubmit, loginError }: { form: UseFormReturn<LoginFormInput, unknown, LoginFormValues>; onSubmit: (values: LoginFormValues) => Promise<void>; loginError: string | null }) {
  return (
    <div className="grid min-h-full grid-cols-1 lg:grid-cols-[1.15fr_0.85fr]">
      <section className="flex flex-col justify-between bg-[#001E2B] px-8 py-10 text-white">
        <div>
          <div className="mb-14 flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#00ED64] text-[#001E2B] font-black">X</div>
            <div>
              <div className="text-lg font-semibold">Xelora</div>
              <div className="text-sm text-white/70">Automate spreadsheets. Stay in control.</div>
            </div>
          </div>

          <div className="max-w-xl">
            <p className="mb-4 text-sm uppercase tracking-[0.35em] text-white/55">Desktop application</p>
            <h1 className="max-w-lg text-5xl font-semibold leading-[1.02]">Welcome to Xelora</h1>
            <p className="mt-6 max-w-xl text-lg text-white/75">
              Automate repetitive spreadsheet work while keeping every change visible, editable, and reversible.
            </p>
          </div>
        </div>

        <div className="grid gap-4 text-sm text-white/75 sm:grid-cols-2">
          <InfoCard title="Local editing" description="Open spreadsheets, work offline, and save changes locally." />
          <InfoCard title="Mock cloud auth" description="Sign in with the demo account while the cloud backend is being connected." />
          <InfoCard title="Secure bridge" description="Privileged file access stays in the Electron main process." />
          <InfoCard title="Desktop installer" description="Built for Windows install, shortcuts, and future updates." />
        </div>
      </section>

      <section className="flex items-center justify-center p-6">
        <div className="w-full max-w-xl rounded-[28px] border border-[#DDE5E2] bg-white p-8 shadow-[0_18px_60px_rgba(0,30,43,0.08)]">
          <div className="mb-6">
            <h2 className="text-2xl font-semibold text-[#001E2B]">Sign in</h2>
            <p className="mt-2 text-sm text-[#5C6C75]">Use the demo account to enter the desktop workspace.</p>
          </div>

          <form
            className="space-y-4"
            onSubmit={form.handleSubmit(async (values) => {
              await onSubmit(values);
            })}
          >
            <label className="block">
              <span className="mb-1 block text-sm font-medium">Email</span>
              <input
                className="w-full rounded-xl border border-[#DDE5E2] bg-white px-4 py-3 text-sm outline-none transition focus:border-[#00684A]"
                {...form.register('email')}
              />
            </label>

            <label className="block">
              <span className="mb-1 block text-sm font-medium">Password</span>
              <input
                type="password"
                className="w-full rounded-xl border border-[#DDE5E2] bg-white px-4 py-3 text-sm outline-none transition focus:border-[#00684A]"
                {...form.register('password')}
              />
            </label>

            <label className="flex items-center gap-2 text-sm text-[#5C6C75]">
              <input type="checkbox" className="h-4 w-4 rounded border-[#B8C4C0]" {...form.register('rememberMe')} />
              Remember me on this device
            </label>

            {loginError ? (
              <div className="rounded-xl border border-[#FECACA] bg-[#FEECEB] px-4 py-3 text-sm text-[#B42318]">{loginError}</div>
            ) : null}

            <button
              type="submit"
              className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-[#00684A] px-4 py-3 font-medium text-white transition hover:bg-[#023430]"
            >
              Sign In
            </button>
          </form>

          <div className="mt-6 rounded-2xl border border-dashed border-[#DDE5E2] bg-[#F1F5F3] p-4 text-sm text-[#5C6C75]">
            <div className="mb-2 font-medium text-[#001E2B]">Demo credentials</div>
            <div>Email: liliane@xelora.app</div>
            <div>Password: Demo123!</div>
            <div className="mt-3 text-xs text-[#889397]">Password is not stored in local storage.</div>
          </div>
        </div>
      </section>
    </div>
  );
}

function TopBar({
  workbook,
  sessionName,
  dirty,
  onOpen,
  onOpenCsv,
  onNew,
  onSample,
  onSave,
  onSaveAs,
  onUndo,
  onRedo,
  onSettings,
  onReports,
  onCleaning,
  onHome,
}: {
  workbook: SpreadsheetWorkbook | null;
  sessionName: string;
  dirty: boolean;
  onOpen: () => void | Promise<void>;
  onOpenCsv: () => void | Promise<void>;
  onNew: () => void;
  onSample: () => void;
  onSave: () => void | Promise<void>;
  onSaveAs: () => void | Promise<void>;
  onUndo: () => void;
  onRedo: () => void;
  onSettings: () => void;
  onReports: () => void;
  onCleaning: () => void;
  onHome: () => void;
}) {
  return (
    <div className="flex items-center justify-between border-b border-[#DDE5E2] bg-white/90 px-4 py-3 backdrop-blur">
      <div className="flex items-center gap-3">
        <button className="flex h-10 w-10 items-center justify-center rounded-xl border border-[#DDE5E2] bg-[#F1F5F3] text-[#001E2B]" onClick={onHome}>
          <FileSpreadsheet className="h-5 w-5" />
        </button>
        <div>
          <div className="text-sm font-semibold">{workbook?.fileName ?? 'Xelora'}</div>
          <div className="text-xs text-[#5C6C75]">Signed in as {sessionName}{dirty ? ' • Unsaved changes' : ''}</div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        <ToolButton label="Open" icon={<PackageOpen className="h-4 w-4" />} onClick={onOpen} />
        <ToolButton label="Import CSV" icon={<Upload className="h-4 w-4" />} onClick={onOpenCsv} />
        <ToolButton label="New" icon={<Plus className="h-4 w-4" />} onClick={onNew} />
        <ToolButton label="Sample" icon={<Download className="h-4 w-4" />} onClick={onSample} />
        <ToolButton label="Save" icon={<Save className="h-4 w-4" />} onClick={onSave} primary />
        <ToolButton label="Save As" icon={<HardDriveDownload className="h-4 w-4" />} onClick={onSaveAs} />
        <ToolButton label="Undo" icon={<RotateCcw className="h-4 w-4" />} onClick={onUndo} />
        <ToolButton label="Redo" icon={<RotateCw className="h-4 w-4" />} onClick={onRedo} />
        <ToolButton label="Reports" icon={<Table2 className="h-4 w-4" />} onClick={onReports} />
        <ToolButton label="Clean Data" icon={<Filter className="h-4 w-4" />} onClick={onCleaning} />
        <ToolButton label="Settings" icon={<Settings2 className="h-4 w-4" />} onClick={onSettings} />
      </div>
    </div>
  );
}

function ToolButton({
  label,
  icon,
  onClick,
  primary = false,
}: {
  label: string;
  icon: React.ReactNode;
  onClick: () => void | Promise<void>;
  primary?: boolean;
}) {
  return (
    <button
      onClick={() => void onClick()}
      className={`inline-flex items-center gap-2 rounded-xl border px-2.5 py-2 text-xs transition ${
        primary
          ? 'border-[#00684A] bg-[#00684A] text-white hover:bg-[#023430]'
          : 'border-[#DDE5E2] bg-white text-[#001E2B] hover:bg-[#F1F5F3]'
      }`}
    >
      {icon}
      {label}
    </button>
  );
}

function LeftRail({
  active,
  onChange,
  workflowSteps,
  progress,
  onUpdateStep,
  onAddStep,
  onRemoveStep,
  onMoveStep,
  onApproveAll,
  onRun,
}: {
  active: 'workflow' | 'ai' | 'reports' | 'cleaning';
  onChange: (panel: 'workflow' | 'ai' | 'reports' | 'cleaning') => void;
  workflowSteps: WorkflowStep[];
  progress: number;
  onUpdateStep: (index: number, next: WorkflowStep) => void;
  onAddStep: () => void;
  onRemoveStep: (index: number) => void;
  onMoveStep: (index: number, direction: number) => void;
  onApproveAll: () => void;
  onRun: () => void;
}) {
  return (
    <aside className="flex min-h-0 flex-col border-r border-[#DDE5E2] bg-white">
      <div className="border-b border-[#DDE5E2] p-4">
        <div className="text-xs uppercase tracking-[0.3em] text-[#889397]">Workspace</div>
        <div className="mt-1 text-lg font-semibold">Workflow & tools</div>
      </div>

      <div className="grid grid-cols-2 gap-2 border-b border-[#DDE5E2] p-3">
        {[
          ['workflow', 'Workflow'],
          ['ai', 'Xelora AI'],
          ['reports', 'Reports'],
          ['cleaning', 'Cleaning'],
        ].map(([id, label]) => (
          <button
            key={id}
            className={`rounded-xl px-3 py-2 text-sm font-medium transition ${
              active === id ? 'bg-[#001E2B] text-white' : 'bg-[#F1F5F3] text-[#001E2B] hover:bg-[#E3EAE7]'
            }`}
            onClick={() => onChange(id as 'workflow' | 'ai' | 'reports' | 'cleaning')}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="min-h-0 flex-1 overflow-auto p-4">
        <div className="rounded-2xl border border-[#DDE5E2] bg-[#F7F9F8] p-4">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <div className="text-sm font-semibold">Review workflow</div>
              <div className="text-xs text-[#5C6C75]">Editable local simulation</div>
            </div>
            <button className="rounded-lg bg-[#00684A] px-3 py-2 text-xs font-medium text-white" onClick={onRun}>
              Run
            </button>
          </div>

          <div className="mb-3 h-2 overflow-hidden rounded-full bg-white">
            <div className="h-full rounded-full bg-[#00ED64]" style={{ width: `${progress}%` }} />
          </div>

          <div className="space-y-2">
            {workflowSteps.map((step, index) => (
              <div key={step.id} className="rounded-xl border border-[#DDE5E2] bg-white p-3">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="text-sm font-medium">{step.label}</div>
                    <div className="text-xs text-[#5C6C75]">{step.description}</div>
                  </div>
                  <span className="rounded-full bg-[#F1F5F3] px-2 py-1 text-[11px] font-medium text-[#5C6C75]">{step.status}</span>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  <TinyButton label="Edit" icon={<Pencil className="h-3.5 w-3.5" />} onClick={() => {
                    const label = window.prompt('Edit step label', step.label);
                    if (label) {
                      onUpdateStep(index, { ...step, label });
                    }
                  }} />
                  <TinyButton label="Up" icon={<ChevronUp className="h-3.5 w-3.5" />} onClick={() => onMoveStep(index, -1)} />
                  <TinyButton label="Down" icon={<ChevronDown className="h-3.5 w-3.5" />} onClick={() => onMoveStep(index, 1)} />
                  <TinyButton label="Remove" icon={<X className="h-3.5 w-3.5" />} onClick={() => onRemoveStep(index)} />
                </div>
              </div>
            ))}
          </div>

          <div className="mt-4 flex flex-wrap gap-2">
            <TinyButton label="Approve all" icon={<Check className="h-3.5 w-3.5" />} onClick={onApproveAll} />
            <TinyButton label="Add step" icon={<Plus className="h-3.5 w-3.5" />} onClick={onAddStep} />
            <TinyButton label="Save workflow" icon={<Download className="h-3.5 w-3.5" />} onClick={() => window.alert('Workflow saved locally as a mock preset.')} />
          </div>
        </div>
      </div>
    </aside>
  );
}

function TinyButton({ label, icon, onClick }: { label: string; icon: React.ReactNode; onClick: () => void }) {
  return (
    <button onClick={onClick} className="inline-flex items-center gap-1 rounded-lg border border-[#DDE5E2] bg-white px-2.5 py-1.5 text-xs hover:bg-[#F1F5F3]">
      {icon}
      {label}
    </button>
  );
}

function WorkbookScreen({
  workbook,
  selectedCell,
  formulaInput,
  onSelectCell,
  onFormulaChange,
  onApplyFormula,
  onStyle,
  onAddSheet,
  onRenameSheet,
  onDuplicateSheet,
  onDeleteSheet,
  onCellMove,
  onOpenReports,
  onOpenCleaning,
  onAskAi,
  onOpenSettings,
  activeCell,
  statusMessage,
  dirty,
}: {
  workbook: SpreadsheetWorkbook;
  selectedCell: string;
  formulaInput: string;
  onSelectCell: (ref: string) => void;
  onFormulaChange: (value: string) => void;
  onApplyFormula: () => Promise<void>;
  onStyle: (patch: Partial<SpreadsheetCell['style']>) => void;
  onAddSheet: () => void;
  onRenameSheet: (name: string) => void;
  onDuplicateSheet: () => void;
  onDeleteSheet: () => void;
  onCellMove: (deltaRow: number, deltaColumn: number) => void;
  onOpenReports: () => void;
  onOpenCleaning: () => void;
  onAskAi: (prompt: string) => void;
  onOpenSettings: () => void;
  activeCell?: SpreadsheetCell;
  statusMessage: string;
  dirty: boolean;
}) {
  const activeSheet = getActiveSheet(workbook);
  return (
    <div className="flex h-full min-h-0 flex-col gap-4 bg-[#EEF3F0] p-4">
      <FormulaBar
        workbook={workbook}
        selectedCell={selectedCell}
        formulaInput={formulaInput}
        onFormulaChange={onFormulaChange}
        onApplyFormula={onApplyFormula}
        onStyle={onStyle}
        activeCell={activeCell}
      />
      <div className="flex min-h-0 flex-1 overflow-hidden rounded-3xl border border-[#DDE5E2] bg-white shadow-sm">
        <SpreadsheetGrid workbook={workbook} selectedCell={selectedCell} onSelectCell={onSelectCell} onCellMove={onCellMove} onAskAi={onAskAi} />
      </div>
      <div className="rounded-2xl border border-[#DDE5E2] bg-white px-4 py-3 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3 text-xs text-[#5C6C75]">
          <div className="flex flex-wrap items-center gap-2">
            <button className="rounded-lg bg-[#F1F5F3] px-3 py-2 font-medium text-[#001E2B]" onClick={onAddSheet}>Add sheet</button>
            <button className="rounded-lg bg-[#F1F5F3] px-3 py-2 font-medium text-[#001E2B]" onClick={() => onRenameSheet(window.prompt('Rename worksheet', activeSheet.name) ?? activeSheet.name)}>Rename</button>
            <button className="rounded-lg bg-[#F1F5F3] px-3 py-2 font-medium text-[#001E2B]" onClick={onDuplicateSheet}>Duplicate</button>
            <button className="rounded-lg bg-[#F1F5F3] px-3 py-2 font-medium text-[#001E2B]" onClick={onDeleteSheet}>Delete</button>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button className="rounded-lg border border-[#DDE5E2] px-3 py-2" onClick={onOpenReports}>Reports</button>
            <button className="rounded-lg border border-[#DDE5E2] px-3 py-2" onClick={onOpenCleaning}>Clean data</button>
            <button className="rounded-lg border border-[#DDE5E2] px-3 py-2" onClick={onOpenSettings}>Settings</button>
            <span className="rounded-full bg-[#F1F5F3] px-3 py-2">{dirty ? 'Unsaved changes' : 'Saved'}</span>
            <span>{statusMessage}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function FormulaBar({
  workbook,
  selectedCell,
  formulaInput,
  onFormulaChange,
  onApplyFormula,
  onStyle,
  activeCell,
}: {
  workbook: SpreadsheetWorkbook;
  selectedCell: string;
  formulaInput: string;
  onFormulaChange: (value: string) => void;
  onApplyFormula: () => Promise<void>;
  onStyle: (patch: Partial<SpreadsheetCell['style']>) => void;
  activeCell?: SpreadsheetCell;
}) {
  return (
    <div className="rounded-3xl border border-[#DDE5E2] bg-white/95 px-4 py-4 shadow-sm">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="rounded-xl border border-[#DDE5E2] bg-[#F1F5F3] px-3 py-2 text-sm font-medium">{selectedCell}</div>
        <input
          value={formulaInput}
          onChange={(event) => onFormulaChange(event.target.value)}
          className="min-w-[320px] flex-1 rounded-xl border border-[#DDE5E2] bg-white px-4 py-2.5 text-sm outline-none focus:border-[#00684A]"
          placeholder="Enter a value or formula starting with ="
        />
        <button className="rounded-xl bg-[#00684A] px-4 py-2.5 text-sm font-medium text-white" onClick={() => void onApplyFormula()}>
          Apply
        </button>
        <button className="rounded-xl border border-[#DDE5E2] bg-white px-4 py-2.5 text-sm font-medium" onClick={() => onFormulaChange(activeCell ? cellMatchesFormula(activeCell) : formulaInput)}>
          Cancel
        </button>
        <button className="rounded-xl border border-[#DDE5E2] bg-white px-4 py-2.5 text-sm font-medium" onClick={() => window.alert(mockAiResponse('Explain this formula'))}>
          Explain Formula
        </button>
        <button className="rounded-xl border border-[#DDE5E2] bg-white px-4 py-2.5 text-sm font-medium" onClick={() => window.alert(mockAiResponse('Fix formula'))}>
          Fix Formula
        </button>
      </div>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <ToggleFormat label="Bold" onClick={() => onStyle({ bold: !(activeCell?.style.bold ?? false) })} active={activeCell?.style.bold ?? false} />
        <ToggleFormat label="Italic" onClick={() => onStyle({ italic: !(activeCell?.style.italic ?? false) })} active={activeCell?.style.italic ?? false} />
        <ToggleFormat label="Underline" onClick={() => onStyle({ underline: !(activeCell?.style.underline ?? false) })} active={activeCell?.style.underline ?? false} />
        <ToggleFormat label="Left" onClick={() => onStyle({ align: 'left' })} active={(activeCell?.style.align ?? 'left') === 'left'} />
        <ToggleFormat label="Center" onClick={() => onStyle({ align: 'center' })} active={activeCell?.style.align === 'center'} />
        <ToggleFormat label="Right" onClick={() => onStyle({ align: 'right' })} active={activeCell?.style.align === 'right'} />
        <ToggleFormat label="Wrap" onClick={() => onStyle({ wrap: !(activeCell?.style.wrap ?? false) })} active={activeCell?.style.wrap ?? false} />
      </div>
    </div>
  );
}

function ToggleFormat({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`rounded-lg border px-3 py-1.5 text-xs font-medium ${active ? 'border-[#00684A] bg-[#E3FCF0] text-[#00684A]' : 'border-[#DDE5E2] bg-white text-[#001E2B]'}`}
    >
      {label}
    </button>
  );
}

function SpreadsheetGrid({
  workbook,
  selectedCell,
  onSelectCell,
  onCellMove,
  onAskAi,
}: {
  workbook: SpreadsheetWorkbook;
  selectedCell: string;
  onSelectCell: (ref: string) => void;
  onCellMove: (deltaRow: number, deltaColumn: number) => void;
  onAskAi: (prompt: string) => void;
}) {
  const sheet = getActiveSheet(workbook);
  const rowCount = Math.max(sheet.rowCount, 20);
  const columnCount = Math.max(sheet.columnCount, 10);
  const [editingCell, setEditingCell] = useState<string | null>(null);
  const [draft, setDraft] = useState('');

  return (
    <div
      className="min-h-0 overflow-auto"
      onKeyDown={(event) => {
        if (event.key === 'ArrowUp') {
          event.preventDefault();
          onCellMove(-1, 0);
        }
        if (event.key === 'ArrowDown') {
          event.preventDefault();
          onCellMove(1, 0);
        }
        if (event.key === 'ArrowLeft') {
          event.preventDefault();
          onCellMove(0, -1);
        }
        if (event.key === 'ArrowRight') {
          event.preventDefault();
          onCellMove(0, 1);
        }
        if (event.key === 'Enter') {
          setDraft(cellMatchesFormula(sheet.cells[selectedCell]));
          setEditingCell(selectedCell);
        }
      }}
      tabIndex={0}
    >
      <div className="min-w-max p-6">
        <div className="grid" style={{ gridTemplateColumns: `56px repeat(${columnCount}, minmax(120px, 1fr))` }}>
          <div className="sticky left-0 top-0 z-20 border border-[#DDE5E2] bg-[#F7F9F8]" />
          {Array.from({ length: columnCount }, (_, index) => (
            <div key={index} className="sticky top-0 z-10 border border-[#DDE5E2] bg-[#F7F9F8] px-3 py-2 text-center text-xs font-semibold text-[#5C6C75]">
              {columnName(index)}
            </div>
          ))}

          {Array.from({ length: rowCount }, (_, rowIndex) => {
            const rowNumber = rowIndex + 1;
            return (
              <>
                <div key={`r-${rowNumber}`} className="sticky left-0 z-10 border border-[#DDE5E2] bg-[#F7F9F8] px-3 py-2 text-center text-xs font-semibold text-[#5C6C75]">
                  {rowNumber}
                </div>
                {Array.from({ length: columnCount }, (_, columnIndex) => {
                  const ref = cellRef(rowIndex, columnIndex);
                  const cell = sheet.cells[ref];
                  const selected = selectedCell === ref;
                  const editing = editingCell === ref;
                  return (
                    <div
                      key={ref}
                      className={`group relative min-h-[42px] border border-[#DDE5E2] bg-white px-3 py-2 text-sm ${selected ? 'ring-2 ring-[#00684A] ring-inset' : ''}`}
                      style={{
                        backgroundColor: cell?.style.backgroundColor ?? '#FFFFFF',
                        color: cell?.style.textColor ?? '#001E2B',
                        textAlign: cell?.style.align ?? 'left',
                        fontWeight: cell?.style.bold ? 600 : 400,
                        fontStyle: cell?.style.italic ? 'italic' : 'normal',
                        textDecoration: cell?.style.underline ? 'underline' : 'none',
                        whiteSpace: cell?.style.wrap ? 'normal' : 'nowrap',
                      }}
                      onClick={() => onSelectCell(ref)}
                      onDoubleClick={() => {
                        setDraft(cellMatchesFormula(cell));
                        setEditingCell(ref);
                        onSelectCell(ref);
                      }}
                    >
                      {editing ? (
                        <input
                          autoFocus
                          value={draft}
                          onChange={(event) => setDraft(event.target.value)}
                          onBlur={async () => {
                            await window.xelora.setUnsavedChanges(true);
                            setEditingCell(null);
                            onAskAi('Explain this formula');
                          }}
                          onKeyDown={async (event) => {
                            if (event.key === 'Enter') {
                              event.preventDefault();
                              const value = draft;
                              const formula = value.startsWith('=') ? value.slice(1) : undefined;
                              await useDesktopStore.getState().editSelectedCell(value, formula);
                              setEditingCell(null);
                            }
                            if (event.key === 'Escape') {
                              setEditingCell(null);
                            }
                          }}
                          className="w-full border-none bg-transparent outline-none"
                        />
                      ) : (
                        <div className="truncate">{cellMatchesFormula(cell)}</div>
                      )}
                    </div>
                  );
                })}
              </>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function HomeScreen({
  metrics,
  recentFiles,
  version,
  onOpenFile,
  onImportCsv,
  onNewWorkbook,
  onOpenCloudFile,
  onRunWorkflow,
  onSampleWorkbook,
  sessionName,
}: {
  metrics: Array<{ label: string; value: string; delta: string }>;
  recentFiles: { filePath: string; fileName: string; fileType: string; sizeBytes: number; lastOpenedAt: string; exists: boolean }[];
  version: string;
  onOpenFile: () => void | Promise<void>;
  onImportCsv: () => void | Promise<void>;
  onNewWorkbook: () => void;
  onOpenCloudFile: () => void;
  onRunWorkflow: () => void;
  onSampleWorkbook: () => void;
  sessionName: string;
}) {
  return (
    <div className="h-full overflow-auto bg-[#EEF3F0] p-4">
      <div className="mb-8">
        <div className="text-sm uppercase tracking-[0.3em] text-[#889397]">Home</div>
        <h1 className="mt-2 text-3xl font-semibold">Welcome back, {sessionName}</h1>
        <p className="mt-2 max-w-2xl text-[#5C6C75]">Use local spreadsheets, mock workflow automation, and the Xelora AI assistant while the cloud backend is being connected.</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric) => (
          <div key={metric.label} className="rounded-2xl border border-[#DDE5E2] bg-white p-5 shadow-sm">
            <div className="text-sm text-[#5C6C75]">{metric.label}</div>
            <div className="mt-2 text-3xl font-semibold">{metric.value}</div>
            <div className="mt-2 text-xs text-[#00684A]">{metric.delta}</div>
          </div>
        ))}
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <div className="rounded-2xl border border-[#DDE5E2] bg-white p-5 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <div className="text-lg font-semibold">Quick actions</div>
              <div className="text-sm text-[#5C6C75]">Open files or start from a demo workbook.</div>
            </div>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <ActionCard title="Open Spreadsheet" description="Choose an .xlsx workbook from your computer." icon={<PackageOpen />} onClick={onOpenFile} />
            <ActionCard title="Import CSV" description="Open a CSV file and convert it into a workbook." icon={<Upload />} onClick={onImportCsv} />
            <ActionCard title="Create New Workbook" description="Start with a blank local workbook." icon={<Plus />} onClick={onNewWorkbook} />
            <ActionCard title="Try Sample Workbook" description="Open a built-in local demo workbook." icon={<BookOpen />} onClick={onSampleWorkbook} />
            <ActionCard title="Open Cloud File" description="Future integration with Xelora Cloud." icon={<CloudOff />} onClick={onOpenCloudFile} />
            <ActionCard title="Run Saved Workflow" description="Execute a deterministic local workflow simulation." icon={<GitBranch />} onClick={onRunWorkflow} />
          </div>
        </div>

        <div className="rounded-2xl border border-[#DDE5E2] bg-white p-5 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <div className="text-lg font-semibold">Recent files</div>
              <div className="text-sm text-[#5C6C75]">Stored locally on this device.</div>
            </div>
            <div className="rounded-full bg-[#F1F5F3] px-3 py-1 text-xs text-[#5C6C75]">v{version}</div>
          </div>
          <div className="space-y-3">
            {recentFiles.length === 0 ? (
              <div className="rounded-xl border border-dashed border-[#DDE5E2] bg-[#F7F9F8] p-4 text-sm text-[#5C6C75]">No recent files yet.</div>
            ) : (
              recentFiles.map((file) => (
                <div key={file.filePath} className="rounded-xl border border-[#DDE5E2] p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="font-medium">{file.fileName}</div>
                      <div className="text-xs text-[#5C6C75]">{file.filePath}</div>
                      <div className="mt-2 text-xs text-[#889397]">{file.fileType.toUpperCase()} • {formatBytes(file.sizeBytes)} • {new Date(file.lastOpenedAt).toLocaleString()}</div>
                    </div>
                    <div className="flex flex-col gap-2">
                      <button className="rounded-lg border border-[#DDE5E2] px-3 py-1.5 text-xs" onClick={() => void window.xelora.openRecentFile(file.filePath)}>Open</button>
                      <button className="rounded-lg border border-[#DDE5E2] px-3 py-1.5 text-xs" onClick={() => void window.xelora.removeRecentFile(file.filePath)}>Remove</button>
                    </div>
                  </div>
                  {!file.exists ? (
                    <div className="mt-3 rounded-lg bg-[#FEECEB] px-3 py-2 text-xs text-[#B42318]">
                      This file is no longer available at its previous location.
                    </div>
                  ) : null}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function DesktopPreviewScreen({
  metrics,
  recentFiles,
  version,
  onOpenFile,
  onImportCsv,
  onNewWorkbook,
  onOpenCloudFile,
  onOpenReports,
  onOpenSettings,
  onRunWorkflow,
  onSampleWorkbook,
  onOpenRecentFile,
  sessionName,
}: {
  metrics: Array<{ label: string; value: string; delta: string }>;
  recentFiles: { filePath: string; fileName: string; fileType: string; sizeBytes: number; lastOpenedAt: string; exists: boolean }[];
  version: string;
  onOpenFile: () => void | Promise<void>;
  onImportCsv: () => void | Promise<void>;
  onNewWorkbook: () => void;
  onOpenCloudFile: () => void;
  onOpenReports: () => void;
  onOpenSettings: () => void;
  onRunWorkflow: () => void;
  onSampleWorkbook: () => void;
  onOpenRecentFile: (filePath: string) => void | Promise<void>;
  sessionName: string;
}) {
  const [prompt, setPrompt] = useState('');
  const [quickActionsOpen, setQuickActionsOpen] = useState(false);

  const promptSuggestions = [
    'Clean a spreadsheet',
    'Create a monthly report',
    'Explain a formula',
    'Find duplicate records',
    'Summarise sales by region',
    'Build a reusable workflow',
  ];

  type PreviewTaskTone = 'running' | 'approval' | 'success';

  interface PreviewTaskItem {
    title: string;
    meta: string;
    tone: PreviewTaskTone;
    icon: React.ReactNode;
  }

  const tasks: PreviewTaskItem[] = recentFiles.length > 0
    ? recentFiles.slice(0, 3).map((file, index) => {
      const tone = index === 0 ? 'running' : index === 1 ? 'approval' : 'success';
      const title = file.fileName.replace(/\.[^.]+$/, '') || `Recent file ${index + 1}`;
      const date = new Intl.DateTimeFormat('en-GB', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
      }).format(new Date(file.lastOpenedAt));

      return {
        title,
        meta: `${file.fileName} · ${date}`,
        tone,
        icon: tone === 'running' ? <Clock3 className="h-4 w-4" /> : tone === 'approval' ? <CircleAlert className="h-4 w-4" /> : <Check className="h-4 w-4" />,
      };
    })
    : [
        { title: 'July Sales Cleanup', meta: 'Sales_Q3_2026.xlsx · 6d ago', tone: 'running' as const, icon: <Clock3 className="h-4 w-4" /> },
        { title: 'Payroll Report', meta: 'Payroll_June_2026.xlsx · 23 Jul 2026', tone: 'approval' as const, icon: <CircleAlert className="h-4 w-4" /> },
        { title: 'Expense Summary', meta: 'Expenses_Q2.xlsx · 22 Jul 2026', tone: 'success' as const, icon: <Check className="h-4 w-4" /> },
      ];

  const avatarInitials = sessionName
    .split(' ')
    .map((part) => part[0] ?? '')
    .join('')
    .slice(0, 2)
    .toUpperCase() || 'XD';

  const recentItems = recentFiles.length > 0
    ? recentFiles.slice(0, 4)
    : [
        {
          filePath: 'sample-1',
          fileName: 'Sales_Q3_2026.xlsx',
          fileType: 'xlsx',
          sizeBytes: 0,
          lastOpenedAt: '2026-07-24T00:00:00.000Z',
          exists: true,
        },
        {
          filePath: 'sample-2',
          fileName: 'Payroll_June_2026.xlsx',
          fileType: 'xlsx',
          sizeBytes: 0,
          lastOpenedAt: '2026-07-23T00:00:00.000Z',
          exists: true,
        },
      ];

  const quickActions = [
    { label: 'Open workbook', icon: <PackageOpen className="h-4 w-4" />, onClick: onOpenFile },
    { label: 'Import CSV', icon: <Upload className="h-4 w-4" />, onClick: onImportCsv },
    { label: 'New workbook', icon: <Plus className="h-4 w-4" />, onClick: onNewWorkbook },
    { label: 'Sample file', icon: <Download className="h-4 w-4" />, onClick: onSampleWorkbook },
    { label: 'Reports', icon: <BarChart3 className="h-4 w-4" />, onClick: onOpenReports },
    { label: 'Settings', icon: <Settings2 className="h-4 w-4" />, onClick: onOpenSettings },
    { label: 'Run workflow', icon: <ListTodo className="h-4 w-4" />, onClick: onRunWorkflow },
    { label: 'Cloud files', icon: <CloudOff className="h-4 w-4" />, onClick: onOpenCloudFile },
  ] as const;

  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setQuickActionsOpen(false);
      }
    };

    if (quickActionsOpen) {
      window.addEventListener('keydown', handleEscape);
    }

    return () => window.removeEventListener('keydown', handleEscape);
  }, [quickActionsOpen]);

  return (
    <div className="relative flex h-full min-h-0 flex-col overflow-hidden bg-[#EEF3F0] text-[#001E2B]">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,_rgba(0,104,74,0.10),_transparent_32%),radial-gradient(circle_at_bottom_left,_rgba(0,237,100,0.10),_transparent_30%)]" />

      <header className="relative flex items-center justify-between border-b border-[#DCE5E2] bg-white/90 px-5 py-4 backdrop-blur">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#001E2B] text-white shadow-[0_10px_24px_rgba(0,30,43,0.16)]">
            <FileSpreadsheet className="h-5 w-5" />
          </div>
          <div>
            <div className="text-xs uppercase tracking-[0.24em] text-[#7A8E98]">Desktop workspace</div>
            <div className="text-lg font-semibold text-[#001E2B]">Xelora</div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="rounded-full border border-[#DDE5E2] bg-white px-3 py-1 text-xs text-[#5C6C75]">v{version}</span>
          <span className="rounded-full border border-[#DDE5E2] bg-white px-3 py-1 text-xs text-[#5C6C75]">
            {recentFiles.length} recent
          </span>
          <span className="rounded-full border border-[#DDE5E2] bg-white px-3 py-1 text-xs text-[#5C6C75]">
            {sessionName}
          </span>
        </div>
      </header>

      <main className="relative mx-auto grid w-full max-w-[1280px] flex-1 gap-6 px-5 py-5 lg:grid-cols-[minmax(0,1.3fr)_340px]">
        <section className="flex min-w-0 flex-col rounded-[28px] border border-[#DDE5E2] bg-white/92 p-7 shadow-[0_12px_36px_rgba(0,30,43,0.08)] backdrop-blur">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-2xl">
              <div className="text-xs uppercase tracking-[0.24em] text-[#7A8E98]">Simple start</div>
              <h1 className="mt-2 text-4xl font-semibold tracking-[-0.05em] text-[#001E2B]">
                What would you like to do?
              </h1>
              <p className="mt-3 text-base leading-7 text-[#5C6C75]">
                Open a workbook, start a new one, or ask Xelora to handle the spreadsheet work with a calm,
                guided flow.
              </p>
            </div>

            <button
              type="button"
              onClick={() => setQuickActionsOpen((value) => !value)}
              aria-expanded={quickActionsOpen}
              aria-controls="xelora-quick-actions"
              className="inline-flex items-center gap-2 rounded-full border border-[#DDE5E2] bg-[#F7F9F8] px-4 py-2 text-sm font-medium text-[#001E2B] transition hover:border-[#B8C4C0] hover:bg-white"
            >
              <Sparkles className="h-4 w-4 text-[#00684A]" />
              Quick actions
            </button>
          </div>

          <div className="mt-7 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {quickActions.slice(0, 4).map((action) => (
              <button
                key={action.label}
                type="button"
                onClick={() => void action.onClick()}
                className="flex items-center gap-3 rounded-2xl border border-[#DDE5E2] bg-[#F8FAF9] px-4 py-3 text-left transition hover:border-[#B8C4C0] hover:bg-white"
              >
                <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[#001E2B] text-white">
                  {action.icon}
                </span>
                <span>
                  <span className="block text-sm font-medium text-[#001E2B]">{action.label}</span>
                  <span className="block text-xs text-[#5C6C75]">Open in one click</span>
                </span>
              </button>
            ))}
          </div>

          <div className="mt-7 rounded-[24px] border border-[#DDE5E2] bg-[#F8FAF9] p-5">
            <div className="flex items-center justify-between gap-4">
              <div>
                <div className="text-xs uppercase tracking-[0.22em] text-[#7A8E98]">Command</div>
                <div className="mt-1 text-sm font-medium text-[#001E2B]">Describe the work, keep it simple</div>
              </div>
              <button
                type="button"
                onClick={() => {
                  setPrompt('');
                  onRunWorkflow();
                }}
                className="inline-flex items-center gap-2 rounded-full bg-[#00684A] px-4 py-2 text-sm font-medium text-white shadow-[0_10px_20px_rgba(0,104,74,0.16)] transition hover:bg-[#025f46]"
              >
                <ArrowRight className="h-4 w-4" />
                Run
              </button>
            </div>

            <textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              placeholder="Describe the spreadsheet work you need..."
              className="mt-4 min-h-[140px] w-full resize-none rounded-2xl border border-[#DDE5E2] bg-white px-4 py-4 text-[15px] text-[#001E2B] outline-none placeholder:text-[#6B8593]"
            />

            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={onOpenFile}
                className="inline-flex items-center gap-2 rounded-full border border-[#DDE5E2] bg-white px-4 py-2 text-sm text-[#3B5A68] transition hover:border-[#B8C4C0] hover:bg-[#F7FAF8]"
              >
                <FolderOpen className="h-4 w-4" />
                Open spreadsheet
              </button>
              <button
                type="button"
                onClick={onImportCsv}
                className="inline-flex items-center gap-2 rounded-full border border-[#DDE5E2] bg-white px-4 py-2 text-sm text-[#3B5A68] transition hover:border-[#B8C4C0] hover:bg-[#F7FAF8]"
              >
                <Upload className="h-4 w-4" />
                Import CSV
              </button>
              <button
                type="button"
                onClick={onNewWorkbook}
                className="inline-flex items-center gap-2 rounded-full border border-[#DDE5E2] bg-white px-4 py-2 text-sm text-[#3B5A68] transition hover:border-[#B8C4C0] hover:bg-[#F7FAF8]"
              >
                <Plus className="h-4 w-4" />
                New workbook
              </button>
            </div>
          </div>

          <div className="mt-7 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {metrics.map((metric) => (
              <div key={metric.label} className="rounded-2xl border border-[#DDE5E2] bg-white p-4">
                <div className="text-xs uppercase tracking-[0.18em] text-[#7A8E98]">{metric.label}</div>
                <div className="mt-2 text-2xl font-semibold text-[#001E2B]">{metric.value}</div>
                <div className="mt-1 text-xs text-[#5C6C75]">{metric.delta}</div>
              </div>
            ))}
          </div>
        </section>

        <aside className="flex min-w-0 flex-col gap-4">
          <div className="rounded-[28px] border border-[#0A352F] bg-[#001E2B] p-6 text-white shadow-[0_12px_36px_rgba(0,30,43,0.18)]">
            <div className="text-xs uppercase tracking-[0.24em] text-[#99B2B0]">At a glance</div>
            <div className="mt-2 text-2xl font-semibold">A clean starting point</div>
            <p className="mt-3 text-sm leading-6 text-[#C7D2D0]">
              Keep the first screen calm. Open a file or use the floating actions button when you need the extra tools.
            </p>

            <div className="mt-5 grid gap-2">
              {recentItems.slice(0, 2).map((file) => (
                <button
                  key={file.filePath}
                  type="button"
                  onClick={() => void onOpenRecentFile(file.filePath)}
                  className="flex items-center justify-between rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-left transition hover:bg-white/10"
                >
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium text-white">{file.fileName}</div>
                    <div className="mt-1 text-xs text-[#AFC3C0]">
                      {file.exists ? 'Available locally' : 'Moved or missing'}
                    </div>
                  </div>
                  <ArrowRight className="h-4 w-4 shrink-0 text-[#BFE8D6]" />
                </button>
              ))}
            </div>
          </div>

          <div className="rounded-[28px] border border-[#DDE5E2] bg-white p-6 shadow-[0_12px_28px_rgba(0,30,43,0.06)]">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-xs uppercase tracking-[0.22em] text-[#7A8E98]">Recent files</div>
                <div className="mt-1 text-lg font-semibold text-[#001E2B]">Continue where you left off</div>
              </div>
              <Clock3 className="h-5 w-5 text-[#00684A]" />
            </div>

            <div className="mt-4 space-y-2">
              {recentItems.map((file) => (
                <button
                  key={file.filePath}
                  type="button"
                  onClick={() => void onOpenRecentFile(file.filePath)}
                  className="flex w-full items-center justify-between rounded-2xl border border-[#DDE5E2] px-4 py-3 text-left transition hover:border-[#B8C4C0] hover:bg-[#F8FAF9]"
                >
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium text-[#001E2B]">{file.fileName}</div>
                    <div className="mt-1 text-xs text-[#5C6C75]">
                      {file.exists ? formatBytes(file.sizeBytes) : 'No longer available'}
                    </div>
                  </div>
                  <span className="ml-4 rounded-full bg-[#F1F5F3] px-2.5 py-1 text-[11px] font-medium text-[#5C6C75]">
                    Open
                  </span>
                </button>
              ))}
            </div>

            <div className="mt-4 flex items-center justify-between rounded-2xl bg-[#F8FAF9] px-4 py-3">
              <div>
                <div className="text-sm font-medium text-[#001E2B]">Cloud files</div>
                <div className="text-xs text-[#5C6C75]">Kept out of the way for now</div>
              </div>
              <button
                type="button"
                onClick={onOpenCloudFile}
                className="rounded-full border border-[#DDE5E2] bg-white px-3 py-1.5 text-xs font-medium text-[#001E2B] transition hover:bg-[#F1F5F3]"
              >
                Coming soon
              </button>
            </div>
          </div>
        </aside>
      </main>

      {quickActionsOpen ? (
        <div
          id="xelora-quick-actions"
          className="absolute bottom-6 right-6 z-20 w-[310px] rounded-[28px] border border-[#DDE5E2] bg-white/96 p-4 shadow-[0_24px_50px_rgba(0,30,43,0.18)] backdrop-blur"
        >
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs uppercase tracking-[0.22em] text-[#7A8E98]">Quick actions</div>
              <div className="mt-1 text-sm font-medium text-[#001E2B]">Tap an icon</div>
            </div>
            <button
              type="button"
              onClick={() => setQuickActionsOpen(false)}
              className="rounded-full border border-[#DDE5E2] bg-[#F8FAF9] px-2.5 py-1.5 text-xs text-[#5C6C75] transition hover:bg-white"
            >
              Close
            </button>
          </div>

          <div className="mt-4 grid grid-cols-2 gap-2">
            {quickActions.map((action) => (
              <button
                key={action.label}
                type="button"
                onClick={() => {
                  setQuickActionsOpen(false);
                  void action.onClick();
                }}
                className="group flex flex-col items-center gap-2 rounded-2xl border border-[#DDE5E2] bg-[#F8FAF9] px-4 py-4 text-center transition hover:border-[#B8C4C0] hover:bg-white"
              >
                <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-[#001E2B] text-white transition group-hover:scale-105">
                  {action.icon}
                </span>
                <span className="text-xs font-medium text-[#001E2B]">{action.label}</span>
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <button
        type="button"
        aria-label="Open quick actions"
        aria-expanded={quickActionsOpen}
        onClick={() => setQuickActionsOpen((value) => !value)}
        className="absolute bottom-6 right-6 z-10 flex h-14 w-14 items-center justify-center rounded-full border border-[#DDE5E2] bg-[#001E2B] text-white shadow-[0_16px_36px_rgba(0,30,43,0.22)] transition hover:scale-105 hover:bg-[#0A2B35]"
      >
        <Sparkles className="h-5 w-5" />
      </button>
    </div>
  );

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-[#EEF3F0] text-[#001E2B]">
      <div className="flex min-h-0 flex-1 overflow-hidden">
        <aside className="flex w-[58px] shrink-0 flex-col items-center justify-between bg-[#051924] px-2 py-3">
          <div className="flex flex-col items-center gap-3">
            <PreviewRailButton active icon={<Home className="h-5 w-5" />} label="Home" />
            <PreviewRailButton icon={<FolderOpen className="h-5 w-5" />} label="Files" onClick={onOpenFile} />
            <PreviewRailButton icon={<Sparkles className="h-5 w-5" />} label="AI" onClick={onSampleWorkbook} />
            <PreviewRailButton icon={<ListTodo className="h-5 w-5" />} label="Tasks" onClick={onRunWorkflow} />
            <PreviewRailButton icon={<BarChart3 className="h-5 w-5" />} label="Reports" onClick={onOpenReports} />
            <PreviewRailButton icon={<LayoutGrid className="h-5 w-5" />} label="CSV" onClick={onImportCsv} />
            <PreviewRailButton icon={<Clock3 className="h-5 w-5" />} label="Recent" />
          </div>

          <div className="flex flex-col items-center gap-3">
            <PreviewRailButton icon={<Bell className="h-5 w-5" />} label="Notifications" />
            <PreviewRailButton icon={<Settings2 className="h-5 w-5" />} label="Settings" onClick={onOpenSettings} />
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#0C7A58] text-[12px] font-semibold text-white shadow-[0_8px_24px_rgba(0,237,100,0.24)]">
              {avatarInitials}
            </div>
          </div>
        </aside>

        <aside className="flex w-[330px] shrink-0 flex-col border-r border-[#DCE5E2] bg-white px-4 py-4">
          <button
            type="button"
            onClick={onNewWorkbook}
            className="inline-flex h-[46px] items-center gap-2 rounded-md bg-[#00684A] px-4 text-[18px] font-medium text-white shadow-[0_8px_20px_rgba(0,104,74,0.14)] transition hover:bg-[#025f46]"
          >
            <Plus className="h-5 w-5" />
            <span className="text-[16px]">New Task</span>
          </button>

          <div className="mt-6 space-y-6 overflow-auto pr-1">
            <PreviewTaskSection
              label="Running"
              items={[
                {
                  title: 'July Sales Cleanup',
                  meta: 'Running · 6d Ago',
                  icon: <Clock3 className="h-4 w-4" />,
                  tone: 'running',
                },
              ]}
            />

            <PreviewTaskSection
              label="Needs Approval"
              items={[
                {
                  title: 'Payroll Report',
                  meta: 'Awaiting Approval · 23 Jul 2026',
                  icon: <CircleAlert className="h-4 w-4" />,
                  tone: 'approval',
                },
              ]}
            />

            <PreviewTaskSection label="Recent" items={tasks} />
          </div>
        </aside>

        <section className="flex min-w-0 flex-1 flex-col bg-white">
          <header className="flex h-[38px] items-center border-b border-[#DCE5E2] bg-white px-4 text-[14px] text-[#4E6470]">
            <button
              type="button"
              className="mr-3 inline-flex h-7 w-7 items-center justify-center rounded-md border border-transparent text-[#4E6470] transition hover:bg-[#F1F5F3]"
            >
              <PanelLeftClose className="h-4 w-4" />
            </button>
            <span className="font-medium text-[#3A5360]">Xelora Desktop</span>
          </header>

          <div className="min-h-0 flex-1 overflow-auto bg-[#FCFDFC] px-8 py-8">
            <div className="mx-auto flex w-full max-w-[1030px] flex-col items-center">
              <div className="pt-6 text-center">
                <h1 className="text-[31px] font-semibold tracking-[-0.04em] text-[#001E2B]">
                  What would you like to do with your spreadsheet?
                </h1>
                <p className="mt-4 text-[18px] text-[#5C6C75]">
                  Open a workbook or describe the task you want Xelora to complete.
                </p>
              </div>

              <div className="mt-10 w-full max-w-[780px] rounded-[18px] border border-[#D9E3DF] bg-white shadow-[0_10px_32px_rgba(0,30,43,0.08)]">
                <textarea
                  value={prompt}
                  onChange={(event) => setPrompt(event.target.value)}
                  placeholder="Describe the spreadsheet work you need..."
                  className="min-h-[116px] w-full resize-none rounded-t-[18px] border-none px-5 py-5 text-[17px] text-[#001E2B] outline-none placeholder:text-[#6B8593]"
                />
                <div className="border-t border-[#DCE5E2] px-4 py-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={onOpenFile}
                      className="inline-flex items-center gap-2 rounded-lg border border-[#D9E3DF] bg-white px-4 py-2 text-[15px] text-[#3B5A68] transition hover:border-[#B7C7C0] hover:bg-[#F7FAF8]"
                    >
                      <FolderOpen className="h-4 w-4" />
                      Open Spreadsheet
                    </button>
                    <button
                      type="button"
                      onClick={onImportCsv}
                      className="inline-flex items-center gap-2 rounded-lg border border-[#D9E3DF] bg-white px-4 py-2 text-[15px] text-[#3B5A68] transition hover:border-[#B7C7C0] hover:bg-[#F7FAF8]"
                    >
                      <Upload className="h-4 w-4" />
                      Import CSV
                    </button>
                    <div className="ml-auto">
                      <button
                        type="button"
                        onClick={() => {
                          setPrompt('');
                          onRunWorkflow();
                        }}
                        className="inline-flex h-[36px] items-center gap-2 rounded-lg bg-[#9CC9BB] px-4 text-[15px] font-medium text-white transition hover:bg-[#7EB6A4]"
                      >
                        <ArrowRight className="h-4 w-4" />
                        Send
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              <div className="mt-4 flex max-w-[820px] flex-wrap justify-center gap-2">
                {promptSuggestions.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => setPrompt(suggestion)}
                    className="rounded-full border border-[#D9E3DF] bg-white px-4 py-2 text-[15px] text-[#3A5A68] transition hover:border-[#AFC0B8] hover:bg-[#F7FAF8]"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>

              <div className="mt-16 w-full max-w-[820px] border-t border-[#E0E7E4] pt-8">
                <div className="text-[15px] font-semibold uppercase tracking-[0.12em] text-[#7A8E98]">
                  Recent Tasks
                </div>
                <div className="mt-6 space-y-6">
                  {tasks.map((task) => (
                    <div key={`${task.title}-${task.meta}`} className="flex items-center gap-4">
                      <div className={taskToneClasses[task.tone]}>{task.icon}</div>
                      <div className="min-w-0 flex-1">
                        <div className="text-[18px] font-medium text-[#001E2B]">{task.title}</div>
                        <div className="text-[15px] text-[#7B8E98]">{task.meta}</div>
                      </div>
                      <button
                        type="button"
                        className="inline-flex h-10 w-10 items-center justify-center rounded-full text-[#8FA0A7] transition hover:bg-[#F1F5F3] hover:text-[#4B6472]"
                      >
                        <ArrowRight className="h-5 w-5" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          <footer className="flex items-center justify-between border-t border-[#DCE5E2] bg-[#F8FAF9] px-4 py-2 text-[12px] text-[#5E6F78]">
            <div className="flex items-center gap-4">
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-[#90D8AE]" />
                Connected
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-[#76A9FF]" />
                1 running
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-[#F7B84B]" />
                1 awaiting approval
              </span>
            </div>
            <div className="flex items-center gap-2">
              <Zap className="h-4 w-4 text-[#5DAA7D]" />
              <span>Xelora Desktop</span>
              <span className="text-[#9AAAB0]">— frontend simulation</span>
              <span className="ml-2 rounded-full bg-white px-2 py-1 text-[11px] text-[#7B8E98]">v{version}</span>
            </div>
          </footer>
        </section>
      </div>
    </div>
  );
}

function PreviewRailButton({
  icon,
  label,
  active = false,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  active?: boolean;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className={`relative flex h-11 w-11 items-center justify-center rounded-xl transition ${
        active
          ? 'bg-[#0A352F] text-[#00ED64] shadow-[inset_0_0_0_1px_rgba(0,237,100,0.18)]'
          : 'text-[#96A8AF] hover:bg-white/10 hover:text-white'
      }`}
    >
      {active ? <span className="absolute left-0 h-7 w-1 rounded-r-full bg-[#00ED64]" /> : null}
      {icon}
    </button>
  );
}

const taskToneClasses: Record<'running' | 'approval' | 'success', string> = {
  running: 'flex h-10 w-10 items-center justify-center rounded-full text-[#3F86FF]',
  approval: 'flex h-10 w-10 items-center justify-center rounded-full text-[#F8A600]',
  success: 'flex h-10 w-10 items-center justify-center rounded-full text-[#0D8C57]',
};

function PreviewTaskSection({
  label,
  items,
}: {
  label: string;
  items: Array<{
    title: string;
    meta: string;
    tone: 'running' | 'approval' | 'success';
    icon: React.ReactNode;
  }>;
}) {
  return (
    <div>
      <div className="mb-4 text-[13px] font-semibold uppercase tracking-[0.12em] text-[#8B99A4]">
        {label}
      </div>
      <div className="space-y-5">
        {items.map((item) => (
          <button
            key={`${item.title}-${item.meta}`}
            type="button"
            className="flex w-full items-start gap-3 rounded-2xl text-left transition hover:bg-[#F7FAF8]"
          >
            <div className={taskToneClasses[item.tone]}>{item.icon}</div>
            <div className="min-w-0">
              <div className="text-[16px] font-medium text-[#001E2B]">{item.title}</div>
              <div className="mt-1 text-[13px] text-[#7A8D97]">{item.meta}</div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

function ActionCard({ title, description, icon, onClick }: { title: string; description: string; icon: React.ReactNode; onClick: () => void | Promise<void> }) {
  return (
    <button onClick={() => void onClick()} className="rounded-2xl border border-[#DDE5E2] bg-[#F7F9F8] p-4 text-left transition hover:border-[#B8C4C0] hover:bg-white">
      <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-[#001E2B] text-white">{icon}</div>
      <div className="text-sm font-semibold">{title}</div>
      <div className="mt-1 text-sm text-[#5C6C75]">{description}</div>
    </button>
  );
}

function ReportsScreen({
  workbook,
  chartRows,
  onReturn,
}: {
  workbook: SpreadsheetWorkbook | null;
  chartRows: Array<{ name: string; revenue: number }>;
  onReturn: () => void;
}) {
  const summary = getWorkbookStats(workbook);
  const pieData = [
    { name: 'Growth', value: 38 },
    { name: 'Starter', value: 27 },
    { name: 'Enterprise', value: 18 },
    { name: 'Other', value: 17 },
  ];

  return (
    <div className="h-full overflow-auto bg-[#EEF3F0] p-4">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <div className="text-sm uppercase tracking-[0.3em] text-[#889397]">Reports</div>
          <h2 className="mt-2 text-3xl font-semibold">Workbook insights</h2>
        </div>
        <button className="rounded-xl border border-[#DDE5E2] bg-white px-4 py-2 text-sm" onClick={onReturn}>Return to spreadsheet</button>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <MetricCard label="Total sales" value={`$${summary.total.toLocaleString()}`} />
        <MetricCard label="Rows" value={`${summary.rows}`} />
        <MetricCard label="Columns" value={`${summary.columns}`} />
        <MetricCard label="Filled cells" value={`${summary.cells}`} />
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-2">
        <ChartCard title="Revenue by row">
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={chartRows}>
              <CartesianGrid strokeDasharray="3 3" stroke="#DDE5E2" />
              <XAxis dataKey="name" stroke="#5C6C75" />
              <YAxis stroke="#5C6C75" />
              <Tooltip />
              <Bar dataKey="revenue" fill="#00684A" radius={[8, 8, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Revenue trend">
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={chartRows}>
              <CartesianGrid strokeDasharray="3 3" stroke="#DDE5E2" />
              <XAxis dataKey="name" stroke="#5C6C75" />
              <YAxis stroke="#5C6C75" />
              <Tooltip />
              <Line type="monotone" dataKey="revenue" stroke="#00ED64" strokeWidth={3} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Plan mix">
          <ResponsiveContainer width="100%" height={280}>
            <PieChart>
              <Pie data={pieData} dataKey="value" innerRadius={60} outerRadius={95} paddingAngle={3}>
                {pieData.map((entry, index) => (
                  <Cell key={entry.name} fill={['#00684A', '#00ED64', '#023430', '#DDE5E2'][index % 4]} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Mock AI insights">
          <div className="space-y-3 text-sm text-[#5C6C75]">
            <div className="rounded-xl border border-[#DDE5E2] bg-[#F7F9F8] p-4">Highest-performing district: Kigali</div>
            <div className="rounded-xl border border-[#DDE5E2] bg-[#F7F9F8] p-4">Growth rate: +12.8% month-over-month</div>
            <div className="rounded-xl border border-[#DDE5E2] bg-[#F7F9F8] p-4">Average order value: ${summary.average.toFixed(2)}</div>
            <div className="rounded-xl border border-[#DDE5E2] bg-[#F7F9F8] p-4">Export, create summary sheet, or add a chart to the workbook when ready.</div>
          </div>
        </ChartCard>
      </div>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-[#DDE5E2] bg-white p-5 shadow-sm">
      <div className="text-sm text-[#5C6C75]">{label}</div>
      <div className="mt-2 text-3xl font-semibold">{value}</div>
    </div>
  );
}

function ChartCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-[#DDE5E2] bg-white p-5 shadow-sm">
      <div className="mb-4 text-lg font-semibold">{title}</div>
      {children}
    </div>
  );
}

function CleaningScreen({
  workbook,
  onReturn,
  onCleanTrim,
  onFillMissing,
}: {
  workbook: SpreadsheetWorkbook | null;
  onReturn: () => void;
  onCleanTrim: () => void;
  onFillMissing: () => void;
}) {
  return (
    <div className="h-full overflow-auto p-6">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <div className="text-sm uppercase tracking-[0.3em] text-[#889397]">Data cleaning</div>
          <h2 className="mt-2 text-3xl font-semibold">Clean the current workbook</h2>
        </div>
        <button className="rounded-xl border border-[#DDE5E2] bg-white px-4 py-2 text-sm" onClick={onReturn}>Return to spreadsheet</button>
      </div>

      <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
        <div className="rounded-2xl border border-[#DDE5E2] bg-white p-5 shadow-sm">
          <div className="mb-4 text-lg font-semibold">Cleaning rules</div>
          <div className="space-y-3">
            <button className="w-full rounded-xl border border-[#DDE5E2] bg-[#F7F9F8] px-4 py-3 text-left" onClick={onCleanTrim}>Trim spaces</button>
            <button className="w-full rounded-xl border border-[#DDE5E2] bg-[#F7F9F8] px-4 py-3 text-left" onClick={onFillMissing}>Fill missing values</button>
            <button className="w-full rounded-xl border border-[#DDE5E2] bg-[#F7F9F8] px-4 py-3 text-left" onClick={() => window.alert('Duplicate detection preview is available in a future refinement.')}>Remove duplicates</button>
            <button className="w-full rounded-xl border border-[#DDE5E2] bg-[#F7F9F8] px-4 py-3 text-left" onClick={() => window.alert('Capitalisation standardisation preview is available in a future refinement.')}>Standardise capitalisation</button>
            <button className="w-full rounded-xl border border-[#DDE5E2] bg-[#F7F9F8] px-4 py-3 text-left" onClick={() => window.alert('Date normalisation preview is available in a future refinement.')}>Standardise dates</button>
          </div>
        </div>

        <div className="rounded-2xl border border-[#DDE5E2] bg-white p-5 shadow-sm">
          <div className="mb-4 text-lg font-semibold">Before and after preview</div>
          <div className="grid gap-4 md:grid-cols-2">
            <PreviewBox title="Before" workbook={workbook} />
            <PreviewBox title="After" workbook={workbook} />
          </div>
        </div>
      </div>
    </div>
  );
}

function PreviewBox({ title, workbook }: { title: string; workbook: SpreadsheetWorkbook | null }) {
  const sheet = workbook ? getActiveSheet(workbook) : null;
  return (
    <div className="rounded-2xl border border-[#DDE5E2] bg-[#F7F9F8] p-4">
      <div className="mb-3 font-medium">{title}</div>
      <div className="space-y-2 text-sm text-[#5C6C75]">
        {sheet ? (
          Object.entries(sheet.cells)
            .slice(0, 6)
            .map(([ref, cell]) => (
              <div key={ref} className="flex items-center justify-between rounded-lg bg-white px-3 py-2">
                <span>{ref}</span>
                <span className="max-w-[180px] truncate">{cellMatchesFormula(cell)}</span>
              </div>
            ))
        ) : (
          <div className="rounded-lg bg-white px-3 py-2">Open a workbook to preview cleaning changes.</div>
        )}
      </div>
    </div>
  );
}

function SettingsScreen({
  form,
  onSave,
  onClose,
}: {
  form: UseFormReturn<SettingsFormInput, unknown, SettingsFormValues>;
  onSave: (values: SettingsFormValues) => Promise<void>;
  onClose: () => void;
}) {
  const [tab, setTab] = useState<'general' | 'files' | 'ai' | 'privacy' | 'application'>('general');

  return (
    <div className="h-full overflow-auto p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <div className="text-sm uppercase tracking-[0.3em] text-[#889397]">Settings</div>
          <h2 className="mt-2 text-3xl font-semibold">Application settings</h2>
        </div>
        <button className="rounded-xl border border-[#DDE5E2] bg-white px-4 py-2 text-sm" onClick={onClose}>Close</button>
      </div>

      <form className="grid gap-6 xl:grid-cols-[240px_minmax(0,1fr)]" onSubmit={form.handleSubmit(async (values) => onSave(values))}>
        <div className="rounded-2xl border border-[#DDE5E2] bg-white p-4 shadow-sm">
          {(['general', 'files', 'ai', 'privacy', 'application'] as const).map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => setTab(item)}
              className={`mb-2 w-full rounded-xl px-4 py-3 text-left text-sm font-medium ${tab === item ? 'bg-[#001E2B] text-white' : 'bg-[#F1F5F3] text-[#001E2B]'}`}
            >
              {item[0].toUpperCase() + item.slice(1)}
            </button>
          ))}
        </div>

        <div className="rounded-2xl border border-[#DDE5E2] bg-white p-6 shadow-sm">
          {tab === 'general' ? (
            <SettingsSection title="General">
              <InputRow label="Language" {...form.register('general.language')} />
              <SelectRow label="Theme" {...form.register('general.theme')} options={['light', 'system']} />
              <SelectRow label="Start page" {...form.register('general.startPage')} options={['welcome', 'dashboard', 'last-workbook']} />
              <ToggleRow label="Restore previous session" checked={form.watch('general.restorePreviousSession')} onChange={(checked) => form.setValue('general.restorePreviousSession', checked)} />
              <InputRow label="Default save folder" {...form.register('general.defaultSaveFolder')} />
            </SettingsSection>
          ) : null}

          {tab === 'files' ? (
            <SettingsSection title="Files">
              <ToggleRow label="Auto-save" checked={form.watch('files.autoSave')} onChange={(checked) => form.setValue('files.autoSave', checked)} />
              <InputRow label="Auto-save interval (minutes)" type="number" {...form.register('files.autoSaveIntervalMinutes')} />
              <ToggleRow label="Create backup before automation" checked={form.watch('files.createBackupBeforeAutomation')} onChange={(checked) => form.setValue('files.createBackupBeforeAutomation', checked)} />
              <InputRow label="Recent-files limit" type="number" {...form.register('files.recentFilesLimit')} />
            </SettingsSection>
          ) : null}

          {tab === 'ai' ? (
            <SettingsSection title="AI">
              <SelectRow label="Explanation level" {...form.register('ai.explanationLevel')} options={['brief', 'balanced', 'detailed']} />
              <SelectRow label="Approval level" {...form.register('ai.approvalLevel')} options={['low', 'medium', 'high']} />
              <SelectRow label="Default context" {...form.register('ai.defaultContext')} options={['selected-cell', 'selected-range', 'worksheet', 'workbook']} />
              <ToggleRow label="Destructive-action confirmation" checked={form.watch('ai.destructiveActionConfirmation')} onChange={(checked) => form.setValue('ai.destructiveActionConfirmation', checked)} />
            </SettingsSection>
          ) : null}

          {tab === 'privacy' ? (
            <SettingsSection title="Privacy">
              <ToggleRow label="Prefer local processing" checked={form.watch('privacy.localProcessingPreference')} onChange={(checked) => form.setValue('privacy.localProcessingPreference', checked)} />
              <ToggleRow label="Cloud processing placeholder" checked={form.watch('privacy.cloudProcessingPlaceholder')} onChange={(checked) => form.setValue('privacy.cloudProcessingPlaceholder', checked)} />
              <ToggleRow label="Clear recent files on sign-out" checked={form.watch('privacy.clearRecentFilesOnSignOut')} onChange={(checked) => form.setValue('privacy.clearRecentFilesOnSignOut', checked)} />
              <ToggleRow label="Clear local history on sign-out" checked={form.watch('privacy.clearLocalHistoryOnSignOut')} onChange={(checked) => form.setValue('privacy.clearLocalHistoryOnSignOut', checked)} />
            </SettingsSection>
          ) : null}

          {tab === 'application' ? (
            <SettingsSection title="Application">
              <InputRow label="Application version" {...form.register('application.version')} />
              <ToggleRow label="Check for updates" checked={form.watch('application.checkForUpdates')} onChange={(checked) => form.setValue('application.checkForUpdates', checked)} />
              <SelectRow label="Release channel" {...form.register('application.releaseChannel')} options={['stable', 'beta']} />
              <ToggleRow label="Show logs path" checked={form.watch('application.showLogsPath')} onChange={(checked) => form.setValue('application.showLogsPath', checked)} />
              <ToggleRow label="Reset application" checked={form.watch('application.resetApplication')} onChange={(checked) => form.setValue('application.resetApplication', checked)} />
            </SettingsSection>
          ) : null}

          <div className="mt-6 flex justify-end gap-2">
            <button type="button" className="rounded-xl border border-[#DDE5E2] px-4 py-2.5 text-sm" onClick={onClose}>Cancel</button>
            <button type="submit" className="rounded-xl bg-[#00684A] px-4 py-2.5 text-sm font-medium text-white">Save settings</button>
          </div>
        </div>
      </form>
    </div>
  );
}

function SettingsSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="mb-4 text-xl font-semibold">{title}</h3>
      <div className="grid gap-4">{children}</div>
    </div>
  );
}

function InfoCard({ title, description }: { title: string; description: string }) {
  return (
    <div className="rounded-2xl border border-white/15 bg-white/8 p-4 shadow-sm">
      <div className="text-sm font-semibold text-white">{title}</div>
      <p className="mt-1 text-sm text-white/70">{description}</p>
    </div>
  );
}

function InputRow(props: React.InputHTMLAttributes<HTMLInputElement> & { label: string }) {
  const { label, ...rest } = props;
  return (
    <label className="grid gap-2 text-sm">
      <span className="font-medium">{label}</span>
      <input {...rest} className="rounded-xl border border-[#DDE5E2] px-4 py-3 outline-none focus:border-[#00684A]" />
    </label>
  );
}

function SelectRow({ label, options, ...rest }: React.SelectHTMLAttributes<HTMLSelectElement> & { label: string; options: string[] }) {
  return (
    <label className="grid gap-2 text-sm">
      <span className="font-medium">{label}</span>
      <select {...rest} className="rounded-xl border border-[#DDE5E2] px-4 py-3 outline-none focus:border-[#00684A]">
        {options.map((option) => (
          <option key={option} value={option}>{option}</option>
        ))}
      </select>
    </label>
  );
}

function ToggleRow({ label, checked, onChange }: { label: string; checked: boolean; onChange: (checked: boolean) => void }) {
  return (
    <label className="flex items-center justify-between gap-4 rounded-xl border border-[#DDE5E2] px-4 py-3 text-sm">
      <span className="font-medium">{label}</span>
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
    </label>
  );
}

function RightRail({
  active,
  workbook,
  prompt,
  onPromptChange,
  onAsk,
  onSuggestion,
  selectedSuggestion,
  onOpenReports,
  onOpenSettings,
  onLogout,
  onOpenExternal,
  onSaveBackup,
}: {
  active: 'workflow' | 'ai' | 'reports' | 'cleaning';
  workbook: SpreadsheetWorkbook | null;
  prompt: string;
  onPromptChange: (value: string) => void;
  onAsk: () => void;
  onSuggestion: (suggestion: string) => void;
  selectedSuggestion: string;
  onOpenReports: () => void;
  onOpenSettings: () => void;
  onLogout: () => void | Promise<void>;
  onOpenExternal: () => void | Promise<void>;
  onSaveBackup: () => void | Promise<void>;
}) {
  const suggestions = [
    'Clean this worksheet',
    'Remove duplicate customers',
    'Calculate total sales',
    'Explain this formula',
    'Find missing values',
    'Create a summary report',
    'Generate a chart',
    'Repeat this process across all sheets',
  ];

  return (
    <aside className="flex min-h-0 flex-col border-l border-[#DDE5E2] bg-white">
      <div className="border-b border-[#DDE5E2] p-4">
        <div className="text-xs uppercase tracking-[0.3em] text-[#889397]">Assistant</div>
        <div className="mt-1 text-lg font-semibold">Xelora AI</div>
      </div>

      <div className="min-h-0 flex-1 overflow-auto p-4">
        <div className="rounded-2xl border border-[#DDE5E2] bg-[#F7F9F8] p-4">
          <div className="mb-2 text-sm font-semibold">Suggested prompts</div>
          <div className="space-y-2">
            {suggestions.map((suggestion) => (
              <button
                key={suggestion}
                className={`w-full rounded-xl border px-3 py-2 text-left text-sm ${
                  selectedSuggestion === suggestion ? 'border-[#00684A] bg-[#E3FCF0]' : 'border-[#DDE5E2] bg-white'
                }`}
                onClick={() => onSuggestion(suggestion)}
              >
                {suggestion}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-4 rounded-2xl border border-[#DDE5E2] bg-white p-4">
          <div className="mb-2 text-sm font-semibold">Ask Xelora</div>
          <textarea
            value={prompt}
            onChange={(event) => onPromptChange(event.target.value)}
            className="min-h-[120px] w-full rounded-xl border border-[#DDE5E2] p-3 text-sm outline-none focus:border-[#00684A]"
            placeholder="Describe what you want to do..."
          />
          <button className="mt-3 w-full rounded-xl bg-[#001E2B] px-4 py-2.5 text-sm font-medium text-white" onClick={onAsk}>Ask Xelora</button>
        </div>

        <div className="mt-4 rounded-2xl border border-[#DDE5E2] bg-[#F7F9F8] p-4 text-sm text-[#5C6C75]">
          <div className="mb-2 font-semibold text-[#001E2B]">Context</div>
          <div>Selected cell</div>
          <div>Selected range</div>
          <div>Current worksheet</div>
          <div>Entire workbook</div>
          <div className="mt-3">Active workbook: {workbook?.fileName ?? 'No workbook open'}</div>
        </div>

        <div className="mt-4 rounded-2xl border border-[#DDE5E2] bg-white p-4">
          <div className="mb-2 text-sm font-semibold">App actions</div>
          <div className="grid gap-2">
            <button className="rounded-xl border border-[#DDE5E2] px-3 py-2 text-left text-sm" onClick={onOpenReports}>Reports</button>
            <button className="rounded-xl border border-[#DDE5E2] px-3 py-2 text-left text-sm" onClick={onOpenSettings}>Settings</button>
            <button className="rounded-xl border border-[#DDE5E2] px-3 py-2 text-left text-sm" onClick={onSaveBackup}>Create backup</button>
            <button className="rounded-xl border border-[#DDE5E2] px-3 py-2 text-left text-sm" onClick={onOpenExternal}>Open website</button>
            <button className="rounded-xl border border-[#DDE5E2] px-3 py-2 text-left text-sm text-[#B42318]" onClick={onLogout}>Sign out</button>
          </div>
        </div>
      </div>
    </aside>
  );
}

function FooterBar({
  workbook,
  selectedCell,
  statusMessage,
  version,
  dirty,
  offline,
}: {
  workbook: SpreadsheetWorkbook | null;
  selectedCell: string;
  statusMessage: string;
  version: string;
  dirty: boolean;
  offline: boolean;
}) {
  const sheet = workbook ? getActiveSheet(workbook) : null;
  const selected = sheet?.cells[selectedCell];
  return (
    <div className="flex items-center justify-between border-t border-[#DDE5E2] bg-white px-4 py-2 text-xs text-[#5C6C75]">
      <div className="flex items-center gap-4">
        <span>{selectedCell}</span>
        <span>{selected?.formula ? `=${selected.formula}` : selected?.value ?? 'Ready'}</span>
        <span>{dirty ? 'Unsaved changes' : 'Saved'}</span>
      </div>
      <div className="flex items-center gap-4">
        <span>{statusMessage}</span>
        {offline ? <span className="rounded-full bg-[#FFF4D6] px-3 py-1 text-[#7A4B00]">Offline</span> : null}
        <span>v{version}</span>
      </div>
    </div>
  );
}

export default App;
