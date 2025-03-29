// This file is required by the index.html file and will
// be executed in the renderer process for that window.
// All of the Node.js APIs are available in this process.

console.log('Renderer process started');

// Example: Fetch data and update the DOM
// async function loadData() {
//     // Replace with actual API calls to Golem or backend
//     const rentals = await fetchRentals();
//     const providers = await fetchProviders();

//     const rentalsDiv = document.getElementById('rentals');
//     const providersDiv = document.getElementById('providers');

//     // Clear existing content (optional)
//     rentalsDiv.innerHTML = '<h2>Current Rentals</h2>';
//     providersDiv.innerHTML = '<h2>Available Providers</h2>';

//     // Populate rentals list
//     rentals.forEach(rental => {
//         const p = document.createElement('p');
//         p.textContent = `Rental ID: ${rental.id}, Provider: ${rental.provider}`;
//         rentalsDiv.appendChild(p);
//     });

//     // Populate providers list
//     providers.forEach(provider => {
//         const p = document.createElement('p');
//         p.textContent = `Provider ID: ${provider.id}, Offer: ${provider.offer}`;
//         providersDiv.appendChild(p);
//     });
// }

// // Dummy fetch functions (replace with actual implementations)
// async function fetchRentals() {
//     console.log('Fetching rentals...');
//     // Simulate API call
//     await new Promise(resolve => setTimeout(resolve, 500));
//     return [
//         { id: 'r123', provider: 'pXYZ' },
//         { id: 'r456', provider: 'pABC' }
//     ];
// }

// async function fetchProviders() {
//     console.log('Fetching providers...');
//     // Simulate API call
//     await new Promise(resolve => setTimeout(resolve, 500));
//     return [
//         { id: 'pXYZ', offer: 'Offer A - 1 CPU, 2GB RAM' },
//         { id: 'pABC', offer: 'Offer B - 4 CPU, 8GB RAM' },
//         { id: 'pDEF', offer: 'Offer C - 2 CPU, 4GB RAM' }
//     ];
// }

// // Load data when the window loads
// window.addEventListener('DOMContentLoaded', () => {
//     loadData();
// });
