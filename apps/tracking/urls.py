from django.urls import path

from . import api
from . import views

urlpatterns = [
	path('api/buses/<int:bus_id>/eta/', api.bus_eta, name='api_bus_eta'),
	path('api/admin/active-buses/', api.active_buses, name='api_active_buses'),
	path('api/driver/trip/start/', api.start_trip, name='api_trip_start'),
	path('api/driver/trip/stop/', api.stop_trip, name='api_trip_stop'),
	path('api/driver/location/', api.update_bus_location, name='api_driver_location'),
	path('api/buses/<int:bus_id>/location/', api.bus_location, name='api_bus_location'),
	path('api/routes/<int:route_id>/stops/', views.route_stops_api, name='route_stops_api'),
	path('dashboard/admin/', views.AdminDashboardView.as_view(), name='admin_dashboard'),
	path('dashboard/admin/live/', views.AdminLiveFleetView.as_view(), name='admin_live_fleet'),
	path('dashboard/admin/buses/', views.BusListView.as_view(), name='bus_list'),
	path('dashboard/admin/buses/add/', views.BusCreateView.as_view(), name='bus_add'),
	path('dashboard/admin/buses/<int:pk>/edit/', views.BusUpdateView.as_view(), name='bus_edit'),
	path('dashboard/admin/buses/<int:pk>/delete/', views.BusDeleteView.as_view(), name='bus_delete'),
	path('dashboard/admin/routes/', views.RouteListView.as_view(), name='route_list'),
	path('dashboard/admin/routes/add/', views.RouteCreateView.as_view(), name='route_add'),
	path('dashboard/admin/routes/<int:pk>/', views.RouteDetailView.as_view(), name='route_detail'),
	path('dashboard/admin/routes/<int:pk>/edit/', views.RouteUpdateView.as_view(), name='route_edit'),
	path('dashboard/admin/routes/<int:pk>/delete/', views.RouteDeleteView.as_view(), name='route_delete'),
	path('dashboard/admin/stops/', views.StopListView.as_view(), name='stop_list'),
	path('dashboard/admin/stops/add/', views.StopCreateView.as_view(), name='stop_add'),
	path('dashboard/admin/stops/<int:pk>/edit/', views.StopUpdateView.as_view(), name='stop_edit'),
	path('dashboard/admin/stops/<int:pk>/delete/', views.StopDeleteView.as_view(), name='stop_delete'),
	path('dashboard/admin/drivers/', views.DriverListView.as_view(), name='driver_list'),
	path('dashboard/admin/drivers/add/', views.DriverCreateView.as_view(), name='driver_add'),
	path('dashboard/admin/drivers/<int:pk>/edit/', views.DriverUpdateView.as_view(), name='driver_edit'),
	path('dashboard/admin/drivers/<int:pk>/delete/', views.DriverDeleteView.as_view(), name='driver_delete'),
	path('dashboard/admin/students/', views.StudentListView.as_view(), name='student_list'),
	path('dashboard/admin/students/add/', views.StudentProfileCreateView.as_view(), name='student_add'),
	path('dashboard/admin/students/<int:user_pk>/assign/', views.StudentAssignmentView.as_view(), name='student_assign_user'),
	path('dashboard/admin/students/<int:pk>/edit/', views.StudentProfileUpdateView.as_view(), name='student_edit'),
	path('dashboard/admin/students/<int:pk>/delete/', views.StudentDeleteView.as_view(), name='student_delete'),
]