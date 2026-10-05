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
	return render(request, 'accounts/dashboard_driver.html')


@role_required(User.Role.STUDENT)
def student_dashboard(request):
	return render(request, 'accounts/dashboard_student.html')


@login_required
def home(request):
	dashboard_name = ROLE_DASHBOARDS.get(request.user.role)
	return redirect(dashboard_name or 'login')
