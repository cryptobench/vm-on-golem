const { app, BrowserWindow, ipcMain, shell } = require('electron');
const { spawn } = require('child_process');
const path = require('path');

let mainWindow;

function createWindow () {
  mainWindow = new BrowserWindow({
    width: 1000,
    height: 720,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  mainWindow.loadFile('index.html');
  // mainWindow.webContents.openDevTools();

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// Relay minimal notifications to renderer if needed later
function sendStatusUpdate(status) {
  if (mainWindow && mainWindow.webContents && !mainWindow.webContents.isDestroyed()) {
    mainWindow.webContents.send('provider-status-update', status);
  }
}

// Optional: receive shutdown requests from renderer and just pass-through
ipcMain.on('shutdown-provider', () => {
  sendStatusUpdate({ type: 'status', message: 'Shutdown requested...' });
});

app.whenReady().then(() => {
  createWindow();
  app.on('activate', function () {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
  // Optionally auto-start provider in background when GUI launches
  // startProviderSafe();
});

app.on('window-all-closed', function () {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// --- Provider CLI helpers -------------------------------------------------

function cliBinaryPath() {
  const resBase = process.resourcesPath; // points to app.asar/../Resources on packaged builds
  const plat = process.platform;
  try {
    if (plat === 'win32') {
      const p = path.join(resBase, 'cli', 'win', 'golem-provider.exe');
      return p;
    }
    if (plat === 'darwin') {
      const p = path.join(resBase, 'cli', 'macos', 'golem-provider');
      return p;
    }
    // linux
    return path.join(resBase, 'cli', 'linux', 'golem-provider');
  } catch (_) {
    return null;
  }
}

function providerInvoker(baseArgs) {
  // When packaged, prefer embedded CLI
  if (app.isPackaged) {
    const embedded = cliBinaryPath();
    if (embedded) return { cmd: embedded, args: baseArgs, opts: { detached: true, stdio: 'ignore' } };
  }

  // Allow override via env to support custom launchers
  const override = process.env.PROVIDER_CLI_CMD; // e.g., "poetry -C provider-server run golem-provider"
  if (override && override.trim().length > 0) {
    // Use shell to support full command strings
    return { cmd: override + ' ' + baseArgs.join(' '), args: [], opts: { shell: true, detached: true, stdio: 'ignore' } };
  }

  // Dev-friendly default: invoke via Poetry from repo
  // Requires Poetry and provider-server deps installed locally
  const poetryArgs = ['-C', 'provider-server', 'run', 'golem-provider', ...baseArgs];
  return { cmd: 'poetry', args: poetryArgs, opts: { detached: true, stdio: 'ignore' } };
}

function startProviderSafe() {
  const { cmd, args, opts } = providerInvoker(['start', '--daemon']);
  try {
    const child = spawn(cmd, args, opts);
    if (child && typeof child.unref === 'function') child.unref();
    sendStatusUpdate({ type: 'started', message: 'Provider start requested' });
  } catch (e) {
    sendStatusUpdate({ type: 'error', message: 'Failed to start provider: ' + e.message });
  }
}

function stopProviderSafe() {
  const { cmd, args, opts } = providerInvoker(['stop']);
  try {
    const child = spawn(cmd, args, opts);
    if (child && typeof child.unref === 'function') child.unref();
    sendStatusUpdate({ type: 'stopped', message: 'Provider stop requested' });
  } catch (e) {
    sendStatusUpdate({ type: 'error', message: 'Failed to stop provider: ' + e.message });
  }
}

ipcMain.handle('provider-start', async () => {
  startProviderSafe();
  return { ok: true };
});

ipcMain.handle('provider-stop', async () => {
  stopProviderSafe();
  return { ok: true };
});

// Multipass check and helpers
ipcMain.handle('multipass-check', async () => {
  try {
    const child = spawn('multipass', ['--version'], { stdio: ['ignore', 'pipe', 'pipe'] });
    let out = '';
    await new Promise((resolve) => {
      child.stdout.on('data', (d) => (out += d.toString()));
      child.on('close', () => resolve());
      child.on('error', () => resolve());
    });
    return { ok: true, version: (out || '').trim() };
  } catch (e) {
    return { ok: false };
  }
});

ipcMain.handle('open-external', async (_e, url) => {
  try {
    await shell.openExternal(url);
    return { ok: true };
  } catch (e) {
    return { ok: false, error: String(e) };
  }
});
