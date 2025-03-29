const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const statusDiv = document.getElementById('status');
const logsDiv = document.getElementById('logs');

function addLog(message, type = 'log') {
    const logEntry = document.createElement('div');
    // Sanitize message slightly - replace potential HTML tags just in case
    logEntry.textContent = message.replace(/</g, "&lt;").replace(/>/g, "&gt;");
    if (type === 'error') {
        logEntry.classList.add('error');
    }
    // Add timestamp
    const timestamp = new Date().toLocaleTimeString();
    logEntry.textContent = `[${timestamp}] ${logEntry.textContent}`;

    logsDiv.appendChild(logEntry);
    // Auto-scroll to the bottom
    logsDiv.scrollTop = logsDiv.scrollHeight;
}

// Ensure elements exist before adding listeners
if (startBtn && stopBtn && statusDiv && logsDiv && window.electronAPI) {
    startBtn.addEventListener('click', () => {
        addLog('Requesting provider start...');
        statusDiv.textContent = 'Status: Starting...'; // Update status immediately
        window.electronAPI.startProvider();
    });

    stopBtn.addEventListener('click', () => {
        addLog('Requesting provider stop...');
        statusDiv.textContent = 'Status: Stopping...'; // Update status immediately
        window.electronAPI.stopProvider();
    });

    window.electronAPI.onProviderStatusUpdate((status) => {
        console.log('Received status update:', status); // Log to dev console
        if (status.type === 'status') {
            statusDiv.textContent = `Status: ${status.message}`;
            addLog(`Status Update: ${status.message}`); // Also add to log area
        } else if (status.type === 'log') {
            addLog(status.message);
        } else if (status.type === 'error') {
            // Display error in status temporarily, but keep logs for details
            statusDiv.textContent = `Status: Error occurred (see logs)`;
            addLog(`ERROR: ${status.message}`, 'error');
        }
    });

    // Initial status message on load
    statusDiv.textContent = 'Status: Ready';
    addLog('GUI Initialized. Ready to start provider.');

    console.log('Renderer script loaded and listeners attached.');

} else {
    console.error('Renderer Error: Could not find required elements or electronAPI.');
    // Display error in the UI if elements are missing
    if (!statusDiv) {
        document.body.innerHTML = '<h1>Error: UI elements missing.</h1>';
    } else {
        statusDiv.textContent = 'Status: Error initializing UI.';
        if (logsDiv) addLog('Error: Could not find required elements or electronAPI.', 'error');
    }
}