const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('xeloraDesktop', {
  platform: process.platform,
  version: '1.4.0',
  reload: () => ipcRenderer.send('reload'),
  isDesktopApp: true,
  setFloatingMode: (enabled) => ipcRenderer.invoke('floating:set', enabled),
  getFloatingMode: () => ipcRenderer.invoke('floating:get'),
  onFloatingModeChange: (callback) => {
    const handler = (_event, enabled) => callback(enabled);
    ipcRenderer.on('floating:changed', handler);
    return () => ipcRenderer.removeListener('floating:changed', handler);
  },
  agent: {
    getStatus: () => ipcRenderer.invoke('agent:status'),
    start: () => ipcRenderer.invoke('agent:start'),
    pair: (details) => ipcRenderer.invoke('agent:pair', details),
    unpair: () => ipcRenderer.invoke('agent:unpair'),
    onChange: (callback) => {
      const handler = (_event, status) => callback(status);
      ipcRenderer.on('agent:changed', handler);
      return () => ipcRenderer.removeListener('agent:changed', handler);
    },
  },
});
