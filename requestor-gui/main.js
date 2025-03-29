const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { execFile } = require('child_process');
const util = require('util');

// Promisify execFile for easier async/await usage
const execFilePromise = util.promisify(execFile);

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
  });
  // --- End IPC Handler ---

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
  if (process.platform !== 'darwin') app.quit();
});
