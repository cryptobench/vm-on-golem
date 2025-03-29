// This file is required by the index.html file and will
// be executed in the renderer process for that window.
// All of the Node.js APIs are available in this process.

console.log('Renderer process started');

// --- UI Element References ---
let statusMessage, rentalListDiv, providerListDiv, refreshProvidersBtn;
let rentModal, rentModalProviderId, rentModalProviderDetails, rentModalVmNameInput, confirmRentBtn, cancelRentBtn;

// --- Data Fetching & State ---
let currentRentals = [];
let currentProviders = [];
let isLoadingRentals = false;
let isLoadingProviders = false;

// --- Helper Functions ---

function updateStatus(message, isError = false, isLoading = false) {
    if (statusMessage) {
        statusMessage.textContent = message;
        statusMessage.className = isError ? 'status-error' : (isLoading ? 'status-loading' : 'status-ok');
    }
    if (isError) console.error(`Status update (Error): ${message}`);
    else console.log(`Status update: ${message}`);
}

function showLoadingIndicator(listDiv, type) {
    listDiv.innerHTML = `<p class="loading">Loading ${type}...</p>`;
}

function clearList(listDiv) {
    listDiv.innerHTML = ''; // Clear previous content
}

// --- Data Fetching ---

async function fetchRentals() {
    if (isLoadingRentals) return;
    isLoadingRentals = true;
    updateStatus('Fetching rentals...', false, true);
    showLoadingIndicator(rentalListDiv, 'rentals');

    try {
        const rentals = await window.electronAPI.getRentals();
        console.log('Received rentals from main process:', rentals);

        if (rentals && rentals.error) {
            updateStatus(`Error fetching rentals: ${rentals.error}`, true);
            currentRentals = [];
        } else {
            currentRentals = Array.isArray(rentals) ? rentals : [];
            updateStatus('Rentals loaded successfully.');
        }
    } catch (error) {
        console.error('Error invoking IPC get-rentals:', error);
        updateStatus(`Failed to fetch rentals: ${error.message}`, true);
        currentRentals = [];
    } finally {
        isLoadingRentals = false;
        updateRentalsList(); // Update UI regardless of success/failure
    }
}

async function fetchProviders(filters = {}) {
    if (isLoadingProviders) return;
    isLoadingProviders = true;
    updateStatus('Fetching providers...', false, true);
    showLoadingIndicator(providerListDiv, 'providers');
    refreshProvidersBtn.disabled = true;

    try {
        const providers = await window.electronAPI.getProviders(filters);
        console.log('Received providers from main process:', providers);

        if (providers && providers.error) {
            updateStatus(`Error fetching providers: ${providers.error}`, true);
            currentProviders = [];
        } else {
            currentProviders = Array.isArray(providers) ? providers : [];
            updateStatus('Providers loaded successfully.');
        }
    } catch (error) {
        console.error('Error invoking IPC get-providers:', error);
        updateStatus(`Failed to fetch providers: ${error.message}`, true);
        currentProviders = [];
    } finally {
        isLoadingProviders = false;
        refreshProvidersBtn.disabled = false;
        updateProvidersList(); // Update UI regardless of success/failure
    }
}

// --- UI Update Functions ---

function updateRentalsList() {
    clearList(rentalListDiv);

    if (currentRentals.length === 0 && !isLoadingRentals) {
        rentalListDiv.innerHTML = '<p class="placeholder">No active rentals found.</p>';
        return;
    }

    currentRentals.forEach(rental => {
        const card = document.createElement('div');
        card.className = 'card rental-card';
        card.innerHTML = `
            <div class="card-body">
                <h5 class="card-title">VM: ${rental.name || 'N/A'}</h5>
                <p class="card-text">Status: <span class="status-${(rental.status || 'unknown').toLowerCase()}">${rental.status || 'Unknown'}</span></p>
                <p class="card-text-small">Provider IP: ${rental.provider_ip || 'N/A'}</p>
                <p class="card-text-small">SSH Port: ${rental.ssh_port || 'N/A'}</p>
                <p class="card-text-small">CPU: ${rental.cpu || 'N/A'}, Mem: ${rental.memory || 'N/A'}GB, Disk: ${rental.storage || 'N/A'}GB</p>
            </div>
            <div class="card-actions">
                <button class="btn btn-danger btn-small destroy-btn" data-vm-name="${rental.name}">Destroy</button>
            </div>
        `;
        // Add event listener for the destroy button
        const destroyBtn = card.querySelector('.destroy-btn');
        if (destroyBtn) {
            destroyBtn.addEventListener('click', handleDestroyClick);
        }
        rentalListDiv.appendChild(card);
    });
}

function updateProvidersList() {
    clearList(providerListDiv);

    if (currentProviders.length === 0 && !isLoadingProviders) {
        providerListDiv.innerHTML = '<p class="placeholder">No providers found matching criteria.</p>';
        return;
    }

    currentProviders.forEach(provider => {
        const card = document.createElement('div');
        card.className = 'card provider-card';
        // Ensure data exists before displaying
        const cpu = provider.cpu || 'N/A';
        const memory = provider.memory || 'N/A';
        const storage = provider.storage || 'N/A';
        const country = provider.country || 'N/A';
        const price = provider.price ? `${provider.price} GLM/h` : 'N/A';

        card.innerHTML = `
            <div class="card-body">
                <h5 class="card-title">Provider: ${provider.id.substring(0, 12)}...</h5>
                 <p class="card-text">Resources: ${cpu} CPU, ${memory} GB RAM, ${storage} GB Disk</p>
                 <p class="card-text-small">Location: ${country}</p>
                 <p class="card-text-small">Price: ${price}</p>
            </div>
            <div class="card-actions">
                <button class="btn btn-primary btn-small rent-btn" data-provider-id="${provider.id}" data-cpu="${cpu}" data-memory="${memory}" data-storage="${storage}">Rent</button>
            </div>
        `;
         // Add event listener for the rent button
        const rentBtn = card.querySelector('.rent-btn');
        if (rentBtn) {
            rentBtn.addEventListener('click', handleRentClick);
        }
        providerListDiv.appendChild(card);
    });
}


// --- Modal Handling ---

function openRentModal(providerId, cpu, memory, storage) {
    if (!rentModal) return;
    rentModalProviderId.textContent = providerId;
    rentModalProviderDetails.textContent = `CPU: ${cpu}, Memory: ${memory}GB, Storage: ${storage}GB`;
    rentModalVmNameInput.value = `my-vm-${Date.now().toString().slice(-5)}`; // Default VM name
    rentModal.style.display = 'block';

    // Store details needed for confirmation
    confirmRentBtn.dataset.providerId = providerId;
    confirmRentBtn.dataset.cpu = cpu;
    confirmRentBtn.dataset.memory = memory;
    confirmRentBtn.dataset.storage = storage;
}

function closeRentModal() {
    if (rentModal) {
        rentModal.style.display = 'none';
        // Clear stored data
        delete confirmRentBtn.dataset.providerId;
        delete confirmRentBtn.dataset.cpu;
        delete confirmRentBtn.dataset.memory;
        delete confirmRentBtn.dataset.storage;
    }
}

// --- Event Handlers ---

function handleRentClick(event) {
    const button = event.currentTarget;
    const providerId = button.dataset.providerId;
    const cpu = button.dataset.cpu;
    const memory = button.dataset.memory;
    const storage = button.dataset.storage;
    openRentModal(providerId, cpu, memory, storage);
}

async function handleConfirmRent() {
    const vmName = rentModalVmNameInput.value.trim();
    const providerId = confirmRentBtn.dataset.providerId;
    const cpu = parseInt(confirmRentBtn.dataset.cpu, 10);
    const memory = parseInt(confirmRentBtn.dataset.memory, 10);
    const storage = parseInt(confirmRentBtn.dataset.storage, 10);

    if (!vmName) {
        updateStatus('VM name cannot be empty.', true);
        return;
    }
    if (!providerId || isNaN(cpu) || isNaN(memory) || isNaN(storage)) {
         updateStatus('Missing provider details for renting.', true);
         return;
    }

    closeRentModal();
    updateStatus(`Attempting to rent VM '${vmName}' from ${providerId}...`, false, true);

    try {
        const vmDetails = { name: vmName, providerId, cpu, memory, storage };
        console.log('Sending create-vm request:', vmDetails);
        const result = await window.electronAPI.createVm(vmDetails);

        if (result && result.error) {
            updateStatus(`Error creating VM: ${result.error} ${result.details || ''}`, true);
        } else if (result && result.success) {
            updateStatus(`VM '${vmName}' created successfully! Refreshing rentals...`);
            await fetchRentals(); // Refresh the rentals list
        } else {
             // Handle cases where the CLI might output success messages directly
             // Check if the result (stdout) contains success indicators
             if (typeof result === 'string' && result.includes("VM Deployed Successfully")) {
                 updateStatus(`VM '${vmName}' created successfully (parsed from output)! Refreshing rentals...`);
                 await fetchRentals(); // Refresh the rentals list
             } else {
                updateStatus(`Unknown outcome creating VM '${vmName}'. Check logs.`, true);
                console.warn('Unknown response from createVm:', result);
             }
        }
    } catch (error) {
        console.error('Error invoking IPC create-vm:', error);
        updateStatus(`Failed to send rent command: ${error.message}`, true);
    }
}

async function handleDestroyClick(event) {
    const button = event.currentTarget;
    const vmName = button.dataset.vmName;

    if (!vmName) {
        updateStatus('Could not identify VM to destroy.', true);
        return;
    }

    // Optional: Add a confirmation dialog here
    // if (!confirm(`Are you sure you want to destroy VM '${vmName}'?`)) {
    //     return;
    // }

    updateStatus(`Attempting to destroy VM '${vmName}'...`, false, true);
    button.disabled = true; // Disable button during operation

    try {
        console.log(`Sending destroy-vm request for: ${vmName}`);
        const result = await window.electronAPI.destroyVm(vmName);

        if (result && result.error) {
            updateStatus(`Error destroying VM: ${result.error} ${result.details || ''}`, true);
            button.disabled = false; // Re-enable on error
        } else if (result && result.success) {
            updateStatus(`VM '${vmName}' destroyed successfully! Refreshing rentals...`);
            await fetchRentals(); // Refresh the rentals list
        } else {
             // Handle cases where the CLI might output success messages directly
             if (typeof result === 'string' && result.includes("VM Destroyed Successfully")) {
                 updateStatus(`VM '${vmName}' destroyed successfully (parsed from output)! Refreshing rentals...`);
                 await fetchRentals(); // Refresh the rentals list
             } else {
                updateStatus(`Unknown outcome destroying VM '${vmName}'. Check logs.`, true);
                console.warn('Unknown response from destroyVm:', result);
                button.disabled = false; // Re-enable on unknown outcome
             }
        }
    } catch (error) {
        console.error('Error invoking IPC destroy-vm:', error);
        updateStatus(`Failed to send destroy command: ${error.message}`, true);
        button.disabled = false; // Re-enable on error
    }
}

function handleRefreshProviders() {
    fetchProviders(); // Fetch providers again (no filters for now)
}

// --- Initialization ---
window.addEventListener('DOMContentLoaded', () => {
    // Get UI elements
    statusMessage = document.getElementById('status-message');
    rentalListDiv = document.getElementById('rental-list');
    providerListDiv = document.getElementById('provider-list');
    refreshProvidersBtn = document.getElementById('refresh-providers-btn');

    // Modal elements
    rentModal = document.getElementById('rent-modal');
    rentModalProviderId = document.getElementById('rent-modal-provider-id');
    rentModalProviderDetails = document.getElementById('rent-modal-provider-details');
    rentModalVmNameInput = document.getElementById('rent-modal-vm-name');
    confirmRentBtn = document.getElementById('confirm-rent-btn');
    cancelRentBtn = document.getElementById('cancel-rent-btn');
    const closeModalBtn = document.querySelector('.modal .close');


    // Add event listeners
    refreshProvidersBtn.addEventListener('click', handleRefreshProviders);
    confirmRentBtn.addEventListener('click', handleConfirmRent);
    cancelRentBtn.addEventListener('click', closeRentModal);
    if(closeModalBtn) closeModalBtn.addEventListener('click', closeRentModal);

    // Close modal if clicking outside of it
    window.onclick = function(event) {
        if (event.target == rentModal) {
            closeRentModal();
        }
    }

    // Initial data load
    updateStatus('Initializing GUI...');
    fetchRentals();
    fetchProviders();
});
