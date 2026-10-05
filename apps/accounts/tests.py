from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class AuthenticationFlowTests(TestCase):
	def setUp(self):
		self.users = {
			role: User.objects.create_user(
				username=f'test_{role}',
				password='SafeTestPassword123!',
				role=role,
			)
			for role in (User.Role.ADMIN, User.Role.DRIVER, User.Role.STUDENT)
		}
		self.dashboard_urls = {
			User.Role.ADMIN: ('admin_dashboard', '/dashboard/admin/'),
			User.Role.DRIVER: ('driver_dashboard', '/dashboard/driver/'),
			User.Role.STUDENT: ('student_dashboard', '/dashboard/student/'),
		}

	def test_login_redirects_each_role_to_its_dashboard(self):
		for role, user in self.users.items():
			with self.subTest(role=role):
				response = self.client.post(
					reverse('login'),
					{'username': user.username, 'password': 'SafeTestPassword123!'},
				)
				self.assertRedirects(
					response,
					self.dashboard_urls[role][1],
					fetch_redirect_response=False,
				)
				self.client.logout()

	def test_dashboards_require_login_and_the_matching_role(self):
		for role, (route_name, _) in self.dashboard_urls.items():
			with self.subTest(role=role, case='anonymous'):
				response = self.client.get(reverse(route_name))
				self.assertRedirects(
					response,
					f'{reverse("login")}?next={reverse(route_name)}',
					fetch_redirect_response=False,
				)

			for user_role, user in self.users.items():
				self.client.force_login(user)
				response = self.client.get(reverse(route_name))
				if role == user_role:
					self.assertEqual(response.status_code, 200)
				else:
					self.assertEqual(response.status_code, 403)
					self.assertContains(response, 'Access denied', status_code=403)
				self.client.logout()

	def test_registration_always_creates_a_student(self):
		response = self.client.post(
			reverse('register'),
			{
				'name': 'Taylor Student',
				'username': 'taylor',
				'phone': '555-0101',
				'password1': 'SafeStudentPassword123!',
				'password2': 'SafeStudentPassword123!',
			},
		)

		self.assertRedirects(response, reverse('login'), fetch_redirect_response=False)
		student = User.objects.get(username='taylor')
		self.assertEqual(student.role, User.Role.STUDENT)
		self.assertEqual(student.first_name, 'Taylor Student')
		self.assertEqual(student.phone, '555-0101')

	def test_logout_ends_the_session(self):
		self.client.force_login(self.users[User.Role.STUDENT])
		response = self.client.post(reverse('logout'))

		self.assertRedirects(response, reverse('login'), fetch_redirect_response=False)
		self.assertNotIn('_auth_user_id', self.client.session)
