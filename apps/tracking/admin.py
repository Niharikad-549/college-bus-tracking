from django.contrib import admin

from .models import Bus, BusLocation, Route, Stop, StudentProfile, Trip


@admin.register(Bus)
class BusAdmin(admin.ModelAdmin):
	list_display = ('bus_number', 'capacity', 'driver', 'is_active')
	list_filter = ('is_active',)
	search_fields = ('bus_number', 'driver__username')


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
	list_display = ('route_name', 'bus')
	list_filter = ('bus',)
	search_fields = ('route_name', 'bus__bus_number')


@admin.register(Stop)
class StopAdmin(admin.ModelAdmin):
	list_display = ('stop_name', 'route', 'stop_order', 'latitude', 'longitude')
	list_filter = ('route',)
	search_fields = ('stop_name', 'route__route_name')
	list_editable = ('stop_order',)


@admin.register(BusLocation)
class BusLocationAdmin(admin.ModelAdmin):
	list_display = ('bus', 'latitude', 'longitude', 'speed', 'timestamp')
	list_filter = ('bus', 'timestamp')
	search_fields = ('bus__bus_number',)
	readonly_fields = ('timestamp',)


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
	list_display = ('bus', 'started_at', 'ended_at', 'is_active')
	list_filter = ('is_active', 'bus', 'started_at')
	search_fields = ('bus__bus_number',)
	readonly_fields = ('started_at',)


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
	list_display = ('user', 'route', 'pickup_stop')
	list_filter = ('route',)
	search_fields = ('user__username', 'user__first_name', 'user__last_name')
