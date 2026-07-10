import { app, BrowserWindow, Notification } from 'electron';
import { autoUpdater } from 'electron-updater';

interface AutoUpdateControllerOptions {
  feedUrl: string;
  enabled: boolean;
  getMainWindow: () => BrowserWindow | null;
}

let initialized = false;
let updateChecksEnabled = false;
let updateCheckTimer: NodeJS.Timeout | null = null;
let getWindow: () => BrowserWindow | null = () => null;

function showUpdateNotification(title: string, body: string): void {
  try {
    new Notification({ title, body, silent: false }).show();
  } catch {
    // Notification setup is best-effort only.
  }
}

function clearUpdateTimer(): void {
  if (updateCheckTimer) {
    clearInterval(updateCheckTimer);
    updateCheckTimer = null;
  }
}

function schedulePeriodicChecks(): void {
  clearUpdateTimer();

  if (!app.isPackaged || !updateChecksEnabled) {
    return;
  }

  updateCheckTimer = setInterval(() => {
    void checkForUpdates('interval');
  }, 6 * 60 * 60 * 1000);
  updateCheckTimer.unref?.();
}

function configureUpdaterListeners(): void {
  autoUpdater.on('checking-for-update', () => {
    const window = getWindow();
    window?.webContents.send('app:update-status', { state: 'checking' });
  });

  autoUpdater.on('update-available', (info) => {
    const window = getWindow();
    window?.webContents.send('app:update-status', { state: 'available', version: info.version });
  });

  autoUpdater.on('update-not-available', (info) => {
    const window = getWindow();
    window?.webContents.send('app:update-status', { state: 'current', version: info.version });
  });

  autoUpdater.on('download-progress', (progress) => {
    const window = getWindow();
    window?.webContents.send('app:update-status', {
      state: 'downloading',
      percent: progress.percent,
      transferred: progress.transferred,
      total: progress.total,
    });
  });

  autoUpdater.on('update-downloaded', (info) => {
    const window = getWindow();
    window?.webContents.send('app:update-status', { state: 'downloaded', version: info.version });
    showUpdateNotification(
      'Xelora update ready',
      `Version ${info.version} has been downloaded and will install when you quit Xelora.`,
    );
  });

  autoUpdater.on('error', (error) => {
    const message = error instanceof Error ? error.message : String(error);
    const window = getWindow();
    window?.webContents.send('app:update-status', { state: 'error', message });
  });
}

export function initializeAutoUpdater(options: AutoUpdateControllerOptions): void {
  getWindow = options.getMainWindow;
  updateChecksEnabled = options.enabled;

  if (!options.feedUrl) {
    return;
  }

  autoUpdater.autoDownload = true;
  autoUpdater.autoInstallOnAppQuit = true;
  autoUpdater.allowPrerelease = false;
  const feedUrl = `${options.feedUrl.replace(/\/+$/, '')}/`;
  autoUpdater.setFeedURL({
    provider: 'generic',
    url: feedUrl,
  });

  if (!initialized) {
    configureUpdaterListeners();
    initialized = true;
  }

  schedulePeriodicChecks();

  if (app.isPackaged && updateChecksEnabled) {
    void checkForUpdates('startup');
  }
}

export function setAutoUpdateChecksEnabled(enabled: boolean): void {
  updateChecksEnabled = enabled;
  schedulePeriodicChecks();

  if (app.isPackaged && updateChecksEnabled) {
    void checkForUpdates('enabled');
  }
}

export async function checkForUpdates(_reason: string = 'manual'): Promise<void> {
  if (!app.isPackaged || !updateChecksEnabled) {
    return;
  }

  try {
    await autoUpdater.checkForUpdates();
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    const window = getWindow();
    window?.webContents.send('app:update-status', { state: 'error', message });
  }
}
