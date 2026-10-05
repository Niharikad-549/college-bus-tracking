from django.urls import path

from . import views

urlpatterns = [
	path('api/routes/<int:route_id>/stops/', views.route_stops_api, name='route_stops_api'),
	path('dashboard/admin/', views.AdminDashboardView.as_view(), name='admin_dashboard'),
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