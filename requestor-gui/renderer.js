// This file is required by the index.html file and will
// be executed in the renderer process for that window.
// All of the Node.js APIs are available in this process.

console.log('Renderer process started');

// --- Configuration ---
const discoveryUrls = {
    prod: 'http://195.201.39.101:9001',
    dev: 'http://127.0.0.1:9001' // Assuming local discovery runs on 9001
};
let currentEnvironment = 'prod'; // Default to production
let isRequestorRunning = false;

// --- UI Element References ---
let envToggle, envLabel, startBtn, stopBtn, statusMessage;
let rentalsDiv, providersDiv;

// --- Data Fetching ---

// Fetch data and update the DOM
async function loadData() {
    // Clear existing lists before loading
    clearLists();
    setLoadingPlaceholders();

    // Fetch in parallel
    const [rentals, providers] = await Promise.all([
        fetchRentals(),
        fetchProviders()
    ]);

    // Update UI after fetching
    updateRentalsList(rentals);
    updateProvidersList(providers);
}

function setLoadingPlaceholders() {
    if (rentalsDiv && rentalsDiv.children.length <= 1) {
         rentalsDiv.innerHTML = '<h2>Current Rentals</h2><p class="loading">Loading rentals...</p>';
    }
     if (providersDiv && providersDiv.children.length <= 1) {
        providersDiv.innerHTML = '<h2>Available Providers</h2><p class="loading">Loading providers...</p>';
    }
}

function clearLists() {
    if (rentalsDiv) rentalsDiv.innerHTML = '<h2>Current Rentals</h2>'; // Keep header
    if (providersDiv) providersDiv.innerHTML = '<h2>Available Providers</h2>'; // Keep header
}

// Fetch rentals from the main process via IPC
async function fetchRentals() {
    console.log('Requesting rentals from main process via IPC...');
    // Only fetch rentals if the requestor is supposed to be running or if we are using the old method
    // For now, we always try, assuming the main process handles it.
    // Later, this might fetch from http://127.0.0.1:8000/rentals if isRequestorRunning is true.
    try {
        // Use the function exposed in preload.js
        const rentals = await window.electronAPI.getRentals();
        console.log('Received rentals from main process:', rentals);

        // Check if the main process returned an error structure
        if (rentals && rentals.error) {
            console.error(`Error fetching rentals from main process: ${rentals.error}`, rentals.details || '');
            return []; // Return empty array on error
        }

        // Ensure the response is an array before returning
        return Array.isArray(rentals) ? rentals : [];
    } catch (error) {
        console.error('Error invoking IPC get-rentals:', error);
        return []; // Return empty array on IPC error
    }
}

// Fetch providers from Discovery Server API based on current environment
async function fetchProviders() {
    const discoveryUrl = discoveryUrls[currentEnvironment];
    console.log(`Fetching providers from ${currentEnvironment} Discovery Server (${discoveryUrl})...`);
    const apiUrl = `${discoveryUrl}/api/v1/advertisements`;

    try {
        const response = await fetch(apiUrl);
        if (!response.ok) {
            console.error(`Error fetching providers: ${response.status} ${response.statusText}`);
            try {
                const errorData = await response.json();
                console.error('Error details:', errorData);
            } catch (jsonError) {
                console.error('Could not parse error response body.');
            }
            return []; // Return empty array on error
        }
        const data = await response.json();
        console.log('Received providers:', data);

        // Transform data to the format expected by the UI
        return data.map(provider => ({
            id: provider.provider_id,
            offer: `CPU: ${provider.resources.cpu}, Mem: ${provider.resources.memory}GB, Disk: ${provider.resources.storage}GB (${provider.country || 'N/A'})`,
            ip_address: provider.ip_address
        }));
    } catch (error) {
        console.error('Network or other error fetching providers:', error);
        return []; // Return empty array on error
    }
}

// --- UI Update Functions ---

function updateRentalsList(rentals) {
    if (!rentalsDiv) return;
    rentalsDiv.innerHTML = '<h2>Current Rentals</h2>'; // Clear previous content except header
    const rentalList = document.createElement('ul');
    rentalList.className = 'data-list';
    rentalsDiv.appendChild(rentalList);

    if (!rentals || rentals.length === 0) {
        const li = document.createElement('li');
        li.textContent = 'No active rentals found or requestor not running.';
        li.className = 'list-placeholder';
        rentalList.appendChild(li);
    } else {
        rentals.forEach(rental => {
            const li = document.createElement('li');
            li.className = 'list-item card';
            li.innerHTML = `
                <span class="item-id">Rental ID: ${rental.id}</span>
                <span class="item-details">Provider: ${rental.provider}</span>
                <span class="item-details">Status: ${rental.status || 'N/A'}</span>
                <button class="btn btn-secondary">Details</button>
            `;
            rentalList.appendChild(li);
        });
    }
}

function updateProvidersList(providers) {
     if (!providersDiv) return;
     providersDiv.innerHTML = '<h2>Available Providers</h2>'; // Clear previous content except header
     const providerList = document.createElement('ul');
     providerList.className = 'data-list';
     providersDiv.appendChild(providerList);

     if (!providers || providers.length === 0) {
        const li = document.createElement('li');
        li.textContent = `No providers found for ${currentEnvironment} environment.`;
        li.className = 'list-placeholder';
        providerList.appendChild(li);
    } else {
        providers.forEach(provider => {
            const li = document.createElement('li');
            li.className = 'list-item card';
            li.innerHTML = `
                <span class="item-id">Provider ID: ${provider.id}</span>
                <span class="item-details">${provider.offer}</span>
                <button class="btn btn-primary">Rent</button>
            `;
            providerList.appendChild(li);
        });
    }
}

function updateStatus(message, isError = false) {
    if (statusMessage) {
        statusMessage.textContent = `Status: ${message}`;
        statusMessage.style.color = isError ? 'red' : '#555';
    }
    console.log(`Status update: ${message}`);
    if (isError) console.error(`Status update (Error): ${message}`);
}

// --- Event Handlers ---

function handleEnvToggleChange() {
    currentEnvironment = envToggle.checked ? 'dev' : 'prod';
    envLabel.textContent = envToggle.checked ? 'Development' : 'Production';
    console.log(`Environment switched to: ${currentEnvironment}`);
    updateStatus(`Switched to ${envLabel.textContent} environment.`);
    // Reload providers for the new environment
    fetchProviders().then(updateProvidersList);
}

async function handleStartRequestor() {
    console.log(`Attempting to start requestor in ${currentEnvironment} mode...`);
    updateStatus(`Starting requestor (${currentEnvironment})...`);
    startBtn.disabled = true;
    envToggle.disabled = true; // Disable toggle while running

    try {
        // IPC call to main process to start the server
        const result = await window.electronAPI.startRequestor(currentEnvironment);
        if (result && result.success) {
            isRequestorRunning = true;
            stopBtn.disabled = false;
            updateStatus(`Requestor started successfully (${currentEnvironment}).`);
            // Optionally, automatically load data after starting
            // loadData();
        } else {
            console.error('Failed to start requestor:', result ? result.error : 'Unknown error');
            updateStatus(`Failed to start requestor: ${result ? result.error : 'Unknown error'}`, true);
            startBtn.disabled = false; // Re-enable start button on failure
            envToggle.disabled = false; // Re-enable toggle on failure
        }
    } catch (error) {
        console.error('Error sending start-requestor IPC message:', error);
        updateStatus(`Error starting requestor: ${error.message}`, true);
        startBtn.disabled = false; // Re-enable start button on error
        envToggle.disabled = false; // Re-enable toggle on error
    }
}

async function handleStopRequestor() {
    console.log('Attempting to stop requestor...');
    updateStatus('Stopping requestor...');
    stopBtn.disabled = true; // Disable stop button immediately

    try {
        // IPC call to main process to stop the server
        const result = await window.electronAPI.stopRequestor();
         if (result && result.success) {
            isRequestorRunning = false;
            startBtn.disabled = false;
            envToggle.disabled = false; // Re-enable toggle when stopped
            updateStatus('Requestor stopped successfully.');
            // Clear rentals list as the source is gone
            updateRentalsList([]);
        } else {
            console.error('Failed to stop requestor:', result ? result.error : 'Unknown error');
            updateStatus(`Failed to stop requestor: ${result ? result.error : 'Unknown error'}`, true);
            stopBtn.disabled = false; // Re-enable stop button on failure (might need manual intervention)
        }
    } catch (error) {
        console.error('Error sending stop-requestor IPC message:', error);
        updateStatus(`Error stopping requestor: ${error.message}`, true);
        stopBtn.disabled = false; // Re-enable stop button on error
    }
}


// --- Initialization ---
window.addEventListener('DOMContentLoaded', () => {
    // Get UI elements
    envToggle = document.getElementById('env-toggle');
    envLabel = document.getElementById('env-label');
    startBtn = document.getElementById('start-btn');
    stopBtn = document.getElementById('stop-btn');
    statusMessage = document.getElementById('status-message');
    rentalsDiv = document.getElementById('rentals');
    providersDiv = document.getElementById('providers');

    // Set initial state
    envToggle.checked = (currentEnvironment === 'dev');
    envLabel.textContent = envToggle.checked ? 'Development' : 'Production';
    startBtn.disabled = false;
    stopBtn.disabled = true; // Can't stop if not started
    envToggle.disabled = false; // Allow changing env when stopped

    // Add event listeners
    envToggle.addEventListener('change', handleEnvToggleChange);
    startBtn.addEventListener('click', handleStartRequestor);
    stopBtn.addEventListener('click', handleStopRequestor);

    // Initial data load
    loadData();
});