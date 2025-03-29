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

      // --- Robust Parsing Logic for Tabulate Grid Format ---
      const lines = stdout.trim().split('\n');
      const dataLines = lines.filter(line => line.startsWith('|')); // Keep only lines starting with '|'

      if (dataLines.length < 2) { // Need at least header and one data row line
          console.log('No rental data found in grid format or unexpected format.');
          return [];
      }

      // Extract header names
      const headerLine = dataLines[0];
      const headers = headerLine.split('|').map(h => h.trim().toLowerCase()).filter(h => h); // Split, trim, lowercase, remove empty

      // Find column indices for required fields
      const nameIndex = headers.indexOf('name');
      const providerIndex = headers.indexOf('provider ip'); // Assuming header is 'Provider IP'
      const statusIndex = headers.indexOf('status');
      const cpuIndex = headers.indexOf('cpu');
      const memoryIndex = headers.indexOf('memory (gb)');
      const storageIndex = headers.indexOf('storage (gb)');
      const sshPortIndex = headers.indexOf('ssh port');

      if (nameIndex === -1 || providerIndex === -1 || statusIndex === -1) {
          console.error('Could not find required columns (name, provider ip, status) in header:', headers.join(', '));
          return { error: 'Failed to parse rental list header columns' };
      }

      const rentals = [];
      // Start from the third line containing '|' (index 2), as the second is the separator '======'
      for (let i = 2; i < dataLines.length; i++) {
          const line = dataLines[i];
          const columns = line.split('|').map(c => c.trim()).filter((c, idx) => idx > 0 && idx <= headers.length); // Split, trim, remove first/last empty due to leading/trailing '|'

          if (columns.length === headers.length) {
              const rental = {
                  id: columns[nameIndex], // Use 'name' as 'id' for the UI
                  name: columns[nameIndex],
                  provider_ip: columns[providerIndex],
                  status: columns[statusIndex],
                  // Add optional fields if found
                  cpu: cpuIndex !== -1 ? columns[cpuIndex] : 'N/A',
                  memory: memoryIndex !== -1 ? columns[memoryIndex] : 'N/A',
                  storage: storageIndex !== -1 ? columns[storageIndex] : 'N/A',
                  ssh_port: sshPortIndex !== -1 ? columns[sshPortIndex] : 'N/A'
              };
              if (rental.id) { // Ensure we parsed a valid name/id
                  rentals.push(rental);
              }
          } else {
              console.warn(`Skipping line due to column mismatch: expected ${headers.length}, got ${columns.length}`, line);
          }
      }

      console.log('Parsed rentals:', rentals);
      return rentals;
      // --- End Parsing Logic ---

    } catch (error) {
      console.error('Failed to execute or parse requestor CLI:', error);
      return { error: 'Failed to execute rental list command', details: error.message };
    }
// --- IPC Handler for start-requestor ---
// --- IPC Handler for get-providers ---
  ipcMain.handle('get-providers', async (event, filters = {}) => {
    console.log('Main process received get-providers request with filters:', filters);
    const pythonPath = 'python3'; // Adjust if needed
    const scriptPath = path.join(app.getAppPath(), '../requestor-server/requestor/run.py');
    const args = ['vm', 'providers'];

    // Add filter arguments if provided
    if (filters.cpu) args.push('--cpu', String(filters.cpu));
    if (filters.memory) args.push('--memory', String(filters.memory));
    if (filters.storage) args.push('--storage', String(filters.storage));
    if (filters.country) args.push('--country', filters.country);

    const options = { cwd: path.join(app.getAppPath(), '../requestor-server') };

    console.log(`Executing: ${pythonPath} ${scriptPath} ${args.join(' ')} in ${options.cwd}`);

    try {
      const { stdout, stderr } = await execFilePromise(pythonPath, [scriptPath, ...args], options);

      if (stderr) {
        console.error('Error executing provider list CLI:', stderr);
        return { error: 'Failed to list providers', details: stderr };
      }

      console.log('Provider list CLI output:\n', stdout);

      // --- Parsing Logic for Provider List (Tabulate Grid Format) ---
      const lines = stdout.trim().split('\n');
      const dataLines = lines.filter(line => line.startsWith('|')); // Keep only lines starting with '|'

      if (dataLines.length < 2) {
          console.log('No provider data found in grid format or unexpected format.');
          // Check if the output indicates no providers found explicitly
          if (stdout.includes("No providers found")) {
              return []; // Return empty array if explicitly none found
          }
          // Otherwise, it might be an error or unexpected output
          return { error: 'Failed to parse provider list: No data rows found' };
      }

      // Extract header names (robustly handle potential color codes)
      const headerLine = dataLines[0];
      // Remove ANSI color codes before splitting
      const cleanHeaderLine = headerLine.replace(/\u001b\[[0-9;]*m/g, '');
      const headers = cleanHeaderLine.split('|').map(h => h.trim().toLowerCase()).filter(h => h);

      // Find column indices (adjust names based on actual CLI output headers)
      const idIndex = headers.indexOf('id');
      const cpuIndex = headers.indexOf('cpu');
      const memoryIndex = headers.indexOf('memory (gb)');
      const storageIndex = headers.indexOf('storage (gb)');
      const countryIndex = headers.indexOf('country');
      const priceIndex = headers.indexOf('price (glm/h)'); // Assuming price is included

      if (idIndex === -1 || cpuIndex === -1 || memoryIndex === -1 || storageIndex === -1) {
          console.error('Could not find required columns (id, cpu, memory, storage) in header:', headers.join(', '));
          return { error: 'Failed to parse provider list header columns' };
      }

      const providers = [];
      // Start from the third line containing '|' (index 2)
      for (let i = 2; i < dataLines.length; i++) {
          const line = dataLines[i];
          // Remove ANSI color codes before splitting data rows
          const cleanLine = line.replace(/\u001b\[[0-9;]*m/g, '');
          const columns = cleanLine.split('|').map(c => c.trim()).filter((c, idx) => idx > 0 && idx <= headers.length);

          if (columns.length === headers.length) {
              const provider = {
                  id: columns[idIndex],
                  cpu: columns[cpuIndex],
                  memory: columns[memoryIndex],
                  storage: columns[storageIndex],
                  country: countryIndex !== -1 ? columns[countryIndex] : 'N/A',
                  price: priceIndex !== -1 ? columns[priceIndex] : 'N/A'
              };
              if (provider.id) { // Ensure we parsed a valid ID
                  providers.push(provider);
              }
          } else {
              console.warn(`Skipping provider line due to column mismatch: expected ${headers.length}, got ${columns.length}`, line);
          }
      }

      console.log('Parsed providers:', providers);
      return providers;
      // --- End Parsing Logic ---

    } catch (error) {
      console.error('Failed to execute or parse provider list CLI:', error);
      return { error: 'Failed to execute provider list command', details: error.message };
    }
  });
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
// --- IPC Handler for create-vm ---
  ipcMain.handle('create-vm', async (event, { name, providerId, cpu, memory, storage }) => {
    console.log(`Main process received create-vm request: Name=${name}, Provider=${providerId}, CPU=${cpu}, Mem=${memory}, Disk=${storage}`);
    const pythonPath = 'python3'; // Adjust if needed
    const scriptPath = path.join(app.getAppPath(), '../requestor-server/requestor/run.py');
    const args = [
        'vm', 'create', name,
        '--provider-id', providerId,
        '--cpu', String(cpu),
        '--memory', String(memory),
        '--storage', String(storage)
    ];
    const options = { cwd: path.join(app.getAppPath(), '../requestor-server') };

    console.log(`Executing: ${pythonPath} ${scriptPath} ${args.join(' ')} in ${options.cwd}`);

    try {
      // Use spawn instead of execFile for potentially long-running processes and better output streaming
      const process = spawn(pythonPath, [scriptPath, ...args], options);
      let stdoutData = '';
      let stderrData = '';

      process.stdout.on('data', (data) => {
        stdoutData += data.toString();
        console.log(`Create VM stdout: ${data}`);
        // Optionally send progress updates to renderer
        // event.sender.send('create-vm-progress', data.toString());
      });

      process.stderr.on('data', (data) => {
        stderrData += data.toString();
        console.error(`Create VM stderr: ${data}`);
      });

      const exitCode = await new Promise((resolve) => {
        process.on('close', resolve);
      });

      console.log(`Create VM process exited with code ${exitCode}`);

      if (exitCode === 0 && stdoutData.includes("VM Deployed Successfully")) {
        console.log('VM creation reported success.');
        // Extract SSH details if needed from stdoutData, though the 'list' command will fetch them later
        return { success: true, message: 'VM created successfully!' };
      } else {
        console.error('VM creation failed. Exit Code:', exitCode, 'Stderr:', stderrData, 'Stdout:', stdoutData);
        // Try to extract a more specific error message from stderr or stdout
        const errorMatch = stderrData.match(/Failed to create VM: (.*)/) || stdoutData.match(/Error: (.*)/);
        const errorMessage = errorMatch ? errorMatch[1] : (stderrData || 'Unknown error during VM creation.');
        return { success: false, message: `Failed to create VM: ${errorMessage}` };
      }
    } catch (error) {
      console.error('Error spawning create VM process:', error);
      return { success: false, message: `Failed to start VM creation process: ${error.message}` };
    }
  });

  // --- IPC Handler for destroy-vm ---
  ipcMain.handle('destroy-vm', async (event, vmName) => {
    console.log(`Main process received destroy-vm request for: ${vmName}`);
    const pythonPath = 'python3'; // Adjust if needed
    const scriptPath = path.join(app.getAppPath(), '../requestor-server/requestor/run.py');
    // Add --yes to bypass confirmation prompt if the CLI command supports it
    // If not, we might need to handle stdin, but execFile is simpler if no interaction needed.
    const args = ['vm', 'destroy', vmName]; // Assuming no confirmation needed or handled by CLI flag
    const options = { cwd: path.join(app.getAppPath(), '../requestor-server') };

    console.log(`Executing: ${pythonPath} ${scriptPath} ${args.join(' ')} in ${options.cwd}`);

    try {
      // Using execFile as destroy is usually faster and less interactive
      const { stdout, stderr } = await execFilePromise(pythonPath, [scriptPath, ...args], options);

      if (stderr) {
        // Check stderr first for explicit failure messages
        console.error(`Destroy VM stderr for ${vmName}:`, stderr);
        const errorMatch = stderr.match(/Failed to destroy VM: (.*)/);
        const errorMessage = errorMatch ? errorMatch[1] : stderr;
         // Check if the error indicates the VM was already gone
        if (errorMessage.includes("not found on provider") || errorMessage.includes("VM not found")) {
            console.log(`VM ${vmName} reported as not found during destroy, considering it success.`);
            return { success: true, message: `VM ${vmName} already removed or not found.` };
        }
        return { success: false, message: `Failed to destroy VM: ${errorMessage}` };
      }

      // Check stdout for success message
      if (stdout.includes("VM Destroyed Successfully")) {
        console.log(`VM ${vmName} destroyed successfully.`);
        return { success: true, message: `VM ${vmName} destroyed successfully.` };
      } else {
         // If no explicit success message and no stderr, assume failure based on output
         console.warn(`Destroy VM stdout for ${vmName} did not contain expected success message:`, stdout);
         return { success: false, message: 'Destroy command finished, but success confirmation was not found.' };
      }

    } catch (error) {
      console.error(`Error executing destroy VM command for ${vmName}:`, error);
       // Check if the error indicates the VM was already gone (e.g., from a previous failed attempt)
       if (error.stderr && (error.stderr.includes("not found on provider") || error.stderr.includes("VM not found"))) {
            console.log(`VM ${vmName} reported as not found during destroy (in catch block), considering it success.`);
            return { success: true, message: `VM ${vmName} already removed or not found.` };
       }
      return { success: false, message: `Error destroying VM: ${error.message}` };
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
