from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import User
from apps.tracking.models import Bus, Route, Stop, StudentProfile, Trip


class Command(BaseCommand):
	help = 'Seed sample buses, routes, stops, drivers, students, and an active trip around Vapi.'

	routes = (
		{
			'name': 'Vapi Station - Chala - Campus',
			'bus_number': 'GJ15-BT-1042',
			'driver': ('vapi_driver_1', 'Arjun Patel', '555-0141'),
			'stops': (
				('Vapi Railway Station', 20.3718, 72.9040),
				('GIDC Char Rasta', 20.3658, 72.9154),
				('Gunjan Circle', 20.3812, 72.9082),
				('Chala Market', 20.3790, 72.9160),
				('Haria Park', 20.3892, 72.9017),
				('College Gate', 20.3920, 72.9140),
			),
			'students': (
				('vapi_student_01', 'Diya Shah', '555-0201', 1),
				('vapi_student_02', 'Rohan Desai', '555-0202', 3),
				('vapi_student_03', 'Meera Joshi', '555-0203', 4),
			),
		},
		{
			'name': 'Dungra - Balitha - Campus',
			'bus_number': 'GJ15-BT-2088',
			'driver': ('vapi_driver_2', 'Kiran Naik', '555-0142'),
			'stops': (
				('Dungra Village', 20.3439, 72.9195),
				('Balitha Check Post', 20.3518, 72.9144),
				('Koparli Road Junction', 20.3597, 72.9066),
				('Vapi Town Hall', 20.3711, 72.9101),
				('Chanod Colony', 20.3801, 72.8979),
				('College Gate', 20.3920, 72.9140),
			),
			'students': (
				('vapi_student_04', 'Aarav Parmar', '555-0204', 1),
				('vapi_student_05', 'Isha Mehta', '555-0205', 2),
				('vapi_student_06', 'Neel Shah', '555-0206', 4),
			),
		},
	)

	def get_or_create_user(self, username, name, phone, role, password):
		user, created = User.objects.get_or_create(
			username=username,
			defaults={'first_name': name, 'phone': phone, 'role': role},
		)
		user.first_name = name
		user.phone = phone
		user.role = role
		if created:
			user.set_password(password)
			user.save()
		else:
			user.save(update_fields=['first_name', 'phone', 'role'])
		return user

	@transaction.atomic
	def handle(self, *args, **options):
		for route_data in self.routes:
			driver_username, driver_name, driver_phone = route_data['driver']
			driver = self.get_or_create_user(
				driver_username,
				driver_name,
				driver_phone,
				User.Role.DRIVER,
				'VapiDriver123!',
			)
			bus, _ = Bus.objects.update_or_create(
				bus_number=route_data['bus_number'],
				defaults={'capacity': 40, 'driver': driver, 'is_active': True},
			)
			route, _ = Route.objects.update_or_create(
				route_name=route_data['name'],
				defaults={'bus': bus},
			)
			stops_by_order = {}
			for order, (name, latitude, longitude) in enumerate(route_data['stops'], start=1):
				stop, _ = Stop.objects.update_or_create(
					route=route,
					stop_order=order,
					defaults={
						'stop_name': name,
						'latitude': latitude,
						'longitude': longitude,
					},
				)
				stops_by_order[order] = stop

			for username, name, phone, pickup_order in route_data['students']:
				student = self.get_or_create_user(
					username,
					name,
					phone,
					User.Role.STUDENT,
					'VapiStudent123!',
				)
				StudentProfile.objects.update_or_create(
					user=student,
					defaults={'route': route, 'pickup_stop': stops_by_order[pickup_order]},
				)

		Trip.objects.get_or_create(bus=Bus.objects.get(bus_number='GJ15-BT-1042'), is_active=True)
		self.stdout.write(self.style.SUCCESS('Vapi demo data is ready: 2 buses, 2 routes, 12 stops, 2 drivers, and 6 students.'))
		self.stdout.write('Driver accounts: vapi_driver_1 / VapiDriver123!, vapi_driver_2 / VapiDriver123!')
		self.stdout.write('Student accounts: vapi_student_01 through vapi_student_06 / VapiStudent123!')