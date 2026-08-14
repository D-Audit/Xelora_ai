import { contextBridge, ipcRenderer } from 'electron';
import type {
  AppInfo,
  BackupRequest,
  BackupResult,
  DesktopNotification,
  DesktopSettings,
  LoginRequest,
  LoginResult,
  OpenWorkbookResult,
  RecentFile,
  SaveResult,
  SaveWorkbookRequest,
  SessionState,
  XeloraDesktopAPI,
} from '../shared/types';

type MenuCallback = (action: string) => void;
type VoidCallback = () => void;
type ProtocolCallback = (url: string) => void;

const api: XeloraDesktopAPI = {
  openWorkbook: () => ipcRenderer.invoke('files:open-workbook') as Promise<OpenWorkbookResult | null>,
  openCsv: () => ipcRenderer.invoke('files:open-csv') as Promise<OpenWorkbookResult | null>,
  saveWorkbook: (request: SaveWorkbookRequest) => ipcRenderer.invoke('files:save-workbook', request) as Promise<SaveResult | null>,
  saveWorkbookAs: (request: SaveWorkbookRequest) => ipcRenderer.invoke('files:save-workbook-as', request) as Promise<SaveResult | null>,
  createBackup: (request: BackupRequest) => ipcRenderer.invoke('files:create-backup', request) as Promise<BackupResult>,
  getRecentFiles: () => ipcRenderer.invoke('files:get-recent') as Promise<RecentFile[]>,
  removeRecentFile: (filePath: string) => ipcRenderer.invoke('files:remove-recent', filePath),
  getSettings: () => ipcRenderer.invoke('settings:get') as Promise<DesktopSettings>,
  updateSettings: (settings: Partial<DesktopSettings>) => ipcRenderer.invoke('settings:update', settings) as Promise<DesktopSettings>,
  getAppInfo: () => ipcRenderer.invoke('app:get-info') as Promise<AppInfo>,
  showNotification: (notification: DesktopNotification) => ipcRenderer.invoke('notifications:show', notification),
  openExternalUrl: (url: string) => ipcRenderer.invoke('external:open', url),
  onMenuAction: (callback: MenuCallback) => {
    const handler = (_event: Electron.IpcRendererEvent, action: string) => callback(action);
    ipcRenderer.on('menu-action', handler);
    return () => {
      ipcRenderer.removeListener('menu-action', handler);
    };
  },
  onCloseSaveRequest: (callback: VoidCallback) => {
    const handler = () => callback();
    ipcRenderer.on('desktop-close-save', handler);
    return () => {
      ipcRenderer.removeListener('desktop-close-save', handler);
    };
  },
  onProtocolCallback: (callback: ProtocolCallback) => {
    const handler = (_event: Electron.IpcRendererEvent, url: string) => callback(url);
    ipcRenderer.on('protocol-callback', handler);
    return () => {
      ipcRenderer.removeListener('protocol-callback', handler);
    };
  },
  setUnsavedChanges: (isDirty: boolean) => ipcRenderer.invoke('window:set-dirty', isDirty),
  confirmCloseAfterSave: () => ipcRenderer.invoke('window:confirm-close-after-save'),
  login: (request: LoginRequest) => ipcRenderer.invoke('auth:login', request) as Promise<LoginResult>,
  getSession: () => ipcRenderer.invoke('auth:get-session') as Promise<SessionState | null>,
  logout: () => ipcRenderer.invoke('auth:logout'),
  openRecentFile: (filePath: string) => ipcRenderer.invoke('files:open-recent', filePath) as Promise<OpenWorkbookResult | null>,
  setFloatingMode: (enabled: boolean) => ipcRenderer.invoke('window:set-floating-mode', enabled) as Promise<boolean>,
  getFloatingMode: () => ipcRenderer.invoke('window:get-floating-mode') as Promise<boolean>,
  onFloatingModeChange: (callback: (enabled: boolean) => void) => {
    const handler = (_event: Electron.IpcRendererEvent, enabled: boolean) => callback(enabled);
    ipcRenderer.on('window:floating-mode-changed', handler);
    return () => ipcRenderer.removeListener('window:floating-mode-changed', handler);
  },
};

contextBridge.exposeInMainWorld('xelora', api);
