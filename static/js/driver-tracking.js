(() => {
    const panel = document.querySelector('[data-driver-trip-panel]');
    if (!panel) {
        return;
    }

    const startButton = panel.querySelector('[data-start-trip]');
    const stopButton = panel.querySelector('[data-stop-trip]');
    const retryButton = panel.querySelector('[data-retry-gps]');
    const tripStatus = panel.querySelector('[data-trip-status]');
    const tripDot = panel.querySelector('[data-trip-dot]');
    const gpsStatus = panel.querySelector('[data-gps-status]');
    const coordinates = panel.querySelector('[data-coordinates]');
    const lastSent = panel.querySelector('[data-last-sent]');
    const networkMessage = panel.querySelector('[data-network-message]');
    const busSelect = panel.querySelector('[data-bus-select]');

    let busId = Number(panel.dataset.busId);
    let tripActive = panel.dataset.isActive === 'true';
    let watchId = null;
    let sendTimer = null;
    let currentPosition = null;
    let sending = false;
    let stopInProgress = false;

    const readCookie = (name) => {
        const cookie = document.cookie.split('; ').find((item) => item.startsWith(`${name}=`));
        return cookie ? decodeURIComponent(cookie.split('=').slice(1).join('=')) : '';
    };

    const setTripUi = (active) => {
        tripActive = active;
        startButton.hidden = active;
        stopButton.hidden = !active;
        tripStatus.textContent = active ? 'Trip active' : 'Ready to start';
        tripDot.classList.toggle('is-active', active);
        if (!active) {
            gpsStatus.textContent = 'Not sharing';
        }
    };

    const stopSending = () => {
        if (sendTimer !== null) {
            window.clearInterval(sendTimer);
            sendTimer = null;
        }
    };

    const stopGpsWatch = () => {
        stopSending();
        if (watchId !== null && navigator.geolocation) {
            navigator.geolocation.clearWatch(watchId);
            watchId = null;
        }
        currentPosition = null;
    };

    const startSendTimer = () => {
        stopSending();
        sendTimer = window.setInterval(sendCurrentLocation, 5000);
    };

    async function sendCurrentLocation() {
        if (!tripActive || stopInProgress || !currentPosition || sending) {
            return;
        }

        sending = true;
        gpsStatus.textContent = 'Sending';
        try {
            const response = await fetch(panel.dataset.locationUrl, {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    Accept: 'application/json',
                    'Content-Type': 'application/json',
                    'X-CSRFToken': readCookie('csrftoken')
                },
                body: JSON.stringify({
                    bus_id: busId,
                    latitude: currentPosition.latitude,
                    longitude: currentPosition.longitude,
                    speed: currentPosition.speed
                })
            });
            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.detail || 'Location update was rejected.');
            }

            lastSent.textContent = new Date().toLocaleTimeString([], {
                hour: '2-digit', minute: '2-digit', second: '2-digit'
            });
            networkMessage.textContent = '';
        } catch (error) {
            gpsStatus.textContent = 'Network error';
            networkMessage.textContent = `${error.message} Retrying automatically in 5 seconds.`;
        } finally {
            sending = false;
        }
    }

    const handlePosition = (position) => {
        currentPosition = {
            latitude: Number(position.coords.latitude.toFixed(6)),
            longitude: Number(position.coords.longitude.toFixed(6)),
            speed: Number(((position.coords.speed || 0) * 3.6).toFixed(2))
        };
        coordinates.textContent = `${currentPosition.latitude.toFixed(6)}, ${currentPosition.longitude.toFixed(6)}`;
        retryButton.hidden = true;
        networkMessage.textContent = '';
        if (tripActive && !stopInProgress) {
            gpsStatus.textContent = 'Sending';
            if (sendTimer === null) {
                startSendTimer();
                sendCurrentLocation();
            }
        }
    };

    const handlePositionError = (error) => {
        stopSending();
        currentPosition = null;
        retryButton.hidden = false;
        if (error.code === error.PERMISSION_DENIED) {
            gpsStatus.textContent = 'Permission denied';
            networkMessage.textContent = 'Allow location access in your browser settings, then try GPS again.';
        } else {
            gpsStatus.textContent = 'GPS error';
            networkMessage.textContent = error.message || 'GPS could not determine your position. Try again.';
        }
    };

    const startGpsWatch = () => {
        if (!navigator.geolocation) {
            gpsStatus.textContent = 'GPS error';
            networkMessage.textContent = 'This browser does not support location services.';
            retryButton.hidden = false;
            return;
        }
        if (watchId !== null) {
            navigator.geolocation.clearWatch(watchId);
        }
        gpsStatus.textContent = 'Waiting for GPS…';
        networkMessage.textContent = '';
        watchId = navigator.geolocation.watchPosition(
            handlePosition,
            handlePositionError,
            { enableHighAccuracy: true, maximumAge: 3000, timeout: 20000 }
        );
    };

    const postTripAction = async (url) => {
        const response = await fetch(url, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                Accept: 'application/json',
                'Content-Type': 'application/json',
                'X-CSRFToken': readCookie('csrftoken')
            },
            body: JSON.stringify({ bus_id: busId })
        });
        const result = await response.json();
        if (!response.ok) {
            throw new Error(result.detail || 'Trip request failed.');
        }
        return result;
    };

    startButton.addEventListener('click', async () => {
        startButton.disabled = true;
        networkMessage.textContent = '';
        try {
            await postTripAction(panel.dataset.startUrl);
            setTripUi(true);
            startGpsWatch();
        } catch (error) {
            networkMessage.textContent = error.message;
        } finally {
            startButton.disabled = false;
        }
    });

    stopButton.addEventListener('click', async () => {
        stopButton.disabled = true;
        stopInProgress = true;
        stopSending();
        tripStatus.textContent = 'Stopping trip…';
        networkMessage.textContent = '';
        try {
            await postTripAction(panel.dataset.stopUrl);
            stopInProgress = false;
            stopGpsWatch();
            setTripUi(false);
            coordinates.textContent = 'Trip stopped';
            retryButton.hidden = true;
        } catch (error) {
            stopInProgress = false;
            tripStatus.textContent = 'Trip still active';
            networkMessage.textContent = `${error.message} Location sharing will resume.`;
            if (tripActive) {
                startSendTimer();
            }
        } finally {
            stopButton.disabled = false;
        }
    });

    retryButton.addEventListener('click', startGpsWatch);
    if (busSelect) {
        busSelect.addEventListener('change', () => {
            const url = new URL(window.location.href);
            url.searchParams.set('bus_id', busSelect.value);
            window.location.assign(url);
        });
    }

    setTripUi(tripActive);
    if (tripActive) {
        startGpsWatch();
    }
})();