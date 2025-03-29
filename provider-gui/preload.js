const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('electronAPI', {
  // Example: Expose a function to send messages from renderer to main
  // sendMessage: (channel, data) => ipcRenderer.send(channel, data),

  // Example: Expose a function to receive messages from main to renderer
  // onMessage: (channel, func) => {
  //   // Deliberately strip event as it includes `sender`
  //   ipcRenderer.on(channel, (event, ...args) => func(...args));
  // }
});

console.log('Preload script loaded.');