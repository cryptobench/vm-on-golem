const { contextBridge, ipcRenderer } = require('electron');

// Expose specific IPC functions to the renderer process for security
contextBridge.exposeInMainWorld('electronAPI', {
  // Function to request the list of rentals from the main process
  getRentals: () => ipcRenderer.invoke('get-rentals')
  // Add other IPC functions here later (e.g., createRental, manageRental)
});

console.log('Preload script loaded.');

// const { contextBridge, ipcRenderer } = require('electron');

// Example of exposing a function to the renderer process:
// contextBridge.exposeInMainWorld('electronAPI', {
//   loadPreferences: () => ipcRenderer.invoke('load-prefs')
// });
