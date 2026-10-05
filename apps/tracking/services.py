from .models import BusLocation


LOCATION_HISTORY_LIMIT = 500


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