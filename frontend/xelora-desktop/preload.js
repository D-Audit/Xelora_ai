const { contextBridge, ipcRenderer } = require('electron');

// Expose a safe API to the renderer (the web app)
contextBridge.exposeInMainWorld('xeloraDesktop', {
  platform: process.platform,
  version: '1.3.0',
  reload: () => ipcRenderer.send('reload'),
  isDesktopApp: true,
});
