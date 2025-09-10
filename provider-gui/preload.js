const { contextBridge, ipcRenderer } = require('electron');

// Expose minimal config and IPC hooks
contextBridge.exposeInMainWorld('config', {
  apiBaseUrl: process.env.PROVIDER_API_URL || 'http://127.0.0.1:7466/api/v1'
});

contextBridge.exposeInMainWorld('electronAPI', {
  onProviderStatusUpdate: (callback) => ipcRenderer.on('provider-status-update', (_event, status) => callback(status)),
  requestShutdown: () => ipcRenderer.send('shutdown-provider'),
  providerStart: () => ipcRenderer.invoke('provider-start'),
  providerStop: () => ipcRenderer.invoke('provider-stop'),
  checkMultipass: () => ipcRenderer.invoke('multipass-check'),
  openExternal: (url) => ipcRenderer.invoke('open-external', url)
});

console.log('Preload script loaded.');
