import time

from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError

from apps.tracking.models import Route, Trip
from apps.tracking.services import record_bus_location


class Command(BaseCommand):
	help = 'Simulate a moving bus along a route, writing a location at each stop.'

	def add_arguments(self, parser):
		parser.add_argument('--route-id', type=int, help='Route to simulate (defaults to the first route).')
		parser.add_argument('--interval', type=float, default=5, help='Seconds between stop locations (default: 5).')
		parser.add_argument('--once', action='store_true', help='Write one location at the first stop and exit.')

	def handle(self, *args, **options):
		if options['interval'] <= 0:
			raise CommandError('--interval must be greater than zero.')

		routes = Route.objects.select_related('bus').prefetch_related('stops')
		if options['route_id']:
			route = routes.filter(pk=options['route_id']).first()
		else:
			route = routes.order_by('pk').first()
		if route is None:
			raise CommandError('No matching route was found. Run seed_demo_data first.')

		stops = list(route.stops.order_by('stop_order'))
		if not stops:
			raise CommandError(f'Route "{route.route_name}" has no stops to simulate.')

		try:
			Trip.objects.get_or_create(bus=route.bus, is_active=True)
		except IntegrityError as error:
			raise CommandError('The bus already has conflicting active trips.') from error

		self.stdout.write(self.style.SUCCESS(
			f'Simulating {route.bus.bus_number} on {route.route_name}. Press Ctrl+C to stop.'
		))
		while True:
			for stop in stops:
				location = record_bus_location(
					bus=route.bus,
					latitude=stop.latitude,
					longitude=stop.longitude,
					speed=0,
				)
				self.stdout.write(
					f'{stop.stop_order}. {stop.stop_name}: {location.latitude}, {location.longitude}'
				)
				if options['once']:
					return
				time.sleep(options['interval'])