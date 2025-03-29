const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('electronAPI', {
  startProvider: () => ipcRenderer.send('start-provider'),
  stopProvider: () => ipcRenderer.send('stop-provider'),
  onProviderStatusUpdate: (callback) => ipcRenderer.on('provider-status-update', (_event, status) => callback(status))
});

console.log('Preload script loaded.');