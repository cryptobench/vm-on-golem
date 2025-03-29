const { contextBridge, ipcRenderer } = require('electron');

// Expose specific IPC functions to the renderer process for security
contextBridge.exposeInMainWorld('electronAPI', {
  // Function to request the list of rentals from the main process
  getRentals: () => ipcRenderer.invoke('get-rentals'),
  // Function to start the requestor process
  startRequestor: (environment) => ipcRenderer.invoke('start-requestor', environment),
  // Function to stop the requestor process
  stopRequestor: () => ipcRenderer.invoke('stop-requestor')
});

console.log('Preload script loaded.');

// const { contextBridge, ipcRenderer } = require('electron');

// Example of exposing a function to the renderer process:
// contextBridge.exposeInMainWorld('electronAPI', {
//   loadPreferences: () => ipcRenderer.invoke('load-prefs')
// });
