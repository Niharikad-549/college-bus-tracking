import json
import math
from urllib.error import URLError
from urllib.request import Request, urlopen

from django.core.cache import cache

from .models import BusLocation


LOCATION_HISTORY_LIMIT = 500
ETA_CACHE_SECONDS = 15
AVERAGE_BUS_SPEED_KMH = 25
EARTH_RADIUS_KM = 6371.0


def record_bus_location(*, bus, latitude, longitude, speed=0):
	location = BusLocation.objects.create(
		bus=bus,
		latitude=latitude,
		longitude=longitude,
		speed=speed,
	)
	old_location_ids = list(
		BusLocation.objects.filter(bus=bus)
		.order_by('-timestamp', '-pk')
		.values_list('pk', flat=True)[LOCATION_HISTORY_LIMIT:]
	)
	if old_location_ids:
		BusLocation.objects.filter(bus=bus, pk__in=old_location_ids).delete()
	return location


def haversine_distance_km(latitude_a, longitude_a, latitude_b, longitude_b):
	latitude_a, longitude_a, latitude_b, longitude_b = map(
		math.radians,
		(float(latitude_a), float(longitude_a), float(latitude_b), float(longitude_b)),
	)
	delta_latitude = latitude_b - latitude_a
	delta_longitude = longitude_b - longitude_a
	a = (
		math.sin(delta_latitude / 2) ** 2
		+ math.cos(latitude_a) * math.cos(latitude_b) * math.sin(delta_longitude / 2) ** 2
	)
	return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def _request_osrm_eta(location, stop):
	coordinates = (
		f'{float(location.longitude)},{float(location.latitude)};'
		f'{float(stop.longitude)},{float(stop.latitude)}'
	)
	url = (
		f'https://router.project-osrm.org/route/v1/driving/{coordinates}'
		'?overview=false&steps=false'
	)
	request = Request(url, headers={'User-Agent': 'CollegeBusTracking/1.0'})
	with urlopen(request, timeout=4) as response:
		payload = json.loads(response.read().decode('utf-8'))
	if payload.get('code') != 'Ok' or not payload.get('routes'):
		raise ValueError('OSRM did not return a route.')
	route = payload['routes'][0]
	return {
		'eta_minutes': max(0, math.ceil(float(route['duration']) / 60)),
		'distance_km': round(float(route['distance']) / 1000, 2),
		'method': 'osrm',
		'used_osrm': True,
	}


def calculate_eta(*, bus, stop, location):
	cache_key = f'bus-eta:v1:{bus.pk}:{stop.pk}'
	cached_result = cache.get(cache_key)
	if cached_result is not None:
		return cached_result

	try:
		result = _request_osrm_eta(location, stop)
	except (OSError, TimeoutError, URLError, ValueError, KeyError, json.JSONDecodeError):
		distance_km = haversine_distance_km(
			location.latitude,
			location.longitude,
			stop.latitude,
			stop.longitude,
		)
		result = {
			'eta_minutes': max(0, math.ceil(distance_km / AVERAGE_BUS_SPEED_KMH * 60)),
			'distance_km': round(distance_km, 2),
			'method': 'haversine',
			'used_osrm': False,
		}

	cache.set(cache_key, result, ETA_CACHE_SECONDS)
	return result