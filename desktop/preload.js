const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('xeloraDesktop', {
  platform: process.platform,
  // Passed in by main.js; a sandboxed preload cannot read package.json.
  version: (process.argv.find((arg) => arg.startsWith('--xelora-version=')) || '').split('=')[1] || '',
  reload: () => ipcRenderer.send('reload'),
  isDesktopApp: true,
  setFloatingMode: (enabled) => ipcRenderer.invoke('floating:set', enabled),
  getFloatingMode: () => ipcRenderer.invoke('floating:get'),
  signInWithBrowser: (provider) => ipcRenderer.invoke('auth:browser-sign-in', provider),
  setTheme: (theme) => ipcRenderer.invoke('theme:set', theme),
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
