// This file is required by the index.html file and will
// be executed in the renderer process for that window.
// All of the Node.js APIs are available in this process.

console.log('Renderer process started');

// Fetch data and update the DOM
async function loadData() {
    // Replace with actual API calls to the requestor REST API
    const rentals = await fetchRentals();
    const providers = await fetchProviders();

    const rentalsDiv = document.getElementById('rentals');
    const providersDiv = document.getElementById('providers');

    // Clear existing content (keeping headers)
    const rentalList = document.createElement('ul');
    rentalList.className = 'data-list';
    rentalsDiv.appendChild(rentalList);

    const providerList = document.createElement('ul');
    providerList.className = 'data-list';
    providersDiv.appendChild(providerList);


    // Populate rentals list
    if (rentals.length === 0) {
        const li = document.createElement('li');
        li.textContent = 'No active rentals.';
        li.className = 'list-placeholder';
        rentalList.appendChild(li);
    } else {
        rentals.forEach(rental => {
            const li = document.createElement('li');
            li.className = 'list-item card'; // Add card class for styling
            li.innerHTML = `
                <span class="item-id">Rental ID: ${rental.id}</span>
                <span class="item-details">Provider: ${rental.provider}</span>
                <button class="btn btn-secondary">Details</button>
            `;
            rentalList.appendChild(li);
        });
    }

    // Populate providers list
     if (providers.length === 0) {
        const li = document.createElement('li');
        li.textContent = 'No providers found.';
        li.className = 'list-placeholder';
        providerList.appendChild(li);
    } else {
        providers.forEach(provider => {
            const li = document.createElement('li');
            li.className = 'list-item card'; // Add card class for styling
            li.innerHTML = `
                <span class="item-id">Provider ID: ${provider.id}</span>
                <span class="item-details">${provider.offer}</span>
                <button class="btn btn-primary">Rent</button>
            `;
            providerList.appendChild(li);
        });
    }
}

// Fetch rentals from the main process via IPC
async function fetchRentals() {
    console.log('Requesting rentals from main process via IPC...');
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

// Fetch providers from Discovery Server API
async function fetchProviders() {
    console.log('Fetching providers from Discovery Server...');
    const discoveryUrl = 'http://195.201.39.101:9001'; // TODO: Make this configurable
    const apiUrl = `${discoveryUrl}/api/v1/advertisements`;

    try {
        const response = await fetch(apiUrl);
        if (!response.ok) {
            console.error(`Error fetching providers: ${response.status} ${response.statusText}`);
            // Try to get error details from response body
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
            // Add other relevant fields if needed, e.g., ip_address
            ip_address: provider.ip_address
        }));
    } catch (error) {
        console.error('Network or other error fetching providers:', error);
        return []; // Return empty array on error
    }
}

// Load data when the window loads
window.addEventListener('DOMContentLoaded', () => {
    // Add placeholders initially
    const rentalsDiv = document.getElementById('rentals');
    const providersDiv = document.getElementById('providers');
    if (rentalsDiv.children.length <= 1) { // Only add if not already populated (e.g. by HMR)
         rentalsDiv.innerHTML = '<h2>Current Rentals</h2><p class="loading">Loading rentals...</p>';
    }
     if (providersDiv.children.length <= 1) {
        providersDiv.innerHTML = '<h2>Available Providers</h2><p class="loading">Loading providers...</p>';
    }

    loadData();
});
