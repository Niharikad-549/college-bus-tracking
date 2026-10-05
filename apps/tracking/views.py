from django.contrib import messages
from django.contrib.messages.views import SuccessMessageMixin as MessagesSuccessMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.accounts.models import User
from apps.accounts.views import role_required

from .forms import BusForm, DriverForm, RouteForm, StopForm, StudentAssignmentForm, StudentProfileForm
from .models import Bus, Route, Stop, StudentProfile, Trip
from .serializers import StopSerializer


class AdminRequiredMixin:
	@method_decorator(role_required(User.Role.ADMIN))
	def dispatch(self, request, *args, **kwargs):
		return super().dispatch(request, *args, **kwargs)


class AdminDashboardView(AdminRequiredMixin, TemplateView):
	template_name = 'tracking/admin/dashboard.html'

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context.update({
			'total_buses': Bus.objects.count(),
			'total_routes': Route.objects.count(),
			'total_drivers': User.objects.filter(role=User.Role.DRIVER).count(),
			'total_students': User.objects.filter(role=User.Role.STUDENT).count(),
			'active_trips': Trip.objects.filter(is_active=True).count(),
		})
		return context


class AdminLiveFleetView(AdminRequiredMixin, TemplateView):
	template_name = 'tracking/admin/live_fleet.html'


class AdminListView(AdminRequiredMixin, ListView):
	template_name = 'tracking/admin/object_list.html'
	paginate_by = 25
	page_title = ''
	add_url_name = ''
	edit_url_name = ''
	delete_url_name = ''
	search_fields = ()
	columns = ()

	def get_queryset(self):
		queryset = super().get_queryset()
		if not self.model._meta.ordering:
			queryset = queryset.order_by('pk')
		query = self.request.GET.get('q', '').strip()
		if query and self.search_fields:
			search = Q()
			for field in self.search_fields:
				search |= Q(**{f'{field}__icontains': query})
			queryset = queryset.filter(search)
		return queryset

	def display_value(self, obj, accessor):
		value = obj
		for part in accessor.split('__'):
			try:
				value = getattr(value, part)
			except AttributeError:
				return 'Not assigned'
			if value is None:
				return 'Not assigned'
		if isinstance(value, bool):
			return 'Active' if value else 'Inactive'
		return str(value)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		objects = context.get('page_obj', self.object_list)
		context.update({
			'page_title': self.page_title,
			'add_url': reverse(self.add_url_name),
			'headers': [header for header, _ in self.columns],
			'rows': [
				{
					'values': [self.display_value(obj, accessor) for _, accessor in self.columns],
					'edit_url': self.get_edit_url(obj),
					'delete_url': self.get_delete_url(obj),
					'detail_url': self.get_detail_url(obj),
				}
				for obj in objects
			],
		})
		return context

	def get_edit_url(self, obj):
		return reverse(self.edit_url_name, args=[obj.pk])

	def get_delete_url(self, obj):
		return reverse(self.delete_url_name, args=[obj.pk])

	def get_detail_url(self, obj):
		return None


class AdminFormViewMixin(AdminRequiredMixin, MessagesSuccessMixin):
	template_name = 'tracking/admin/object_form.html'
	form_title = ''
	list_url_name = ''
	success_message = 'Changes saved.'

	def get_success_url(self):
		return reverse(self.list_url_name)

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context.update({'form_title': self.form_title, 'list_url': reverse(self.list_url_name)})
		context['is_stop_form'] = isinstance(self.get_form_class(), type) and issubclass(self.get_form_class(), StopForm)
		return context


class AdminDeleteView(AdminRequiredMixin, DeleteView):
	template_name = 'tracking/admin/confirm_delete.html'
	page_title = ''
	list_url_name = ''
	success_message = 'Item deleted.'

	def get_context_data(self, **kwargs):
		context = super().get_context_data(**kwargs)
		context.update({'page_title': self.page_title, 'list_url': reverse(self.list_url_name)})
		return context

	def get_success_url(self):
		return reverse(self.list_url_name)

	def form_valid(self, form):
		messages.success(self.request, self.success_message)
		return super().form_valid(form)


class BusListView(AdminListView):
	model = Bus
	page_title = 'Buses'
	item_label = 'bus'
	add_url_name = 'bus_add'
	edit_url_name = 'bus_edit'
	delete_url_name = 'bus_delete'
	search_fields = ('bus_number', 'driver__username', 'driver__first_name')
	columns = (('Bus number', 'bus_number'), ('Capacity', 'capacity'), ('Driver', 'driver'), ('Status', 'is_active'))

	def get_queryset(self):
		return super().get_queryset().select_related('driver')


class BusCreateView(AdminFormViewMixin, CreateView):
	model = Bus
	form_class = BusForm
	form_title = 'Add bus'
	list_url_name = 'bus_list'
	success_message = 'Bus created successfully.'


class BusUpdateView(AdminFormViewMixin, UpdateView):
	model = Bus
	form_class = BusForm
	form_title = 'Edit bus'
	list_url_name = 'bus_list'
	success_message = 'Bus updated successfully.'


class BusDeleteView(AdminDeleteView):
	model = Bus
	page_title = 'Delete bus'
	list_url_name = 'bus_list'
	success_message = 'Bus deleted successfully.'


class RouteListView(AdminListView):
	model = Route
	page_title = 'Routes'
	item_label = 'route'
	add_url_name = 'route_add'
	edit_url_name = 'route_edit'
	delete_url_name = 'route_delete'
	search_fields = ('route_name', 'bus__bus_number')
	columns = (('Route', 'route_name'), ('Assigned bus', 'bus'))

	def get_queryset(self):
		return super().get_queryset().select_related('bus')

	def get_detail_url(self, obj):
		return reverse('route_detail', args=[obj.pk])


class RouteDetailView(AdminRequiredMixin, DetailView):
	model = Route
	template_name = 'tracking/admin/route_detail.html'

	def get_queryset(self):
		return super().get_queryset().select_related('bus').prefetch_related('stops')


@api_view(['GET'])
@permission_classes([AllowAny])
def route_stops_api(request, route_id):
	route = get_object_or_404(Route, pk=route_id)
	stops = route.stops.all().order_by('stop_order')
	return Response(StopSerializer(stops, many=True).data)


class RouteCreateView(AdminFormViewMixin, CreateView):
	model = Route
	form_class = RouteForm
	form_title = 'Add route'
	list_url_name = 'route_list'
	success_message = 'Route created successfully.'


class RouteUpdateView(AdminFormViewMixin, UpdateView):
	model = Route
	form_class = RouteForm
	form_title = 'Edit route'
	list_url_name = 'route_list'
	success_message = 'Route updated successfully.'


class RouteDeleteView(AdminDeleteView):
	model = Route
	page_title = 'Delete route'
	list_url_name = 'route_list'
	success_message = 'Route deleted successfully.'


class StopListView(AdminListView):
	model = Stop
	page_title = 'Stops'
	item_label = 'stop'
	add_url_name = 'stop_add'
	edit_url_name = 'stop_edit'
	delete_url_name = 'stop_delete'
	search_fields = ('stop_name', 'route__route_name')
	columns = (('Stop', 'stop_name'), ('Route', 'route'), ('Order', 'stop_order'), ('Latitude', 'latitude'), ('Longitude', 'longitude'))

	def get_queryset(self):
		return super().get_queryset().select_related('route')


class StopCreateView(AdminFormViewMixin, CreateView):
	model = Stop
	form_class = StopForm
	form_title = 'Add stop'
	list_url_name = 'stop_list'
	success_message = 'Stop created successfully.'


class StopUpdateView(AdminFormViewMixin, UpdateView):
	model = Stop
	form_class = StopForm
	form_title = 'Edit stop'
	list_url_name = 'stop_list'
	success_message = 'Stop updated successfully.'


class StopDeleteView(AdminDeleteView):
	model = Stop
	page_title = 'Delete stop'
	list_url_name = 'stop_list'
	success_message = 'Stop deleted successfully.'


class DriverListView(AdminListView):
	model = User
	page_title = 'Drivers'
	item_label = 'driver'
	add_url_name = 'driver_add'
	edit_url_name = 'driver_edit'
	delete_url_name = 'driver_delete'
	search_fields = ('username', 'first_name', 'phone')
	columns = (('Name', 'first_name'), ('Username', 'username'), ('Phone', 'phone'), ('Status', 'is_active'))

	def get_queryset(self):
		return super().get_queryset().filter(role=User.Role.DRIVER).order_by('username')


class DriverCreateView(AdminFormViewMixin, CreateView):
	model = User
	form_class = DriverForm
	form_title = 'Add driver'
	list_url_name = 'driver_list'
	success_message = 'Driver account created successfully.'


class DriverUpdateView(AdminFormViewMixin, UpdateView):
	model = User
	form_class = DriverForm
	form_title = 'Edit driver'
	list_url_name = 'driver_list'
	success_message = 'Driver account updated successfully.'

	def get_queryset(self):
		return super().get_queryset().filter(role=User.Role.DRIVER)


class DriverDeleteView(AdminDeleteView):
	model = User
	page_title = 'Delete driver'
	list_url_name = 'driver_list'
	success_message = 'Driver account deleted successfully.'

	def get_queryset(self):
		return super().get_queryset().filter(role=User.Role.DRIVER)


class StudentListView(AdminListView):
	model = User
	page_title = 'Students'
	item_label = 'student'
	add_url_name = 'student_add'
	edit_url_name = 'student_edit'
	delete_url_name = 'student_delete'
	search_fields = ('username', 'first_name', 'phone', 'student_profile__route__route_name')
	columns = (('Student', 'first_name'), ('Username', 'username'), ('Phone', 'phone'), ('Route', 'student_profile__route'), ('Pickup stop', 'student_profile__pickup_stop'))

	def get_queryset(self):
		return super().get_queryset().filter(role=User.Role.STUDENT).select_related(
			'student_profile__route', 'student_profile__pickup_stop'
		).order_by('username')

	def get_edit_url(self, obj):
		try:
			profile = obj.student_profile
		except StudentProfile.DoesNotExist:
			return reverse('student_assign_user', args=[obj.pk])
		return reverse('student_edit', args=[profile.pk])

	def get_delete_url(self, obj):
		return reverse('student_delete', args=[obj.pk])


class StudentProfileCreateView(AdminFormViewMixin, CreateView):
	model = StudentProfile
	form_class = StudentProfileForm
	form_title = 'Assign student route'
	list_url_name = 'student_list'
	success_message = 'Student route assigned successfully.'


class StudentAssignmentView(AdminFormViewMixin, CreateView):
	model = StudentProfile
	form_class = StudentAssignmentForm
	form_title = 'Assign student route'
	list_url_name = 'student_list'
	success_message = 'Student route assigned successfully.'

	@method_decorator(role_required(User.Role.ADMIN))
	def dispatch(self, request, *args, **kwargs):
		self.student = get_object_or_404(User, pk=kwargs['user_pk'], role=User.Role.STUDENT)
		if StudentProfile.objects.filter(user=self.student).exists():
			return redirect('student_edit', pk=self.student.student_profile.pk)
		return super().dispatch(request, *args, **kwargs)

	def form_valid(self, form):
		form.instance.user = self.student
		return super().form_valid(form)


class StudentProfileUpdateView(AdminFormViewMixin, UpdateView):
	model = StudentProfile
	form_class = StudentProfileForm
	form_title = 'Edit student assignment'
	list_url_name = 'student_list'
	success_message = 'Student assignment updated successfully.'


class StudentDeleteView(AdminDeleteView):
	model = User
	page_title = 'Delete student account'
	list_url_name = 'student_list'
	success_message = 'Student account deleted successfully.'

	def get_queryset(self):
		return super().get_queryset().filter(role=User.Role.STUDENT)

# Create your views here.
