from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.tracking.forms import BusForm, StudentProfileForm, StopForm
from apps.tracking.models import Bus, Route, Stop, StudentProfile, Trip


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
