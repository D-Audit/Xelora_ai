const { app, BrowserWindow, shell, Menu, ipcMain, screen } = require('electron');
const path = require('path');

const WEB_APP_URL = process.env.XELORA_WEB_URL || 'http://localhost:3000/dashboard';

let mainWindow;
let floatingModeEnabled = false;
let windowBeforeFloating = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1100,
    minHeight: 700,
    title: 'Xelora',
    backgroundColor: '#001E2B',
    icon: path.join(__dirname, 'assets', 'icon.ico'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      spellcheck: false,
    },
    titleBarStyle: 'hidden',
    titleBarOverlay: {
      color: '#001E2B',
      symbolColor: '#ffffff',
      height: 36,
    },
    show: false,
  });

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  mainWindow.loadURL(WEB_APP_URL).catch(() => {
    mainWindow.loadFile(path.join(__dirname, 'assets', 'offline.html'));
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  Menu.setApplicationMenu(null);
}

function setFloatingMode(enabled) {
  floatingModeEnabled = Boolean(enabled);
  if (!mainWindow || mainWindow.isDestroyed()) return floatingModeEnabled;

  if (floatingModeEnabled) {
    if (!windowBeforeFloating) {
      windowBeforeFloating = {
      bounds: mainWindow.getBounds(),
      wasMaximized: mainWindow.isMaximized(),
      minimumSize: mainWindow.getMinimumSize(),
      };
    }

    if (mainWindow.isMaximized()) mainWindow.unmaximize();
    const display = screen.getDisplayMatching(windowBeforeFloating.bounds);
    const { x, y, width: workWidth, height: workHeight } = display.workArea;
    mainWindow.setMinimumSize(420, 520);
    const width = Math.min(520, workWidth - 48);
    const height = Math.min(700, workHeight - 48);
    mainWindow.setBounds({
      x: x + workWidth - width - 24,
      y: y + workHeight - height - 24,
      width,
      height,
    });
  } else if (windowBeforeFloating) {
    mainWindow.setMinimumSize(...windowBeforeFloating.minimumSize);
    if (windowBeforeFloating.wasMaximized) {
      mainWindow.maximize();
    } else {
      mainWindow.setBounds(windowBeforeFloating.bounds);
    }
    windowBeforeFloating = null;
  }

  mainWindow.setAlwaysOnTop(floatingModeEnabled, floatingModeEnabled ? 'screen-saver' : 'normal');
  mainWindow.setVisibleOnAllWorkspaces(floatingModeEnabled, { visibleOnFullScreen: floatingModeEnabled });
  mainWindow.webContents.send('floating:changed', floatingModeEnabled);
  return floatingModeEnabled;
}

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

ipcMain.on('reload', () => {
  if (mainWindow) mainWindow.loadURL(WEB_APP_URL);
});

ipcMain.handle('floating:set', (_event, enabled) => setFloatingMode(enabled));
ipcMain.handle('floating:get', () => floatingModeEnabled);
