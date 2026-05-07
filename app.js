// Configuration
const API_URL = 'http://localhost:5001/data';
const POLL_INTERVAL = 2000;

// State Management
let map;
let markers = {};
let riderMarker;
let isSimulating = false;
let pollTimer = null;

// Initialize Map
function initMap() {
    // Dark mode tiles
    map = L.map('map', {
        zoomControl: false,
        attributionControl: false
    }).setView([19.0760, 72.8777], 13);

    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        maxZoom: 19
    }).addTo(map);

    // Rider Icon
    const riderIcon = L.icon({
        iconUrl: 'rider.png',
        iconSize: [40, 40],
        iconAnchor: [20, 40]
    });

    riderMarker = L.marker([19.0760, 72.8777], { icon: riderIcon }).addTo(map);
    riderMarker.bindPopup("<b>Rider Location</b><br>Mumbai Central").openPopup();
}

// Fetch Data from Python Backend
async function fetchData() {
    try {
        const response = await fetch(API_URL);
        const data = await response.json();
        updateUI(data);
    } catch (err) {
        console.error("Backend connection failed:", err);
    }
}

function updateUI(data) {
    const { drivers, alerts } = data;
    
    // Update Stats
    document.getElementById('count-drivers').innerText = Object.keys(drivers).length;

    // Update Drivers List & Markers
    const driversList = document.getElementById('drivers-list');
    driversList.innerHTML = '';

    const carIcon = L.icon({
        iconUrl: 'car.png',
        iconSize: [32, 32],
        iconAnchor: [16, 16]
    });

    for (const [id, info] of Object.entries(drivers)) {
        // 1. Update/Create Marker
        if (!markers[id]) {
            markers[id] = L.marker(info.location, { icon: carIcon }).addTo(map);
            markers[id].bindTooltip(`Driver ${id}`, { permanent: false });
        } else {
            // Smooth move
            animateMarker(markers[id], info.location);
        }

        // 2. Add Card to List
        const card = document.createElement('div');
        card.className = 'driver-card';
        card.innerHTML = `
            <div class="driver-header">
                <span class="driver-id">${id}</span>
                <span class="driver-status">${info.status}</span>
            </div>
            <div class="driver-metrics">
                <div><span class="metric-label">Speed:</span> ${info.speed} km/h</div>
                <div><span class="metric-label">ETA:</span> ${info.eta} min</div>
                <div><span class="metric-label">Avg:</span> ${info.avg_speed} km/h</div>
                <div><span class="metric-label">Dist:</span> ${info.distance} km</div>
            </div>
        `;
        driversList.appendChild(card);
    }

    // Update Alerts
    const alertsList = document.getElementById('alerts-list');
    if (alerts.length > 0) {
        alertsList.innerHTML = '';
        alerts.forEach(a => {
            const item = document.createElement('div');
            item.className = 'alert-item';
            item.innerHTML = `
                <span class="time">${a.time}</span>
                <span class="msg">Driver ${a.driver_id}: ${a.msg}</span>
            `;
            alertsList.appendChild(item);
        });
    }
}

// Simple Marker Animation
function animateMarker(marker, newPos) {
    const startPos = marker.getLatLng();
    const duration = POLL_INTERVAL;
    const start = performance.now();

    function step(timestamp) {
        const progress = Math.min((timestamp - start) / duration, 1);
        const lat = startPos.lat + (newPos[0] - startPos.lat) * progress;
        const lng = startPos.lng + (newPos[1] - startPos.lng) * progress;
        marker.setLatLng([lat, lng]);

        if (progress < 1) {
            requestAnimationFrame(step);
        }
    }
    requestAnimationFrame(step);
}

// Controls
document.getElementById('btn-toggle').addEventListener('click', (e) => {
    isSimulating = !isSimulating;
    if (isSimulating) {
        e.target.innerText = "Stop Monitoring";
        e.target.classList.add('danger');
        pollTimer = setInterval(fetchData, POLL_INTERVAL);
        fetchData();
    } else {
        e.target.innerText = "Start Monitoring";
        e.target.classList.remove('danger');
        clearInterval(pollTimer);
    }
});

document.getElementById('btn-reset').addEventListener('click', () => {
    map.setView([19.0760, 72.8777], 13);
});

// Start
initMap();
