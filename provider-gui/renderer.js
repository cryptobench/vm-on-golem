console.log('Renderer script loaded.');

// Example: Function to fetch data from the provider API
async function getProviderStatus() {
    // Assuming the provider API runs on localhost:8000 (default in provider-server/config.py)
    // We'll need to confirm this and make it configurable later.
    const apiUrl = 'http://localhost:8000/status'; // Replace with actual status endpoint if different

    try {
        // Note: We might need to handle CORS on the Python server side.
        const response = await fetch(apiUrl);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        console.log('Provider Status:', data);
        // Update the UI with the status data
        document.querySelector('p').textContent = `Status: ${JSON.stringify(data)}`;
    } catch (error) {
        console.error('Error fetching provider status:', error);
        document.querySelector('p').textContent = `Error fetching status: ${error.message}`;
    }
}

// Call the function when the page loads
window.addEventListener('DOMContentLoaded', () => {
    getProviderStatus();
});