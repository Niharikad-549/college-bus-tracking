from functools import wraps

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import StudentRegistrationForm
from .models import User
from apps.tracking.models import Bus, StudentProfile, Trip


ROLE_DASHBOARDS = {
	User.Role.ADMIN: 'admin_dashboard',
	User.Role.DRIVER: 'driver_dashboard',
	User.Role.STUDENT: 'student_dashboard',
}


class RoleLoginView(LoginView):
	template_name = 'accounts/login.html'
	redirect_authenticated_user = True

	def get_success_url(self):
		dashboard_name = ROLE_DASHBOARDS.get(self.request.user.role)
		return reverse(dashboard_name or 'login')


def role_required(required_role):
	def decorator(view_func):
		@wraps(view_func)
		@login_required
		def wrapped_view(request, *args, **kwargs):
			if request.user.role != required_role:
				return render(request, 'accounts/access_denied.html', status=403)
			return view_func(request, *args, **kwargs)

		return wrapped_view

	return decorator


def register_student(request):
	if request.method == 'POST':
		form = StudentRegistrationForm(request.POST)
		if form.is_valid():
			form.save()
			messages.success(request, 'Your student account is ready. Please sign in.')
			return redirect('login')
	else:
		form = StudentRegistrationForm()

	return render(request, 'accounts/register.html', {'form': form})


@require_POST
@login_required
def logout_view(request):
	logout(request)
	return redirect('login')


@role_required(User.Role.DRIVER)
def driver_dashboard(request):
	assigned_buses = list(
		Bus.objects.filter(driver=request.user).prefetch_related('routes').order_by('bus_number')
	)
	active_trip = Trip.objects.filter(
		bus__driver=request.user,
		is_active=True,
	).select_related('bus').first()
	requested_bus_id = request.GET.get('bus_id')
	driver_bus = next(
		(bus for bus in assigned_buses if str(bus.pk) == requested_bus_id),
		None,
	)
	if driver_bus is None:
		driver_bus = active_trip.bus if active_trip else (assigned_buses[0] if assigned_buses else None)
	active_trip = Trip.objects.filter(bus=driver_bus, is_active=True).first() if driver_bus else None
	driver_route = driver_bus.routes.order_by('pk').first() if driver_bus else None
	return render(request, 'accounts/dashboard_driver.html', {
		'assigned_buses': assigned_buses,
		'driver_bus': driver_bus,
		'driver_route': driver_route,
		'active_trip': active_trip,
	})


@role_required(User.Role.STUDENT)
def student_dashboard(request):
	try:
		student_route = request.user.student_profile.route
	except StudentProfile.DoesNotExist:
		student_route = None
	return render(request, 'accounts/dashboard_student.html', {'student_route': student_route})


@login_required
def home(request):
	dashboard_name = ROLE_DASHBOARDS.get(request.user.role)
	return redirect(dashboard_name or 'login')
