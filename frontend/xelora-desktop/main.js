const { app, BrowserWindow, shell, Menu, ipcMain } = require('electron');
const path = require('path');

// The web app URL — points at your real Xelora dashboard, the exact
// same fully-integrated app (auth, billing, files, workflows, the
// real AI Agent page) that runs in a browser tab. This window is just
// a native wrapper around it - there is no separate desktop-only UI
// or logic here.
//
// Defaults to your local dev server. Override with the XELORA_WEB_URL
// environment variable when pointing at a deployed production URL,
// e.g.:
//   XELORA_WEB_URL=https://app.yourdomain.com/dashboard npm start
const WEB_APP_URL = process.env.XELORA_WEB_URL || 'http://localhost:3000/dashboard';

let mainWindow;

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

  // Show once ready — avoids white flash
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  mainWindow.loadURL(WEB_APP_URL).catch(() => {
    // If the dev server isn't running, show a helpful offline page
    mainWindow.loadFile(path.join(__dirname, 'assets', 'offline.html'));
  });

  // Open external links in the system browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  // Remove default menu bar
  Menu.setApplicationMenu(null);
}

// App lifecycle
app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

// Handle reload from renderer
ipcMain.on('reload', () => {
  if (mainWindow) mainWindow.loadURL(WEB_APP_URL);
});
