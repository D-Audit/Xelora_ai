const { app, BrowserWindow, shell, Menu, ipcMain, screen } = require('electron');
const crypto = require('crypto');
const path = require('path');
const { autoUpdater } = require('electron-updater');
const localAgent = require('./agent');

const { xelora } = require('./package.json');

// XELORA_WEB_URL overrides; installed builds use package.json "xelora.webUrl",
// `npm start` uses the local Next.js dev server.
const WEB_APP_URL = process.env.XELORA_WEB_URL
  || (app.isPackaged ? xelora.webUrl : 'http://localhost:3000/dashboard');

let mainWindow;
let floatingModeEnabled = false;

// ── Sign in with Google/Microsoft in the system browser ───────────────────
// Google blocks OAuth inside embedded app windows. The app opens the user's
// browser with a one-time secret; the website finishes sign-in and sends a
// short-lived code back through xelora://auth. The code is exchanged only
// together with that secret, which never leaves this process.
const PROTOCOL = 'xelora';
const HANDOFF_TTL_MS = 10 * 60 * 1000;
let pendingHandoff = null; // { secret, createdAt }

if (!app.requestSingleInstanceLock()) {
  app.quit();
}
if (process.defaultApp) {
  app.setAsDefaultProtocolClient(PROTOCOL, process.execPath, [path.resolve(process.argv[1] || '.')]);
} else {
  app.setAsDefaultProtocolClient(PROTOCOL);
}

function startBrowserSignIn(provider) {
  if (!['google', 'microsoft'].includes(provider)) throw new Error('Unknown sign-in provider.');
  const secret = crypto.randomBytes(32).toString('base64url');
  pendingHandoff = { secret, createdAt: Date.now() };
  const origin = new URL(WEB_APP_URL).origin;
  shell.openExternal(`${origin}/api/auth/${provider}/start?desktop=${encodeURIComponent(secret)}`);
  return true;
}

function handleDeepLink(url) {
  let parsed;
  try { parsed = new URL(url); } catch { return; }
  if (parsed.protocol !== `${PROTOCOL}:` || parsed.hostname !== 'auth') return;
  const code = parsed.searchParams.get('code');
  const handoff = pendingHandoff;
  pendingHandoff = null;
  if (!code || !handoff || Date.now() - handoff.createdAt > HANDOFF_TTL_MS || !mainWindow || mainWindow.isDestroyed()) return;
  const origin = new URL(WEB_APP_URL).origin;
  const complete = `${origin}/api/auth/desktop/complete?code=${encodeURIComponent(code)}&secret=${encodeURIComponent(handoff.secret)}`;
  if (mainWindow.isMinimized()) mainWindow.restore();
  mainWindow.show();
  mainWindow.focus();
  mainWindow.loadURL(complete);
}

app.on('second-instance', (_event, argv) => {
  const link = argv.find((arg) => arg.startsWith(`${PROTOCOL}://`));
  if (link) handleDeepLink(link);
  else if (mainWindow) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.focus();
  }
});
app.on('open-url', (event, url) => { event.preventDefault(); handleDeepLink(url); });
let windowBeforeFloating = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1100,
    minHeight: 700,
    title: 'Xelora',
    backgroundColor: '#FAFAFA',
    icon: path.join(__dirname, 'assets', process.platform === 'win32' ? 'icon.ico' : 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      additionalArguments: [`--xelora-version=${app.getVersion()}`],
      nodeIntegration: false,
      contextIsolation: true,
      spellcheck: false,
    },
    titleBarStyle: 'hidden',
    titleBarOverlay: {
      color: '#FAFAFA',
      symbolColor: '#18181B',
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
  localAgent.init((status) => {
    if (mainWindow && !mainWindow.isDestroyed()) mainWindow.webContents.send('agent:changed', status);
  });

  if (app.isPackaged) {
    autoUpdater.checkForUpdatesAndNotify();
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('before-quit', () => localAgent.stop());

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

ipcMain.on('reload', () => {
  if (mainWindow) mainWindow.loadURL(WEB_APP_URL);
});

ipcMain.handle('floating:set', (_event, enabled) => setFloatingMode(enabled));
ipcMain.handle('auth:browser-sign-in', (event, provider) => {
  if (!fromWebApp(event)) throw new Error('Not allowed.');
  return startBrowserSignIn(provider);
});
ipcMain.handle('floating:get', () => floatingModeEnabled);

// Only the Xelora web app loaded in this window may pair or control the agent.
const WEB_APP_ORIGIN = new URL(WEB_APP_URL).origin;
function fromWebApp(event) {
  try {
    return new URL(event.senderFrame.url).origin === WEB_APP_ORIGIN;
  } catch {
    return false;
  }
}
function agentHandler(handler) {
  return (event, ...args) => {
    if (!fromWebApp(event)) throw new Error('Not allowed.');
    return handler(...args);
  };
}
ipcMain.handle('agent:status', agentHandler(() => localAgent.getStatus()));
ipcMain.handle('agent:start', agentHandler(() => localAgent.start()));
ipcMain.handle('agent:pair', agentHandler((details) => localAgent.pair(details)));
ipcMain.handle('agent:unpair', agentHandler(() => localAgent.unpair()));
