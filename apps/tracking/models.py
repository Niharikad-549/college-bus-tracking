from django.conf import settings
from django.db import models


class Bus(models.Model):
	bus_number = models.CharField(max_length=20, unique=True)
	capacity = models.PositiveIntegerField()
	driver = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='driven_buses',
	)
	is_active = models.BooleanField(default=True)

	def __str__(self):
		return self.bus_number


class Route(models.Model):
	route_name = models.CharField(max_length=100)
	bus = models.ForeignKey(Bus, on_delete=models.CASCADE, related_name='routes')

	def __str__(self):
		return self.route_name


class Stop(models.Model):
	route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name='stops')
	stop_name = models.CharField(max_length=100)
	latitude = models.DecimalField(max_digits=9, decimal_places=6)
	longitude = models.DecimalField(max_digits=9, decimal_places=6)
	stop_order = models.PositiveSmallIntegerField()

	class Meta:
		ordering = ['route', 'stop_order']
		constraints = [
			models.UniqueConstraint(
				fields=['route', 'stop_order'],
				name='unique_stop_order_per_route',
			),
		]

	def __str__(self):
		return f'{self.route.route_name}: {self.stop_name}'


class BusLocation(models.Model):
	bus = models.ForeignKey(Bus, on_delete=models.CASCADE, related_name='locations')
	latitude = models.DecimalField(max_digits=9, decimal_places=6)
	longitude = models.DecimalField(max_digits=9, decimal_places=6)
	speed = models.DecimalField(max_digits=6, decimal_places=2, default=0)
	timestamp = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-timestamp']

	def __str__(self):
		return f'{self.bus.bus_number} at {self.timestamp:%Y-%m-%d %H:%M:%S}'


class Trip(models.Model):
	bus = models.ForeignKey(Bus, on_delete=models.CASCADE, related_name='trips')
	started_at = models.DateTimeField(auto_now_add=True)
	ended_at = models.DateTimeField(null=True, blank=True)
	is_active = models.BooleanField(default=True)

	class Meta:
		ordering = ['-started_at']

	def __str__(self):
		return f'{self.bus.bus_number} trip started {self.started_at:%Y-%m-%d %H:%M}'


class StudentProfile(models.Model):
	user = models.OneToOneField(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name='student_profile',
	)
	route = models.ForeignKey(
		Route,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='students',
	)
	pickup_stop = models.ForeignKey(
		Stop,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='student_profiles',
	)

	def __str__(self):
		return f'{self.user.username} student profile'

# Create your models here.
