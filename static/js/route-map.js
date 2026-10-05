(() => {
    const mapElements = document.querySelectorAll('[data-route-map]');

    mapElements.forEach(async (element) => {
        const status = element.querySelector('[data-map-status]');
        const isStudentMap = element.dataset.liveStudent === 'true';
        const mapLayout = element.closest('[data-student-map-layout]');
        const liveCard = mapLayout?.querySelector('[data-student-live-card]');
        const locationStatus = liveCard?.querySelector('[data-location-status]')
            || element.parentElement.querySelector('[data-location-status]');
        try {
            const response = await fetch(element.dataset.stopsUrl, {
                headers: { Accept: 'application/json' }
            });
            if (!response.ok) {
                throw new Error(`Stops request failed (${response.status}).`);
            }

            const stops = await response.json();
            if (!Array.isArray(stops) || stops.length === 0) {
                status.textContent = 'This route does not have any stops yet.';
                return;
            }

            const map = L.map(element, { scrollWheelZoom: false });
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                maxZoom: 19,
                attribution: '&copy; OpenStreetMap contributors'
            }).addTo(map);

            const coordinates = stops.map((stop) => [Number(stop.latitude), Number(stop.longitude)]);
            const bounds = L.latLngBounds(coordinates);
            const markers = L.featureGroup().addTo(map);
            const pickupStopId = element.dataset.pickupStopId;
            const fitRouteBounds = (lineBounds = null) => {
                const fitBounds = !isStudentMap && lineBounds
                    ? bounds.clone().extend(lineBounds)
                    : bounds;
                const bottomPadding = isStudentMap
                    ? Math.min(350, Math.round(element.clientHeight * 0.44))
                    : 28;
                map.fitBounds(fitBounds, {
                    paddingTopLeft: [28, 28],
                    paddingBottomRight: [28, bottomPadding],
                    maxZoom: 15
                });
            };

            stops.forEach((stop, index) => {
                const isPickup = pickupStopId && String(stop.id) === pickupStopId;
                const marker = L.marker(coordinates[index], {
                    icon: L.divIcon({
                        className: '',
                        html: `<span class="route-stop-marker${isPickup ? ' is-pickup' : ''}">${index + 1}</span>`,
                        iconSize: [28, 28],
                        iconAnchor: [14, 14]
                    })
                });

                const popup = document.createElement('div');
                popup.className = 'route-stop-popup';
                const name = document.createElement('strong');
                name.textContent = stop.stop_name;
                const order = document.createElement('span');
                order.textContent = isPickup ? `Stop ${stop.stop_order} · Your pickup` : `Stop ${stop.stop_order}`;
                popup.append(name, order);
                marker.bindPopup(popup);
                markers.addLayer(marker);
            });

            let routeLine = L.polyline(coordinates, {
                color: '#173f35',
                weight: 4,
                opacity: 0.78,
                dashArray: '8 7'
            }).addTo(map);
            fitRouteBounds();
            if (coordinates.length === 1) {
                map.setView(coordinates[0], 14);
            }

            let busMarker = null;
            let locationRequestInProgress = false;
            let locationPollTimer = null;
            let busAnimationFrame = null;
            let lastLocationTimestamp = null;

            const setStudentLiveStatus = (locationData) => {
                if (!liveCard) {
                    return;
                }

                const tripIsActive = Boolean(locationData.trip_status?.is_active);
                const tripStatus = liveCard.querySelector('[data-trip-status]');
                const liveIndicator = liveCard.querySelector('[data-live-indicator]');
                const lastUpdated = liveCard.querySelector('[data-last-updated]');
                const speed = liveCard.querySelector('[data-speed]');
                const busNumber = liveCard.querySelector('[data-bus-number]');
                const driverName = liveCard.querySelector('[data-driver-name]');

                busNumber.textContent = locationData.bus_number || 'Bus not assigned';
                driverName.textContent = locationData.driver_name || 'Driver not assigned';
                tripStatus.textContent = tripIsActive ? 'Trip active' : 'Trip not started';
                tripStatus.classList.toggle('is-active', tripIsActive);
                liveIndicator.classList.toggle('is-active', tripIsActive);

                if (!locationData.location) {
                    lastLocationTimestamp = null;
                    lastUpdated.textContent = 'Not updated yet';
                    speed.textContent = '--';
                    locationStatus.textContent = tripIsActive
                        ? 'Waiting for the driver’s first location update.'
                        : 'Trip not started. Location will appear when the driver begins the trip.';
                    locationStatus.classList.toggle('is-warning', !tripIsActive);
                    liveIndicator.classList.remove('is-stale');
                    return;
                }

                const updatedAt = new Date(locationData.location.timestamp);
                const updatedAtMs = updatedAt.getTime();
                const isStale = !Number.isFinite(updatedAtMs) || Date.now() - updatedAtMs > 60000;
                lastLocationTimestamp = Number.isFinite(updatedAtMs) ? updatedAtMs : null;
                lastUpdated.textContent = Number.isFinite(updatedAtMs)
                    ? updatedAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
                    : 'Unknown';
                speed.textContent = `${Number(locationData.location.speed || 0).toFixed(0)} km/h`;

                const messages = [];
                if (!tripIsActive) {
                    messages.push('Trip not started.');
                }
                if (isStale) {
                    messages.push('Location is stale; the last update is over 60 seconds old.');
                }
                locationStatus.textContent = messages.join(' ') || 'Bus location is up to date.';
                locationStatus.classList.toggle('is-warning', messages.length > 0);
                liveIndicator.classList.toggle('is-stale', isStale);
            };

            const animateBusTo = (target) => {
                const targetLatLng = L.latLng(target);
                if (!busMarker) {
                    busMarker = L.marker(targetLatLng, {
                        icon: L.divIcon({
                            className: '',
                            html: '<span class="bus-location-marker" aria-hidden="true">🚌</span>',
                            iconSize: [42, 42],
                            iconAnchor: [21, 21]
                        }),
                        zIndexOffset: 1000
                    }).addTo(map);
                    const centerButton = mapLayout?.querySelector('[data-center-bus]');
                    if (centerButton) {
                        centerButton.disabled = false;
                    }
                    return;
                }

                if (busAnimationFrame !== null) {
                    window.cancelAnimationFrame(busAnimationFrame);
                }
                const start = busMarker.getLatLng();
                const startedAt = performance.now();
                const duration = liveCard ? 1200 : 500;
                const animate = (now) => {
                    const progress = Math.min((now - startedAt) / duration, 1);
                    const eased = 1 - ((1 - progress) ** 3);
                    busMarker.setLatLng([
                        start.lat + (targetLatLng.lat - start.lat) * eased,
                        start.lng + (targetLatLng.lng - start.lng) * eased
                    ]);
                    if (progress < 1) {
                        busAnimationFrame = window.requestAnimationFrame(animate);
                    } else {
                        busAnimationFrame = null;
                    }
                };
                busAnimationFrame = window.requestAnimationFrame(animate);
            };

            const refreshBusLocation = async () => {
                if (!element.dataset.locationUrl || locationRequestInProgress) {
                    return;
                }
                locationRequestInProgress = true;
                try {
                    const locationResponse = await fetch(element.dataset.locationUrl, {
                        headers: { Accept: 'application/json' },
                        credentials: 'same-origin'
                    });
                    const locationData = await locationResponse.json();
                    if (!locationResponse.ok) {
                        throw new Error(locationData.detail || 'Location is unavailable.');
                    }
                    if (liveCard) {
                        setStudentLiveStatus(locationData);
                    }
                    if (!locationData.location) {
                        if (!liveCard) {
                            locationStatus.textContent = locationData.trip_status.is_active
                                ? 'Trip active · waiting for the first GPS update.'
                                : 'No bus location has been reported yet.';
                        }
                        return;
                    }

                    const point = [Number(locationData.location.latitude), Number(locationData.location.longitude)];
                    animateBusTo(point);

                    const popup = document.createElement('div');
                    popup.className = 'route-stop-popup';
                    const busName = document.createElement('strong');
                    busName.textContent = locationData.bus_number;
                    const tripState = document.createElement('span');
                    tripState.textContent = `${locationData.driver_name || 'Driver not assigned'} · ${locationData.trip_status.is_active ? 'Trip active' : 'Trip not started'}`;
                    popup.append(busName, tripState);
                    busMarker.bindPopup(popup);

                    const updatedAt = new Date(locationData.location.timestamp).toLocaleTimeString([], {
                        hour: '2-digit', minute: '2-digit', second: '2-digit'
                    });
                    if (!liveCard) {
                        locationStatus.textContent = `${locationData.bus_number} · ${locationData.trip_status.is_active ? 'Trip active' : 'Trip not started'} · Updated ${updatedAt}`;
                    }
                } catch (error) {
                    if (liveCard && lastLocationTimestamp && Date.now() - lastLocationTimestamp > 60000) {
                        locationStatus.textContent = 'Location is stale; the last update is over 60 seconds old.';
                        locationStatus.classList.add('is-warning');
                        liveCard.querySelector('[data-live-indicator]').classList.add('is-stale');
                    } else {
                        locationStatus.textContent = 'Bus location is temporarily unavailable.';
                        locationStatus.classList.add('is-warning');
                    }
                } finally {
                    locationRequestInProgress = false;
                }
            };

            const centerButton = mapLayout?.querySelector('[data-center-bus]');
            if (centerButton) {
                centerButton.addEventListener('click', () => {
                    if (busMarker) {
                        map.flyTo(busMarker.getLatLng(), Math.max(map.getZoom(), 15), { duration: 0.6 });
                    } else {
                        map.fitBounds(bounds, { padding: [28, 28], maxZoom: 15 });
                    }
                });
            }

            const stopLocationPolling = () => {
                if (locationPollTimer !== null) {
                    window.clearInterval(locationPollTimer);
                    locationPollTimer = null;
                }
            };
            const startLocationPolling = () => {
                if (document.hidden || locationPollTimer !== null) {
                    return;
                }
                refreshBusLocation();
                locationPollTimer = window.setInterval(refreshBusLocation, 5000);
                window.requestAnimationFrame(() => map.invalidateSize());
            };
            document.addEventListener('visibilitychange', () => {
                if (document.hidden) {
                    stopLocationPolling();
                } else {
                    startLocationPolling();
                }
            });
            startLocationPolling();

            status.textContent = 'Showing direct route between stops.';
            try {
                const osrmCoordinates = stops
                    .map((stop) => `${Number(stop.longitude)},${Number(stop.latitude)}`)
                    .join(';');
                const controller = new AbortController();
                const timeout = window.setTimeout(() => controller.abort(), 8000);
                const routeResponse = await fetch(
                    `https://router.project-osrm.org/route/v1/driving/${osrmCoordinates}?overview=full&geometries=geojson&steps=false`,
                    { signal: controller.signal }
                );
                window.clearTimeout(timeout);
                if (!routeResponse.ok) {
                    throw new Error(`OSRM request failed (${routeResponse.status}).`);
                }
                const routeData = await routeResponse.json();
                const roadCoordinates = routeData.routes?.[0]?.geometry?.coordinates;
                if (routeData.code !== 'Ok' || !roadCoordinates?.length) {
                    throw new Error('OSRM returned no route geometry.');
                }

                map.removeLayer(routeLine);
                routeLine = L.geoJSON(routeData.routes[0].geometry, {
                    style: { color: '#ed815f', weight: 5, opacity: 0.88 }
                }).addTo(map);
                fitRouteBounds(routeLine.getBounds());
                status.textContent = 'Road route shown via OpenStreetMap routing.';
            } catch (error) {
                status.textContent = 'Road routing unavailable. Showing a direct line between stops.';
            }

            window.requestAnimationFrame(() => map.invalidateSize());
        } catch (error) {
            status.textContent = 'Route stops could not be loaded. Refresh the page to try again.';
        }
    });
})();