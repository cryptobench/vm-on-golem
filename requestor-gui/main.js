const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { execFile } = require('child_process');
const { spawn } = require('child_process');
const util = require('util');

// Promisify execFile for easier async/await usage
const execFilePromise = util.promisify(execFile);
let requestorProcess = null; // To hold the reference to the running requestor server process

function createWindow () {
  const mainWindow = new BrowserWindow({
    width: 800,
    height: 600,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true, // Recommended for security
      nodeIntegration: false // Recommended for security
    }
  });

  mainWindow.loadFile('index.html');

  // Open the DevTools (optional)
  // mainWindow.webContents.openDevTools();
}

app.whenReady().then(() => {
  // --- IPC Handler for get-rentals ---
  ipcMain.handle('get-rentals', async () => {
    console.log('Main process received get-rentals request.');
    // Adjust pythonPath if necessary, especially for packaged apps or different environments
    const pythonPath = 'python3'; // Or specify the full path to the python executable if needed
    // Path relative to the project root where main.js is located
    const scriptPath = path.join(app.getAppPath(), '../requestor-server/requestor/run.py');
    const args = ['vm', 'list'];
    // Set the working directory to the requestor-server so it can find its config/db
    const options = { cwd: path.join(app.getAppPath(), '../requestor-server') };

    console.log(`Executing: ${pythonPath} ${scriptPath} ${args.join(' ')} in ${options.cwd}`);

    try {
      const { stdout, stderr } = await execFilePromise(pythonPath, [scriptPath, ...args], options);

      if (stderr) {
        console.error('Error executing requestor CLI:', stderr);
        // Optionally return an error object or specific structure
        return { error: 'Failed to list rentals', details: stderr };
      }

      console.log('Requestor CLI output:\n', stdout);

      // --- Basic Parsing Logic (Needs Refinement) ---
      // This assumes a simple table output. Adjust based on actual output format.
      const lines = stdout.trim().split('\n');
      if (lines.length < 2) { // Expecting header + data rows
          console.log('No rental data found or unexpected format.');
          return [];
      }

      // Assuming header is the first line, find column indices (example)
      const header = lines[0].toLowerCase();
      const nameIndex = header.indexOf('name');
      const providerIndex = header.indexOf('provider'); // Or 'provider_id' etc.
      const statusIndex = header.indexOf('status');

      if (nameIndex === -1 || providerIndex === -1 || statusIndex === -1) {
          console.error('Could not parse header columns from CLI output:', header);
          return { error: 'Failed to parse rental list header' };
      }

      const rentals = lines.slice(1).map(line => {
          // Basic fixed-width parsing - VERY FRAGILE, replace with better parsing
          // if the output is structured (e.g., JSON) or use regex.
          const name = line.substring(nameIndex, providerIndex).trim();
          const provider = line.substring(providerIndex, statusIndex).trim();
          const status = line.substring(statusIndex).trim(); // Assumes status is last
          return { id: name, provider: provider, status: status }; // Use 'name' as 'id' for the UI
      }).filter(r => r.id); // Filter out empty lines or parsing errors

      console.log('Parsed rentals:', rentals);
      return rentals;
      // --- End Parsing Logic ---

    } catch (error) {
      console.error('Failed to execute or parse requestor CLI:', error);
      return { error: 'Failed to execute rental list command', details: error.message };
    }
// --- IPC Handler for start-requestor ---
  ipcMain.handle('start-requestor', async (event, environment) => {
    console.log(`Main process received start-requestor request for env: ${environment}`);
    if (requestorProcess) {
      console.log('Requestor process already running.');
      return { success: false, error: 'Requestor already running.' };
    }

    const pythonPath = 'python3'; // Adjust if needed
    const scriptDir = path.join(app.getAppPath(), '../requestor-server');
    const scriptPath = path.join(scriptDir, 'requestor/run.py');
    const args = ['server', 'start'];
    const env = { ...process.env, GOLEM_ENV: environment }; // Set environment variable

    console.log(`Starting requestor: ${pythonPath} ${scriptPath} ${args.join(' ')} in ${scriptDir} with GOLEM_ENV=${environment}`);

    try {
      requestorProcess = spawn(pythonPath, [scriptPath, ...args], {
        cwd: scriptDir,
        env: env,
        stdio: ['ignore', 'pipe', 'pipe'] // Ignore stdin, pipe stdout/stderr
      });

      requestorProcess.stdout.on('data', (data) => {
        console.log(`Requestor stdout: ${data}`);
        // Optionally, send status updates to renderer via mainWindow.webContents.send()
      });

      requestorProcess.stderr.on('data', (data) => {
        console.error(`Requestor stderr: ${data}`);
        // Optionally, send error updates to renderer
      });

      requestorProcess.on('close', (code) => {
        console.log(`Requestor process exited with code ${code}`);
        requestorProcess = null; // Clear the reference
        // Optionally, notify renderer that the process stopped unexpectedly
        // mainWindow.webContents.send('requestor-stopped');
      });

      requestorProcess.on('error', (err) => {
        console.error('Failed to start requestor process:', err);
        requestorProcess = null; // Clear the reference on spawn error
        // Don't return here, let the main try-catch handle it if spawn itself throws
      });

      // Give the process a moment to potentially fail on startup
      await new Promise(resolve => setTimeout(resolve, 500));

      if (requestorProcess && requestorProcess.exitCode === null && !requestorProcess.killed) {
         console.log('Requestor process spawned successfully (PID:', requestorProcess.pid, ')');
         return { success: true };
      } else {
         const exitCode = requestorProcess ? requestorProcess.exitCode : 'N/A';
         console.error(`Requestor process failed to start or exited quickly (Exit code: ${exitCode}). Check logs.`);
         requestorProcess = null; // Ensure it's cleared
         return { success: false, error: `Requestor failed to start (Exit code: ${exitCode}). Check console logs.` };
      }


    } catch (error) {
      console.error('Error spawning requestor process:', error);
      requestorProcess = null; // Ensure reference is cleared on error
      return { success: false, error: error.message };
    }
  });

  // --- IPC Handler for stop-requestor ---
  ipcMain.handle('stop-requestor', async () => {
    console.log('Main process received stop-requestor request.');
    if (!requestorProcess) {
      console.log('Requestor process is not running.');
      return { success: false, error: 'Requestor not running.' };
    }

    try {
      console.log(`Attempting to kill requestor process (PID: ${requestorProcess.pid})...`);
      const killed = requestorProcess.kill('SIGTERM'); // Send SIGTERM first
      if (killed) {
          console.log('Sent SIGTERM to requestor process.');
          // Wait a short period for graceful shutdown before potentially sending SIGKILL
          await new Promise(resolve => setTimeout(resolve, 1000));

          if (requestorProcess && !requestorProcess.killed) {
              console.log('Requestor process still running, sending SIGKILL.');
              requestorProcess.kill('SIGKILL');
          }
          requestorProcess = null; // Assume killed or will be killed
          console.log('Requestor process stopped.');
          return { success: true };
      } else {
          console.error('Failed to send kill signal to requestor process.');
          // It might have already exited
          if (requestorProcess && requestorProcess.exitCode !== null) {
              console.log('Process had already exited.');
              requestorProcess = null;
              return { success: true }; // Consider it stopped
          }
          return { success: false, error: 'Failed to send kill signal.' };
      }
    } catch (error) {
      console.error('Error stopping requestor process:', error);
      // Attempt to force kill if an error occurred during SIGTERM handling
      if (requestorProcess && !requestorProcess.killed) {
          try { requestorProcess.kill('SIGKILL'); } catch (killError) { console.error('Error sending SIGKILL:', killError); }
      }
      requestorProcess = null; // Clear reference on error
      return { success: false, error: error.message };
    }
  });
  });
  // --- End IPC Handler ---

  createWindow();

  app.on('activate', function () {
    // On macOS it's common to re-create a window in the app when the
    // dock icon is clicked and there are no other windows open.
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

// Ensure requestor process is killed when the app quits
app.on('will-quit', () => {
  if (requestorProcess) {
    console.log('App quitting, killing requestor process...');
    try {
      requestorProcess.kill('SIGKILL'); // Force kill on quit
    } catch (error) {
      console.error('Error killing requestor process on quit:', error);
    }
    requestorProcess = null;
  }
});
app.on('window-all-closed', function () {
  // Quit when all windows are closed, except on macOS. There, it's common
  // for applications and their menu bar to stay active until the user quits
  // explicitly with Cmd + Q.
  if (process.platform !== 'darwin') app.quit();
});
