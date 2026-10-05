(() => {
    const mapElements = document.querySelectorAll('[data-route-map]');

    mapElements.forEach(async (element) => {
        const status = element.querySelector('[data-map-status]');
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

            stops.forEach((stop, index) => {
                const marker = L.marker(coordinates[index], {
                    icon: L.divIcon({
                        className: '',
                        html: `<span class="route-stop-marker">${index + 1}</span>`,
                        iconSize: [28, 28],
                        iconAnchor: [14, 14]
                    })
                });

                const popup = document.createElement('div');
                popup.className = 'route-stop-popup';
                const name = document.createElement('strong');
                name.textContent = stop.stop_name;
                const order = document.createElement('span');
                order.textContent = `Stop ${stop.stop_order}`;
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
            map.fitBounds(bounds, { padding: [28, 28], maxZoom: 15 });
            if (coordinates.length === 1) {
                map.setView(coordinates[0], 14);
            }

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
                map.fitBounds(bounds.extend(routeLine.getBounds()), { padding: [28, 28], maxZoom: 15 });
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