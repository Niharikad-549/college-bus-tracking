(() => {
    const element = document.querySelector('[data-active-fleet]');
    if (!element) {
        return;
    }

    const status = element.querySelector('[data-fleet-status]');
    const count = document.querySelector('[data-fleet-count]');
    const map = L.map(element, { scrollWheelZoom: false }).setView([20.371, 72.905], 12);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);

    const markers = new Map();
    let requestInProgress = false;
    let pollTimer = null;
    let hasFitted = false;

    const busPopup = (bus) => {
        const popup = document.createElement('div');
        popup.className = 'route-stop-popup';
        [bus.bus_number, bus.driver_name, bus.route_name].forEach((line) => {
            const item = document.createElement('span');
            item.textContent = line;
            popup.append(item);
        });
        return popup;
    };

    const refreshFleet = async () => {
        if (requestInProgress) {
            return;
        }
        requestInProgress = true;
        try {
            const response = await fetch(element.dataset.activeBusesUrl, {
                headers: { Accept: 'application/json' },
                credentials: 'same-origin'
            });
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.detail || 'Fleet data is unavailable.');
            }

            const busesWithLocations = result.buses.filter((bus) => bus.location);
            const activeBusIds = new Set(result.buses.map((bus) => String(bus.bus_id)));
            markers.forEach((marker, busId) => {
                if (!activeBusIds.has(busId)) {
                    map.removeLayer(marker);
                    markers.delete(busId);
                }
            });

            result.buses.forEach((bus) => {
                if (!bus.location) {
                    return;
                }
                const busId = String(bus.bus_id);
                const point = [Number(bus.location.latitude), Number(bus.location.longitude)];
                let marker = markers.get(busId);
                if (!marker) {
                    marker = L.marker(point, {
                        icon: L.divIcon({
                            className: '',
                            html: '<span class="fleet-bus-icon" aria-hidden="true">🚌</span>',
                            iconSize: [42, 42],
                            iconAnchor: [21, 21]
                        })
                    }).addTo(map);
                    markers.set(busId, marker);
                } else {
                    marker.setLatLng(point);
                }
                marker.bindPopup(busPopup(bus));
            });

            count.textContent = `${result.buses.length} active ${result.buses.length === 1 ? 'bus' : 'buses'}`;
            if (result.buses.length === 0) {
                status.textContent = 'No buses are currently on an active trip.';
            } else if (busesWithLocations.length === 0) {
                status.textContent = 'Active trips are running, but no locations have been reported yet.';
            } else {
                status.textContent = `${busesWithLocations.length} of ${result.buses.length} active buses reporting locations.`;
                if (!hasFitted) {
                    map.fitBounds(L.featureGroup([...markers.values()]).getBounds(), {
                        padding: [36, 36],
                        maxZoom: 14
                    });
                    hasFitted = true;
                }
            }
        } catch (error) {
            status.textContent = 'Live fleet data is unavailable. Check your connection and try again.';
        } finally {
            requestInProgress = false;
        }
    };

    const startPolling = () => {
        if (document.hidden || pollTimer !== null) {
            return;
        }
        refreshFleet();
        pollTimer = window.setInterval(refreshFleet, 5000);
        window.requestAnimationFrame(() => map.invalidateSize());
    };
    const stopPolling = () => {
        if (pollTimer !== null) {
            window.clearInterval(pollTimer);
            pollTimer = null;
        }
    };

    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            stopPolling();
        } else {
            startPolling();
        }
    });
    startPolling();
})();