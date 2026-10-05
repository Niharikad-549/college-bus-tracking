from decimal import Decimal
from io import StringIO
import json
from math import ceil
from unittest.mock import patch
from urllib.error import URLError

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.tracking.forms import BusForm, StudentProfileForm, StopForm
from apps.tracking.models import Bus, BusLocation, Route, Stop, StudentProfile, Trip
from apps.tracking.services import haversine_distance_km, record_bus_location
from config.views import server_error
from rest_framework.test import APIClient


User = get_user_model()


class AdminManagementTests(TestCase):
	def setUp(self):
		self.admin = User.objects.create_user(username='manager', role=User.Role.ADMIN)
		self.driver = User.objects.create_user(username='manager_driver', role=User.Role.DRIVER)
		self.student = User.objects.create_user(
			username='assigned_student', role=User.Role.STUDENT, first_name='Assigned Student'
		)
		self.unassigned_student = User.objects.create_user(
			username='new_student', role=User.Role.STUDENT, first_name='New Student'
		)
		self.bus = Bus.objects.create(bus_number='TEST-101', capacity=36, driver=self.driver)
		self.route = Route.objects.create(route_name='Test Route', bus=self.bus)
		self.stop = Stop.objects.create(
			route=self.route,
			stop_name='Main Gate',
			latitude=20.371000,
			longitude=72.904800,
			stop_order=1,
		)
		self.profile = StudentProfile.objects.create(user=self.student, route=self.route, pickup_stop=self.stop)
		Trip.objects.create(bus=self.bus, is_active=True)
		self.client.force_login(self.admin)

	def test_dashboard_shows_counts_and_links(self):
		response = self.client.get(reverse('admin_dashboard'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Management dashboard')
		self.assertEqual(response.context['total_buses'], 1)
		self.assertEqual(response.context['total_routes'], 1)
		self.assertEqual(response.context['total_drivers'], 1)
		self.assertEqual(response.context['total_students'], 2)
		self.assertEqual(response.context['active_trips'], 1)
		self.assertContains(response, reverse('admin_live_fleet'))

	def test_health_check_returns_ok(self):
		response = self.client.get(reverse('health_check'))
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json(), {'status': 'ok'})

	def test_route_stops_api_returns_stops_in_order(self):
		second_stop = Stop.objects.create(
			route=self.route,
			stop_name='Library',
			latitude=20.372000,
			longitude=72.906000,
			stop_order=2,
		)
		self.client.logout()

		response = self.client.get(reverse('route_stops_api', args=[self.route.pk]))

		self.assertEqual(response.status_code, 200)
		self.assertEqual([stop['stop_order'] for stop in response.json()], [1, 2])
		self.assertEqual(response.json()[0]['stop_name'], self.stop.stop_name)
		self.assertEqual(response.json()[1]['id'], second_stop.pk)
		self.assertEqual(response.json()[0]['latitude'], '20.371000')

	def test_route_detail_and_student_dashboard_include_route_map(self):
		admin_response = self.client.get(reverse('route_detail', args=[self.route.pk]))
		self.assertEqual(admin_response.status_code, 200)
		self.assertContains(admin_response, 'data-route-map')
		self.assertContains(admin_response, reverse('route_stops_api', args=[self.route.pk]))

		self.client.force_login(self.student)
		student_response = self.client.get(reverse('student_dashboard'))
		self.assertEqual(student_response.status_code, 200)
		self.assertContains(student_response, 'data-route-map')
		self.assertContains(student_response, 'data-live-student="true"')
		self.assertContains(student_response, f'data-pickup-stop-id="{self.stop.pk}"')
		self.assertContains(student_response, 'data-center-bus')
		self.assertContains(student_response, 'data-student-live-card')
		self.assertContains(student_response, reverse('route_stops_api', args=[self.route.pk]))
		self.assertContains(student_response, reverse('api_bus_location', args=[self.bus.pk]))

	def test_lists_and_forms_render_for_each_resource(self):
		for name in ('bus_list', 'route_list', 'stop_list', 'driver_list', 'student_list'):
			with self.subTest(page=name):
				self.assertEqual(self.client.get(reverse(name)).status_code, 200)

		for name in ('bus_add', 'route_add', 'stop_add', 'driver_add', 'student_add'):
			with self.subTest(form=name):
				response = self.client.get(reverse(name))
				self.assertEqual(response.status_code, 200)
				if name == 'stop_add':
					self.assertContains(response, 'stop-map')
					self.assertContains(response, 'leaflet@1.9.4')

	def test_edit_and_delete_pages_render_for_each_resource(self):
		resources = (
			('bus', self.bus.pk, self.bus.pk),
			('route', self.route.pk, self.route.pk),
			('stop', self.stop.pk, self.stop.pk),
			('driver', self.driver.pk, self.driver.pk),
			('student', self.profile.pk, self.student.pk),
		)
		for resource, edit_pk, delete_pk in resources:
			with self.subTest(resource=resource, page='edit'):
				response = self.client.get(reverse(f'{resource}_edit', args=[edit_pk]))
				self.assertEqual(response.status_code, 200)
			with self.subTest(resource=resource, page='delete'):
				response = self.client.get(reverse(f'{resource}_delete', args=[delete_pk]))
				self.assertEqual(response.status_code, 200)

	def test_unassigned_student_can_be_assigned_from_students_list(self):
		response = self.client.get(reverse('student_list'))
		self.assertContains(response, 'new_student')
		assignment_url = reverse('student_assign_user', args=[self.unassigned_student.pk])
		self.assertContains(response, assignment_url)

		response = self.client.post(assignment_url, {
			'route': self.route.pk,
			'pickup_stop': self.stop.pk,
		})
		self.assertRedirects(response, reverse('student_list'))
		self.assertEqual(self.unassigned_student.student_profile.route, self.route)

	def test_non_admin_cannot_open_management_pages(self):
		self.client.force_login(self.driver)
		response = self.client.get(reverse('admin_dashboard'))

		self.assertEqual(response.status_code, 403)
		self.assertContains(response, 'Access denied', status_code=403)

	def test_stop_coordinates_and_order_are_validated(self):
		invalid_coordinates = StopForm(data={
			'route': self.route.pk,
			'stop_name': 'Outside world',
			'latitude': '90.000001',
			'longitude': '72.900000',
			'stop_order': 2,
		})
		self.assertFalse(invalid_coordinates.is_valid())
		self.assertIn('latitude', invalid_coordinates.errors)

		invalid_longitude = StopForm(data={
			'route': self.route.pk,
			'stop_name': 'Outside longitude range',
			'latitude': '20.370000',
			'longitude': '180.000001',
			'stop_order': 2,
		})
		self.assertFalse(invalid_longitude.is_valid())
		self.assertIn('longitude', invalid_longitude.errors)

		duplicate_order = StopForm(data={
			'route': self.route.pk,
			'stop_name': 'Duplicate order',
			'latitude': '20.370000',
			'longitude': '72.905000',
			'stop_order': 1,
		})
		self.assertFalse(duplicate_order.is_valid())
		self.assertIn('stop_order', duplicate_order.errors)

	def test_bus_number_must_be_unique(self):
		form = BusForm(data={
			'bus_number': self.bus.bus_number,
			'capacity': 40,
			'driver': self.driver.pk,
			'is_active': 'on',
		})

		self.assertFalse(form.is_valid())
		self.assertIn('bus_number', form.errors)

	def test_student_pickup_stop_must_match_route(self):
		other_route = Route.objects.create(route_name='Other Route', bus=self.bus)
		form = StudentProfileForm(data={
			'user': self.unassigned_student.pk,
			'route': other_route.pk,
			'pickup_stop': self.stop.pk,
		})

		self.assertFalse(form.is_valid())
		self.assertIn('pickup_stop', form.errors)

	def test_admin_can_create_bus_route_stop_driver_and_student_assignment(self):
		response = self.client.post(reverse('bus_add'), {
			'bus_number': 'TEST-202', 'capacity': 42, 'driver': self.driver.pk, 'is_active': 'on',
		})
		self.assertRedirects(response, reverse('bus_list'))
		new_bus = Bus.objects.get(bus_number='TEST-202')

		response = self.client.post(reverse('route_add'), {
			'route_name': 'New Test Route', 'bus': new_bus.pk,
		})
		self.assertRedirects(response, reverse('route_list'))
		new_route = Route.objects.get(route_name='New Test Route')

		response = self.client.post(reverse('stop_add'), {
			'route': new_route.pk,
			'stop_name': 'Library',
			'latitude': '20.372000',
			'longitude': '72.906000',
			'stop_order': 1,
		})
		self.assertRedirects(response, reverse('stop_list'))
		new_stop = Stop.objects.get(route=new_route, stop_order=1)

		response = self.client.post(reverse('driver_add'), {
			'first_name': 'Sam Driver',
			'username': 'new_driver',
			'phone': '555-0199',
			'password1': 'SafeDriverPassword123!',
			'password2': 'SafeDriverPassword123!',
			'is_active': 'on',
		})
		self.assertRedirects(response, reverse('driver_list'))
		new_driver = User.objects.get(username='new_driver')
		self.assertEqual(new_driver.role, User.Role.DRIVER)
		self.assertTrue(new_driver.check_password('SafeDriverPassword123!'))

		response = self.client.post(reverse('student_add'), {
			'user': self.unassigned_student.pk,
			'route': new_route.pk,
			'pickup_stop': new_stop.pk,
		})
		self.assertRedirects(response, reverse('student_list'))
		self.assertEqual(self.unassigned_student.student_profile.pickup_stop, new_stop)

	def test_bus_can_be_edited_and_deleted(self):
		response = self.client.post(reverse('bus_edit', args=[self.bus.pk]), {
			'bus_number': 'TEST-UPDATED', 'capacity': 38, 'driver': self.driver.pk, 'is_active': 'on',
		})
		self.assertRedirects(response, reverse('bus_list'))
		self.assertTrue(Bus.objects.filter(pk=self.bus.pk, bus_number='TEST-UPDATED').exists())

		response = self.client.get(reverse('bus_delete', args=[self.bus.pk]))
		self.assertEqual(response.status_code, 200)
		response = self.client.post(reverse('bus_delete', args=[self.bus.pk]))
		self.assertRedirects(response, reverse('bus_list'))
		self.assertFalse(Bus.objects.filter(pk=self.bus.pk).exists())

	def test_demo_seed_is_repeatable(self):
		call_command('seed_demo_data', stdout=StringIO())
		call_command('seed_demo_data', stdout=StringIO())

		self.assertEqual(Bus.objects.filter(bus_number__startswith='GJ15-BT-').count(), 2)
		self.assertEqual(Route.objects.filter(route_name__contains='Campus').count(), 2)
		self.assertEqual(Stop.objects.filter(route__route_name__contains='Campus').count(), 12)
		self.assertEqual(User.objects.filter(username__startswith='vapi_driver_').count(), 2)
		self.assertEqual(User.objects.filter(username__startswith='vapi_student_').count(), 6)
		self.assertEqual(Trip.objects.filter(bus__bus_number='GJ15-BT-1042', is_active=True).count(), 1)


class DriverLocationApiTests(TestCase):
	def setUp(self):
		cache.clear()
		self.driver = User.objects.create_user(
			username='api_driver', password='DriverPassword123!', role=User.Role.DRIVER
		)
		self.other_driver = User.objects.create_user(
			username='other_driver', password='DriverPassword123!', role=User.Role.DRIVER
		)
		self.student = User.objects.create_user(
			username='api_student', password='StudentPassword123!', role=User.Role.STUDENT
		)
		self.other_student = User.objects.create_user(
			username='other_student', password='StudentPassword123!', role=User.Role.STUDENT
		)
		self.admin = User.objects.create_user(
			username='api_admin', password='AdminPassword123!', role=User.Role.ADMIN
		)
		self.bus = Bus.objects.create(bus_number='API-101', capacity=32, driver=self.driver)
		self.other_bus = Bus.objects.create(bus_number='API-202', capacity=32, driver=self.other_driver)
		self.route = Route.objects.create(route_name='API Route', bus=self.bus)
		self.stop = Stop.objects.create(
			route=self.route,
			stop_name='API Stop',
			latitude=20.371000,
			longitude=72.904000,
			stop_order=1,
		)
		StudentProfile.objects.create(user=self.student, route=self.route, pickup_stop=self.stop)
		self.client = APIClient()

	def login_as(self, user):
		self.assertTrue(self.client.login(username=user.username, password='DriverPassword123!' if user.role == User.Role.DRIVER else f'{user.role.title()}Password123!'))

	def post_json(self, name, payload=None):
		return self.client.post(reverse(name), payload or {}, format='json')

	def test_driver_can_start_only_one_active_trip_and_then_stop_it(self):
		self.login_as(self.driver)
		response = self.post_json('api_trip_start', {'bus_id': self.bus.pk})
		self.assertEqual(response.status_code, 201)
		trip_id = response.json()['id']

		duplicate = self.post_json('api_trip_start', {'bus_id': self.bus.pk})
		self.assertEqual(duplicate.status_code, 409)
		self.assertEqual(Trip.objects.filter(bus=self.bus, is_active=True).count(), 1)

		stopped = self.post_json('api_trip_stop', {'bus_id': self.bus.pk})
		self.assertEqual(stopped.status_code, 200)
		trip = Trip.objects.get(pk=trip_id)
		self.assertFalse(trip.is_active)
		self.assertIsNotNone(trip.ended_at)
		self.assertEqual(self.post_json('api_trip_stop', {'bus_id': self.bus.pk}).status_code, 409)

	def test_driver_dashboard_shows_assigned_bus_route_and_trip_controls(self):
		Trip.objects.create(bus=self.bus, is_active=True)
		self.login_as(self.driver)

		response = self.client.get(reverse('driver_dashboard'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, self.bus.bus_number)
		self.assertContains(response, self.route.route_name)
		self.assertContains(response, 'data-start-trip')
		self.assertContains(response, 'data-stop-trip')
		self.assertContains(response, 'data-location-url')

	def test_trip_and_location_posts_require_a_driver_and_assigned_bus(self):
		self.login_as(self.student)
		self.assertEqual(self.post_json('api_trip_start').status_code, 403)
		self.assertEqual(self.post_json('api_driver_location', {
			'latitude': 20.371, 'longitude': 72.904,
		}).status_code, 403)

		self.login_as(self.other_driver)
		self.assertEqual(self.post_json('api_trip_start', {'bus_id': self.bus.pk}).status_code, 404)
		self.assertEqual(self.post_json('api_driver_location', {
			'bus_id': self.bus.pk, 'latitude': 20.371, 'longitude': 72.904,
		}).status_code, 409)

		self.client.logout()
		self.assertEqual(self.post_json('api_trip_start', {'bus_id': self.bus.pk}).status_code, 403)

	def test_location_requires_an_active_trip_and_valid_coordinates_and_speed(self):
		self.login_as(self.driver)
		valid_location = {'latitude': 20.371, 'longitude': 72.904, 'speed': 12.5}
		self.assertEqual(self.post_json('api_driver_location', valid_location).status_code, 409)
		self.post_json('api_trip_start', {'bus_id': self.bus.pk})

		for invalid in (
			{'latitude': 90.1, 'longitude': 72.904},
			{'latitude': 20.371, 'longitude': -180.1},
			{'latitude': 20.371, 'longitude': 72.904, 'speed': -1},
			{'latitude': 20.371, 'longitude': 72.904, 'speed': 301},
		):
			with self.subTest(payload=invalid):
				response = self.post_json('api_driver_location', invalid)
				self.assertEqual(response.status_code, 400)

		response = self.post_json('api_driver_location', valid_location)
		self.assertEqual(response.status_code, 201)
		location = BusLocation.objects.get(bus=self.bus)
		self.assertEqual(location.latitude, Decimal('20.371000'))
		self.assertEqual(location.speed, Decimal('12.50'))

	def test_bus_location_is_visible_only_to_admin_driver_or_assigned_student(self):
		location = record_bus_location(bus=self.bus, latitude=20.371, longitude=72.904, speed=0)
		url = reverse('api_bus_location', args=[self.bus.pk])

		for user in (self.driver, self.student, self.admin):
			with self.subTest(user=user.username):
				self.login_as(user)
				response = self.client.get(url)
				self.assertEqual(response.status_code, 200)
				self.assertEqual(response.json()['location']['id'], location.pk)
				self.assertEqual(response.json()['driver_name'], self.driver.username)
				self.assertFalse(response.json()['trip_status']['is_active'])

		self.login_as(self.other_student)
		self.assertEqual(self.client.get(url).status_code, 403)

	def test_bus_location_reports_active_trip_status(self):
		Trip.objects.create(bus=self.bus, is_active=True)
		record_bus_location(bus=self.bus, latitude=20.371, longitude=72.904, speed=0)
		latest = record_bus_location(bus=self.bus, latitude=20.372, longitude=72.905, speed=0)
		tied_timestamp = timezone.now()
		BusLocation.objects.filter(bus=self.bus).update(timestamp=tied_timestamp)
		self.login_as(self.student)

		response = self.client.get(reverse('api_bus_location', args=[self.bus.pk]))

		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.json()['trip_status']['is_active'])
		self.assertEqual(response.json()['location']['id'], latest.pk)

	def test_eta_uses_haversine_fallback_when_osrm_fails(self):
		location = record_bus_location(bus=self.bus, latitude=20.35, longitude=72.91, speed=0)
		self.login_as(self.student)
		with patch('apps.tracking.services.urlopen', side_effect=URLError('OSRM unavailable')):
			response = self.client.get(reverse('api_bus_eta', args=[self.bus.pk]), {'stop_id': self.stop.pk})

		self.assertEqual(response.status_code, 200)
		result = response.json()
		distance = haversine_distance_km(
			location.latitude,
			location.longitude,
			self.stop.latitude,
			self.stop.longitude,
		)
		self.assertEqual(result['method'], 'haversine')
		self.assertFalse(result['used_osrm'])
		self.assertEqual(result['distance_km'], round(distance, 2))
		self.assertEqual(result['eta_minutes'], ceil(distance / 25 * 60))
		self.assertEqual(result['arrival_state'], 'trip_not_started')

	def test_eta_caches_successful_osrm_result_for_repeated_requests(self):
		record_bus_location(bus=self.bus, latitude=20.35, longitude=72.91, speed=0)
		self.login_as(self.student)
		response_data = {'code': 'Ok', 'routes': [{'duration': 300, 'distance': 2500}]}
		with patch('apps.tracking.services.urlopen') as mocked_urlopen:
			mocked_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(response_data).encode()
			first = self.client.get(reverse('api_bus_eta', args=[self.bus.pk]), {'stop_id': self.stop.pk})
			second = self.client.get(reverse('api_bus_eta', args=[self.bus.pk]), {'stop_id': self.stop.pk})

		self.assertEqual(first.status_code, 200)
		self.assertEqual(second.status_code, 200)
		self.assertEqual(mocked_urlopen.call_count, 1)
		self.assertEqual(first.json()['eta_minutes'], 5)
		self.assertEqual(first.json()['distance_km'], 2.5)
		self.assertEqual(first.json()['method'], 'osrm')
		self.assertTrue(first.json()['used_osrm'])

	def test_eta_requires_access_to_the_bus_and_stop(self):
		url = reverse('api_bus_eta', args=[self.bus.pk])
		self.login_as(self.other_student)
		self.assertEqual(self.client.get(url, {'stop_id': self.stop.pk}).status_code, 403)

		self.login_as(self.student)
		self.assertEqual(self.client.get(url).status_code, 400)
		self.assertEqual(self.client.get(url, {'stop_id': 99999}).status_code, 404)

		other_route = Route.objects.create(route_name='Other API Route', bus=self.bus)
		other_stop = Stop.objects.create(
			route=other_route,
			stop_name='Other Pickup',
			latitude=20.38,
			longitude=72.91,
			stop_order=1,
		)
		self.assertEqual(self.client.get(url, {'stop_id': other_stop.pk}).status_code, 403)

	def test_eta_rejects_malformed_stop_id(self):
		self.login_as(self.student)
		response = self.client.get(reverse('api_bus_eta', args=[self.bus.pk]), {'stop_id': 'not-a-number'})
		self.assertEqual(response.status_code, 400)

	def test_eta_reports_arriving_and_passed_stop_states(self):
		Trip.objects.create(bus=self.bus, is_active=True)
		self.login_as(self.student)
		with patch('apps.tracking.services._request_osrm_eta', return_value={
			'eta_minutes': 0, 'distance_km': 0.0, 'method': 'osrm', 'used_osrm': True,
		}):
			record_bus_location(
				bus=self.bus,
				latitude=self.stop.latitude,
				longitude=self.stop.longitude,
				speed=0,
			)
			arriving = self.client.get(
				reverse('api_bus_eta', args=[self.bus.pk]),
				{'stop_id': self.stop.pk},
			)
			self.assertEqual(arriving.status_code, 200)
			self.assertEqual(arriving.json()['arrival_state'], 'arriving_now')

			later_stop = Stop.objects.create(
				route=self.route,
				stop_name='Later Stop',
				latitude=20.3735,
				longitude=72.904,
				stop_order=2,
			)
			record_bus_location(
				bus=self.bus,
				latitude=later_stop.latitude,
				longitude=later_stop.longitude,
				speed=0,
			)
			passed = self.client.get(
				reverse('api_bus_eta', args=[self.bus.pk]),
				{'stop_id': self.stop.pk},
			)
			self.assertEqual(passed.status_code, 200)
			self.assertEqual(passed.json()['arrival_state'], 'passed_stop')

	@override_settings(REST_FRAMEWORK={
		'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework.authentication.SessionAuthentication'],
		'DEFAULT_THROTTLE_RATES': {'driver_location': '1/minute'},
	})
	def test_driver_location_endpoint_is_throttled(self):
		cache.clear()
		Trip.objects.create(bus=self.bus, is_active=True)
		self.login_as(self.driver)
		payload = {'latitude': 20.371, 'longitude': 72.904}

		first = self.post_json('api_driver_location', payload)
		second = self.post_json('api_driver_location', payload)

		self.assertEqual(first.status_code, 201)
		self.assertEqual(second.status_code, 429)

	def test_driver_location_endpoint_enforces_csrf(self):
		csrf_client = APIClient(enforce_csrf_checks=True)
		self.assertTrue(csrf_client.login(
			username=self.driver.username,
			password='DriverPassword123!',
		))

		response = csrf_client.post(reverse('api_trip_start'), {'bus_id': self.bus.pk}, format='json')

		self.assertEqual(response.status_code, 403)

	def test_active_buses_feed_is_admin_only(self):
		Trip.objects.create(bus=self.bus, is_active=True)
		record_bus_location(bus=self.bus, latitude=20.371, longitude=72.904, speed=0)
		url = reverse('api_active_buses')

		self.login_as(self.student)
		self.assertEqual(self.client.get(url).status_code, 403)

		self.login_as(self.admin)
		response = self.client.get(url)
		self.assertEqual(response.status_code, 200)
		self.assertEqual(len(response.json()['buses']), 1)
		self.assertEqual(response.json()['buses'][0]['bus_number'], self.bus.bus_number)

		page = self.client.get(reverse('admin_live_fleet'))
		self.assertEqual(page.status_code, 200)
		self.assertContains(page, 'data-active-fleet')

	@override_settings(DEBUG=False)
	def test_custom_404_page_renders(self):
		response = self.client.get('/this-page-does-not-exist/')
		self.assertEqual(response.status_code, 404)
		self.assertContains(response, 'This page isn’t on the route.', status_code=404)

	def test_custom_500_page_renders(self):
		response = server_error(RequestFactory().get('/'))
		self.assertEqual(response.status_code, 500)
		self.assertContains(response, 'We couldn’t load this page.', status_code=500)

	def test_location_history_keeps_only_the_latest_500_per_bus(self):
		old_locations = BusLocation.objects.bulk_create([
			BusLocation(bus=self.bus, latitude=20, longitude=72, speed=0)
			for _ in range(500)
		])
		newest = record_bus_location(bus=self.bus, latitude=21, longitude=73, speed=1)

		self.assertEqual(BusLocation.objects.filter(bus=self.bus).count(), 500)
		self.assertFalse(BusLocation.objects.filter(pk=old_locations[0].pk).exists())
		self.assertTrue(BusLocation.objects.filter(pk=newest.pk).exists())
		self.assertEqual(BusLocation.objects.filter(bus=self.other_bus).count(), 0)

	def test_simulator_writes_location_and_starts_trip(self):
		call_command('simulate_bus', route_id=self.route.pk, once=True, stdout=StringIO())

		self.assertTrue(Trip.objects.filter(bus=self.bus, is_active=True).exists())
		self.assertEqual(BusLocation.objects.filter(bus=self.bus).count(), 1)
		location = BusLocation.objects.get(bus=self.bus)
		self.assertEqual(location.latitude, Decimal(str(self.stop.latitude)))
		self.assertEqual(location.longitude, Decimal(str(self.stop.longitude)))
