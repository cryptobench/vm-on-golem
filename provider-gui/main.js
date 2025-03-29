const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

let mainWindow;
let providerProcess = null; // To hold the spawned provider process

function createWindow () {
  mainWindow = new BrowserWindow({ // Assign to global mainWindow
    width: 800,
    height: 600,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true, // Recommended for security
      nodeIntegration: false // Recommended for security
    }
  });

  mainWindow.loadFile('index.html');

  // Optional: Open DevTools for debugging
  // mainWindow.webContents.openDevTools();

  mainWindow.on('closed', () => {
    mainWindow = null; // Dereference window object
    // Ensure provider process is killed if window is closed
    if (providerProcess) {
      console.log('Window closed, stopping provider process...');
      providerProcess.kill();
      providerProcess = null;
    }
  });
}

function sendStatusUpdate(status) {
  if (mainWindow && mainWindow.webContents) {
    // Check if webContents is not destroyed before sending
    if (!mainWindow.webContents.isDestroyed()) {
        mainWindow.webContents.send('provider-status-update', status);
    } else {
        console.log("WebContents destroyed, cannot send status update.");
    }
  }
}

ipcMain.on('start-provider', () => {
  if (providerProcess) {
    console.log('Provider process already running.');
    sendStatusUpdate({ type: 'status', message: 'Provider already running.' });
    return;
  }

  console.log('Starting provider process...');
  sendStatusUpdate({ type: 'status', message: 'Starting provider...' });

  const providerDir = path.resolve(__dirname, '../provider-server'); // Path to provider-server directory

  try {
    // Spawn poetry run golem-provider in the provider-server directory
    // Set GOLEM_PROVIDER_DEBUG=true to disable port checking
    // Use shell: true for better cross-platform compatibility with commands like poetry
    providerProcess = spawn('poetry', ['run', 'golem-provider'], {
      cwd: providerDir,
      env: { ...process.env, GOLEM_PROVIDER_DEBUG: 'true' },
      shell: true // Use shell to handle potential path issues with poetry/commands
    });

    providerProcess.stdout.on('data', (data) => {
      const logMessage = data.toString();
      console.log(`Provider stdout: ${logMessage}`);
      sendStatusUpdate({ type: 'log', message: logMessage });
      // Optionally check for specific messages indicating readiness
      if (logMessage.includes("Starting provider server on")) {
         sendStatusUpdate({ type: 'status', message: 'Provider running.' });
      }
    });

    providerProcess.stderr.on('data', (data) => {
      const errorMessage = data.toString();
      console.error(`Provider stderr: ${errorMessage}`);
      // Send stderr as 'log' type for display, but also log as error in main process
      sendStatusUpdate({ type: 'log', message: `[ERROR] ${errorMessage}` });
    });

    providerProcess.on('close', (code) => {
      console.log(`Provider process exited with code ${code}`);
      const wasRunning = providerProcess !== null; // Check if we thought it was running
      providerProcess = null; // Clear the process reference immediately

      if (wasRunning) { // Only send update if we weren't already stopped
          let finalStatusMessage;
          if (code === 0 || code === null) { // Treat null exit code (often from SIGTERM/kill) as clean stop
              finalStatusMessage = 'Provider stopped.';
              sendStatusUpdate({ type: 'status', message: finalStatusMessage });
          } else {
              // Non-zero exit code means it crashed or exited with an error
              finalStatusMessage = `Provider stopped unexpectedly (exit code: ${code}). Check logs.`;
              // Send as 'error' type so renderer highlights it and adds the detailed message to logs
              sendStatusUpdate({ type: 'error', message: finalStatusMessage });
          }
          console.log(`Final status sent: ${finalStatusMessage}`);
      } else {
          console.log("Process already marked as stopped, ignoring close event.");
      }
    });

    providerProcess.on('error', (err) => {
      console.error('Failed to start provider process:', err);
      sendStatusUpdate({ type: 'error', message: `Failed to start provider: ${err.message}` });
      providerProcess = null;
    });

  } catch (error) {
      console.error('Error spawning provider process:', error);
      sendStatusUpdate({ type: 'error', message: `Error spawning provider: ${error.message}` });
      providerProcess = null;
  }
});

ipcMain.on('stop-provider', () => {
  if (providerProcess) {
    console.log('Stopping provider process...');
    sendStatusUpdate({ type: 'status', message: 'Stopping provider...' });
    providerProcess.kill('SIGTERM'); // Send SIGTERM for graceful shutdown
    // Status update will be sent via the 'close' event handler
  } else {
    console.log('Provider process not running.');
    sendStatusUpdate({ type: 'status', message: 'Provider already stopped.' });
  }
});


app.whenReady().then(() => {
  createWindow();

  app.on('activate', function () {
    // On macOS it's common to re-create a window in the app when the
    // dock icon is clicked and there are no other windows open.
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', function () {
  // Quit when all windows are closed, except on macOS. There, it's common
  // for applications and their menu bar to stay active until the user quits
  // explicitly with Cmd + Q.
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// Ensure provider process is killed on app quit
app.on('will-quit', () => {
  if (providerProcess) {
    console.log('App quitting, stopping provider process...');
    providerProcess.kill('SIGTERM');
  }
});