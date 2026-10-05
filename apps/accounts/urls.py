from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('accounts/login/', views.RoleLoginView.as_view(), name='login'),
    path('accounts/logout/', views.logout_view, name='logout'),
    path('accounts/register/', views.register_student, name='register'),
    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/driver/', views.driver_dashboard, name='driver_dashboard'),
    path('dashboard/student/', views.student_dashboard, name='student_dashboard'),
]