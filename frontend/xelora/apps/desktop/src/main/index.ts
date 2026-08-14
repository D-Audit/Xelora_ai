import { app, BrowserWindow, dialog, ipcMain, Notification, nativeImage, shell, session } from 'electron';
import { join } from 'node:path';
import fs from 'node:fs/promises';
import path from 'node:path';
import { createAppMenu } from './menu';
import { createBackupCopy, fileExists, fileSize, readSpreadsheet, saveSpreadsheet } from './services/file-service';
import { JsonStore, createUserDataPath } from './services/store';
import {
  getDemoCredentials,
  createSession,
} from './services/auth';
import {
  initializeAutoUpdater,
  setAutoUpdateChecksEnabled,
} from './services/updater';
import type {
  AppInfo,
  BackupRequest,
  DesktopNotification,
  DesktopSettings,
  OpenWorkbookResult,
  SaveWorkbookRequest,
  SaveResult,
} from '../shared/types';

const store = new JsonStore('xelora-state.json');
const protocol = 'xelora';
let mainWindow: BrowserWindow | null = null;
let floatingModeEnabled = false;
let allowWindowClose = false;
let pendingCloseAfterSave = false;

function getUpdateFeedUrl(): string {
  return process.env.XELORA_UPDATE_FEED_URL?.trim()
    || (app.isPackaged
      ? 'https://updates.xelora.app/api/desktop/windows'
      : 'http://localhost:3000/api/desktop/windows');
}

function getIconPath(fileName: string): string {
  const basePath = app.isPackaged ? process.resourcesPath : join(app.getAppPath(), 'build');
  return join(basePath, fileName);
}

async function ensureAppDirs(): Promise<void> {
  await fs.mkdir(createUserDataPath(), { recursive: true });
}

function resolveDevUrl(): string | null {
  const devUrl = process.env.VITE_DEV_SERVER_URL;
  return devUrl ?? null;
}

function getAppInfo(): AppInfo {
  return {
    name: app.name,
    productName: app.getName(),
    version: app.getVersion(),
    executableName: 'Xelora',
    appId: 'app.xelora.desktop',
    userDataPath: app.getPath('userData'),
    releaseChannel: app.isPackaged ? 'stable' : 'beta',
    updateServerUrl: getUpdateFeedUrl(),
  };
}

function updateWindowTitle(workbookName?: string): void {
  if (!mainWindow) {
    return;
  }

  mainWindow.setTitle(workbookName ? `${workbookName} - Xelora` : 'Xelora');
}

async function openWorkbookByPath(filePath: string): Promise<OpenWorkbookResult> {
  const result = await readSpreadsheet(filePath);
  await store.update({
    recentFiles: [
      result.recentFile,
      ...store.getState().recentFiles.filter((item) => item.filePath !== result.recentFile.filePath),
    ].slice(0, store.getState().settings.files.recentFilesLimit),
  });
  return result;
}

async function promptForFile(allowCsv: boolean): Promise<string | null> {
  if (!mainWindow) {
    return null;
  }

  const response = await dialog.showOpenDialog(mainWindow, {
    title: allowCsv ? 'Open CSV File' : 'Open Spreadsheet',
    properties: ['openFile'],
    filters: allowCsv
      ? [{ name: 'Spreadsheet files', extensions: ['xlsx', 'csv'] }]
      : [{ name: 'Excel workbooks', extensions: ['xlsx'] }],
  });

  if (response.canceled || response.filePaths.length === 0) {
    return null;
  }

  return response.filePaths[0];
}

async function promptForSave(defaultPath?: string): Promise<string | null> {
  if (!mainWindow) {
    return null;
  }

  const response = await dialog.showSaveDialog(mainWindow, {
    title: 'Save Workbook',
    defaultPath,
    filters: [
      { name: 'Excel Workbook', extensions: ['xlsx'] },
      { name: 'CSV', extensions: ['csv'] },
    ],
  });

  if (response.canceled || !response.filePath) {
    return null;
  }

  return response.filePath;
}

async function saveWorkbookRequest(request: SaveWorkbookRequest, saveAs = false): Promise<SaveResult | null> {
  const filePath = saveAs || !request.filePath ? await promptForSave(request.filePath ?? request.workbook.fileName) : request.filePath;
  if (!filePath) {
    return null;
  }

  const result = await saveSpreadsheet(request.workbook, filePath);
  await store.update({
    recentFiles: [
      {
        filePath: result.filePath,
        fileName: result.fileName,
        fileType: path.extname(result.filePath).slice(1),
        sizeBytes: result.sizeBytes,
        lastOpenedAt: result.savedAt,
        exists: true,
      },
      ...store.getState().recentFiles.filter((item) => item.filePath !== result.filePath),
    ].slice(0, store.getState().settings.files.recentFilesLimit),
  });
  return result;
}

function setupSecureSession(): void {
  session.defaultSession.setPermissionRequestHandler((_webContents, permission, callback) => {
    const allowed = permission === 'notifications';
    callback(allowed);
  });

  session.defaultSession.setPermissionCheckHandler(() => false);
}

function createWindow(): BrowserWindow {
  const bounds = store.getState().windowBounds ?? { x: 40, y: 40, width: 1440, height: 900 };

  const window = new BrowserWindow({
    ...bounds,
    minWidth: 1100,
    minHeight: 700,
    backgroundColor: '#F7F9F8',
    title: 'Xelora',
    icon: getIconPath('icon.png'),
    webPreferences: {
      preload: join(app.getAppPath(), 'out/preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  window.on('resize', () => {
    if (!window.isMinimized() && !window.isMaximized()) {
      void store.setWindowBounds(window.getBounds());
    }
  });

  window.on('move', () => {
    if (!window.isMinimized() && !window.isMaximized()) {
      void store.setWindowBounds(window.getBounds());
    }
  });

  window.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('https://')) {
      void shell.openExternal(url);
    }
    return { action: 'deny' };
  });

  window.webContents.on('will-navigate', (event, url) => {
    const allowed = url.startsWith('https://') || url.startsWith('file://') || url.startsWith(`${protocol}:`);
    if (!allowed) {
      event.preventDefault();
    }
  });

  const devUrl = resolveDevUrl();
  if (devUrl) {
    void window.loadURL(devUrl);
    window.webContents.openDevTools({ mode: 'detach' });
  } else {
    void window.loadFile(join(app.getAppPath(), 'out/renderer/index.html'));
  }

  window.on('close', (event) => {
    if (allowWindowClose) {
      return;
    }

    if (!store.getState().isDirty) {
      return;
    }

    event.preventDefault();
    const choice = dialog.showMessageBoxSync(window, {
      type: 'warning',
      buttons: ['Save', "Don\'t Save", 'Cancel'],
      defaultId: 0,
      cancelId: 2,
      title: 'Unsaved Changes',
      message: 'You have unsaved changes. Save before closing?',
    });

    if (choice === 2) {
      return;
    }

    if (choice === 1) {
      allowWindowClose = true;
      window.destroy();
      return;
    }

    pendingCloseAfterSave = true;
    window.webContents.send('desktop-close-save');
  });

  return window;
}

function setFloatingMode(enabled: boolean): boolean {
  floatingModeEnabled = enabled;
  if (!mainWindow || mainWindow.isDestroyed()) {
    return floatingModeEnabled;
  }

  mainWindow.setAlwaysOnTop(enabled, enabled ? 'screen-saver' : 'normal');
  mainWindow.setVisibleOnAllWorkspaces(enabled, { visibleOnFullScreen: enabled });
  mainWindow.webContents.send('window:floating-mode-changed', floatingModeEnabled);
  return floatingModeEnabled;
}

function registerIpc(): void {
  ipcMain.handle('app:get-info', async () => getAppInfo());
  ipcMain.handle('app:get-demo-credentials', async () => getDemoCredentials());

  ipcMain.handle('auth:get-session', async () => store.getState().session);
  ipcMain.handle('auth:login', async (_event, request) => {
    const sessionState = createSession(request);
    await store.update({ session: sessionState });
    return {
      user: sessionState.user,
      token: sessionState.token,
      rememberMe: sessionState.rememberMe,
    };
  });
  ipcMain.handle('auth:logout', async () => {
    await store.update({ session: null });
  });

  ipcMain.handle('settings:get', async () => store.getState().settings);
  ipcMain.handle('settings:update', async (_event, patch: Partial<DesktopSettings>) => {
    await store.update({ settings: patch });
    const settings = store.getState().settings;
    setAutoUpdateChecksEnabled(settings.application.checkForUpdates);
    return settings;
  });

  ipcMain.handle('files:get-recent', async () => {
    const recent = await Promise.all(
      store.getState().recentFiles.map(async (item) => ({
        ...item,
        exists: await fileExists(item.filePath),
        sizeBytes: (await fileExists(item.filePath)) ? await fileSize(item.filePath) : item.sizeBytes,
      })),
    );
    return recent;
  });

  ipcMain.handle('files:remove-recent', async (_event, filePath: string) => {
    await store.update({
      recentFiles: store.getState().recentFiles.filter((item) => item.filePath !== filePath),
    });
  });

  ipcMain.handle('files:open-workbook', async () => {
    const filePath = await promptForFile(false);
    if (!filePath) {
      return null;
    }
    return openWorkbookByPath(filePath);
  });

  ipcMain.handle('files:open-csv', async () => {
    const filePath = await promptForFile(true);
    if (!filePath) {
      return null;
    }
    return openWorkbookByPath(filePath);
  });

  ipcMain.handle('files:open-recent', async (_event, filePath: string) => {
    if (!(await fileExists(filePath))) {
      throw new Error('This file is no longer available at its previous location.');
    }
    return openWorkbookByPath(filePath);
  });

  ipcMain.handle('files:save-workbook', async (_event, request: SaveWorkbookRequest) => saveWorkbookRequest(request, false));
  ipcMain.handle('files:save-workbook-as', async (_event, request: SaveWorkbookRequest) => saveWorkbookRequest(request, true));
  ipcMain.handle('files:create-backup', async (_event, request: BackupRequest) => createBackupCopy(request.sourceFilePath, request.workbookName));

  ipcMain.handle('notifications:show', async (_event, notification: DesktopNotification) => {
    const icon = nativeImage.createFromPath(getIconPath('icon.png'));
    const instance = new Notification({
      title: notification.title,
      body: notification.body,
      silent: notification.silent ?? false,
      icon,
    });
    instance.show();
  });

  ipcMain.handle('external:open', async (_event, url: string) => {
    if (!url.startsWith('https://')) {
      throw new Error('Only secure https:// URLs can be opened from Xelora.');
    }

    await shell.openExternal(url);
  });

  ipcMain.handle('window:set-dirty', async (_event, isDirty: boolean) => {
    await store.setDirty(isDirty);
  });

  ipcMain.handle('window:confirm-close-after-save', async () => {
    if (!pendingCloseAfterSave || !mainWindow) {
      return;
    }

    allowWindowClose = true;
    pendingCloseAfterSave = false;
    mainWindow.close();
  });

  ipcMain.handle('window:set-floating-mode', async (_event, enabled: boolean) => setFloatingMode(Boolean(enabled)));
  ipcMain.handle('window:get-floating-mode', async () => floatingModeEnabled);
}

function registerProtocolHandlers(): void {
  app.setAsDefaultProtocolClient(protocol);

  app.on('open-url', (_event, url) => {
    if (url.startsWith(`${protocol}://auth/callback`)) {
      mainWindow?.webContents.send('protocol-callback', url);
      mainWindow?.focus();
    }
  });

  app.on('second-instance', (_event, argv) => {
    const urlArg = argv.find((value) => value.startsWith(`${protocol}://`));
    if (urlArg) {
      mainWindow?.webContents.send('protocol-callback', urlArg);
    }

    if (mainWindow) {
      if (mainWindow.isMinimized()) {
        mainWindow.restore();
      }
      mainWindow.focus();
    }
  });
}

async function bootstrap(): Promise<void> {
  await ensureAppDirs();
  await store.init();
  if (!store.getState().session) {
    const credentials = getDemoCredentials();
    await store.update({
      session: createSession({
        email: credentials.email,
        password: credentials.password,
        rememberMe: true,
      }),
    });
  }
  setupSecureSession();
  registerIpc();
  registerProtocolHandlers();

  app.setAppUserModelId('app.xelora.desktop');
  mainWindow = createWindow();
  createAppMenu(mainWindow);
  updateWindowTitle();
  void store.setDirty(false);

  initializeAutoUpdater({
    feedUrl: getUpdateFeedUrl(),
    enabled: store.getState().settings.application.checkForUpdates,
    getMainWindow: () => mainWindow,
  });

  mainWindow.webContents.once('did-finish-load', () => {
    mainWindow?.webContents.send('app:ready', {
      info: getAppInfo(),
      session: store.getState().session,
    });
  });

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      mainWindow = createWindow();
      createAppMenu(mainWindow);
    }
  });
}

app.whenReady().then(() => {
  void bootstrap();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', () => {
  if (mainWindow) {
    void store.setWindowBounds(mainWindow.getBounds());
  }
});
