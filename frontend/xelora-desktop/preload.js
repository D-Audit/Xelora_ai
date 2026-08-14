const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('xeloraDesktop', {
  platform: process.platform,
  version: '1.3.0',
  reload: () => ipcRenderer.send('reload'),
  isDesktopApp: true,
  setFloatingMode: (enabled) => ipcRenderer.invoke('floating:set', enabled),
  getFloatingMode: () => ipcRenderer.invoke('floating:get'),
  onFloatingModeChange: (callback) => {
    const handler = (_event, enabled) => callback(enabled);
    ipcRenderer.on('floating:changed', handler);
    return () => ipcRenderer.removeListener('floating:changed', handler);
  },
});
