const { contextBridge, ipcRenderer } = require('electron');

// Expose specific IPC functions to the renderer process for security
contextBridge.exposeInMainWorld('electronAPI', {
  // Function to request the list of rentals from the main process
  getRentals: () => ipcRenderer.invoke('get-rentals'),
  // Function to start the requestor process
  startRequestor: (environment) => ipcRenderer.invoke('start-requestor', environment),
  // Function to stop the requestor process
  stopRequestor: () => ipcRenderer.invoke('stop-requestor'),
  // Function to create a VM
  createVm: (vmDetails) => ipcRenderer.invoke('create-vm', vmDetails), // vmDetails = { name, providerId, cpu, memory, storage }
  // Function to destroy a VM
  destroyVm: (vmName) => ipcRenderer.invoke('destroy-vm', vmName),
  // Function to get available providers
  getProviders: (filters) => ipcRenderer.invoke('get-providers', filters) // filters = { cpu, memory, storage, country } (optional)
});

console.log('Preload script loaded, exposing: getRentals, startRequestor, stopRequestor, createVm, destroyVm');

// const { contextBridge, ipcRenderer } = require('electron');

// Example of exposing a function to the renderer process:
// contextBridge.exposeInMainWorld('electronAPI', {
//   loadPreferences: () => ipcRenderer.invoke('load-prefs')
// });
