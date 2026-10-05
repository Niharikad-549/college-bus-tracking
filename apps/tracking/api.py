from datetime import timedelta

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import throttle_classes
from rest_framework.settings import api_settings
from rest_framework.throttling import UserRateThrottle

from apps.accounts.models import User

from .models import Bus, BusLocation, Stop, StudentProfile, Trip
from .services import calculate_eta, haversine_distance_km, record_bus_location


class IsDriver(BasePermission):
	message = 'Only driver accounts can use this endpoint.'

	def has_permission(self, request, view):
		return request.user.is_authenticated and request.user.role == User.Role.DRIVER


class DriverLocationThrottle(UserRateThrottle):
	scope = 'driver_location'

	def get_rate(self):
		return api_settings.DEFAULT_THROTTLE_RATES[self.scope]


class EtaQuerySerializer(serializers.Serializer):
	stop_id = serializers.IntegerField(min_value=1)


class TripActionSerializer(serializers.Serializer):
	bus_id = serializers.IntegerField(required=False, min_value=1)


class LocationUpdateSerializer(serializers.Serializer):
	bus_id = serializers.IntegerField(required=False, min_value=1)
	latitude = serializers.DecimalField(
		max_digits=9,
		decimal_places=6,
		min_value=-90,
		max_value=90,
	)
	longitude = serializers.DecimalField(
		max_digits=9,
		decimal_places=6,
		min_value=-180,
		max_value=180,
	)
	speed = serializers.DecimalField(
		max_digits=6,
		decimal_places=2,
		min_value=0,
		max_value=300,
		required=False,
		default=0,
	)


class BusLocationSerializer(serializers.ModelSerializer):
	class Meta:
		model = BusLocation
		fields = ('id', 'latitude', 'longitude', 'speed', 'timestamp')
		read_only_fields = fields


class TripStatusSerializer(serializers.ModelSerializer):
	class Meta:
		model = Trip
		fields = ('id', 'is_active', 'started_at', 'ended_at')
		read_only_fields = fields


def get_driver_bus(driver, bus_id=None):
	assigned_buses = Bus.objects.filter(driver=driver).order_by('bus_number')
	if bus_id is not None:
		return assigned_buses.filter(pk=bus_id).first()
	return assigned_buses.first()


def user_can_view_bus(user, bus):
	if user.role == User.Role.ADMIN:
		return True
	if user.role == User.Role.DRIVER:
		return bus.driver_id == user.pk
	if user.role == User.Role.STUDENT:
		try:
			return user.student_profile.route.bus_id == bus.pk
		except (StudentProfile.DoesNotExist, AttributeError):
			return False
	return False


@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDriver])
def start_trip(request):
	serializer = TripActionSerializer(data=request.data)
	serializer.is_valid(raise_exception=True)
	bus = get_driver_bus(request.user, serializer.validated_data.get('bus_id'))
	if bus is None:
		return Response({'detail': 'No assigned bus was found.'}, status=status.HTTP_404_NOT_FOUND)

	try:
		with transaction.atomic():
			bus = Bus.objects.select_for_update().get(pk=bus.pk, driver=request.user)
			if Trip.objects.filter(bus=bus, is_active=True).exists():
				return Response({'detail': 'This bus already has an active trip.'}, status=status.HTTP_409_CONFLICT)
			trip = Trip.objects.create(bus=bus)
	except IntegrityError:
		return Response({'detail': 'This bus already has an active trip.'}, status=status.HTTP_409_CONFLICT)

	return Response(TripStatusSerializer(trip).data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDriver])
def stop_trip(request):
	serializer = TripActionSerializer(data=request.data)
	serializer.is_valid(raise_exception=True)
	trips = Trip.objects.filter(bus__driver=request.user, is_active=True)
	bus_id = serializer.validated_data.get('bus_id')
	if bus_id is not None:
		trips = trips.filter(bus_id=bus_id)
	trip = trips.select_related('bus').order_by('-started_at').first()
	if trip is None:
		return Response({'detail': 'There is no active trip for your assigned bus.'}, status=status.HTTP_409_CONFLICT)

	with transaction.atomic():
		trip = Trip.objects.select_for_update().get(pk=trip.pk)
		if not trip.is_active:
			return Response({'detail': 'This trip has already stopped.'}, status=status.HTTP_409_CONFLICT)
		trip.is_active = False
		trip.ended_at = timezone.now()
		trip.save(update_fields=['is_active', 'ended_at'])
	return Response(TripStatusSerializer(trip).data)


@api_view(['POST'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated, IsDriver])
@throttle_classes([DriverLocationThrottle])
def update_bus_location(request):
	serializer = LocationUpdateSerializer(data=request.data)
	serializer.is_valid(raise_exception=True)
	data = serializer.validated_data
	active_trips = Trip.objects.filter(bus__driver=request.user, is_active=True).select_related('bus')
	if data.get('bus_id') is not None:
		active_trips = active_trips.filter(bus_id=data['bus_id'])
	trip = active_trips.order_by('-started_at').first()
	if trip is None:
		return Response({'detail': 'Start an active trip for your assigned bus before sending location.'}, status=status.HTTP_409_CONFLICT)

	location = record_bus_location(
		bus=trip.bus,
		latitude=data['latitude'],
		longitude=data['longitude'],
		speed=data['speed'],
	)
	return Response({
		'bus_id': trip.bus_id,
		'bus_number': trip.bus.bus_number,
		'location': BusLocationSerializer(location).data,
	}, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def bus_location(request, bus_id):
	bus = get_object_or_404(Bus, pk=bus_id)
	if not user_can_view_bus(request.user, bus):
		return Response({'detail': 'You do not have access to this bus location.'}, status=status.HTTP_403_FORBIDDEN)

	location = BusLocation.objects.filter(bus=bus).order_by('-timestamp', '-pk').first()
	trip = Trip.objects.filter(bus=bus, is_active=True).first()
	if trip is None:
		trip = Trip.objects.filter(bus=bus).order_by('-started_at', '-pk').first()
	return Response({
		'bus_id': bus.pk,
		'bus_number': bus.bus_number,
		'driver_name': (
			bus.driver.get_full_name() or bus.driver.username
			if bus.driver else 'Driver not assigned'
		),
		'location': BusLocationSerializer(location).data if location else None,
		'trip_status': TripStatusSerializer(trip).data if trip else {
			'is_active': False,
			'started_at': None,
			'ended_at': None,
		},
	})


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def bus_eta(request, bus_id):
	bus = get_object_or_404(Bus, pk=bus_id)
	if not user_can_view_bus(request.user, bus):
		return Response({'detail': 'You do not have access to this bus ETA.'}, status=status.HTTP_403_FORBIDDEN)

	query = EtaQuerySerializer(data=request.query_params)
	query.is_valid(raise_exception=True)
	stop = get_object_or_404(Stop, pk=query.validated_data['stop_id'], route__bus=bus)
	if request.user.role == User.Role.STUDENT and request.user.student_profile.route_id != stop.route_id:
		return Response({'detail': 'You do not have access to this stop ETA.'}, status=status.HTTP_403_FORBIDDEN)

	location = BusLocation.objects.filter(bus=bus).order_by('-timestamp', '-pk').first()
	if location is None:
		return Response({'detail': 'This bus has not reported a location yet.'}, status=status.HTTP_409_CONFLICT)

	eta = calculate_eta(bus=bus, stop=stop, location=location)
	trip_is_active = Trip.objects.filter(bus=bus, is_active=True).exists()
	distance_to_stop = haversine_distance_km(
		location.latitude,
		location.longitude,
		stop.latitude,
		stop.longitude,
	)
	arrival_state = 'trip_not_started'
	if trip_is_active:
		if distance_to_stop <= 0.15:
			arrival_state = 'arriving_now'
		else:
			later_stops = stop.route.stops.filter(stop_order__gt=stop.stop_order)
			passed_stop = any(
				haversine_distance_km(
					location.latitude,
					location.longitude,
					later_stop.latitude,
					later_stop.longitude,
				) <= 0.35
				for later_stop in later_stops
			)
			arrival_state = 'passed_stop' if passed_stop else 'en_route'

	return Response({
		'bus_id': bus.pk,
		'bus_number': bus.bus_number,
		'stop_id': stop.pk,
		'stop_name': stop.stop_name,
		**eta,
		'arrival_state': arrival_state,
		'trip_active': trip_is_active,
		'is_location_stale': timezone.now() - location.timestamp > timedelta(seconds=60),
	})


@api_view(['GET'])
@authentication_classes([SessionAuthentication])
@permission_classes([IsAuthenticated])
def active_buses(request):
	if request.user.role != User.Role.ADMIN:
		return Response({'detail': 'Only admins can view the fleet map.'}, status=status.HTTP_403_FORBIDDEN)

	buses = []
	trips = Trip.objects.filter(is_active=True).select_related('bus', 'bus__driver').order_by('bus__bus_number')
	for trip in trips:
		bus = trip.bus
		location = BusLocation.objects.filter(bus=bus).order_by('-timestamp', '-pk').first()
		route = bus.routes.order_by('pk').first()
		buses.append({
			'bus_id': bus.pk,
			'bus_number': bus.bus_number,
			'driver_name': (
				bus.driver.get_full_name() or bus.driver.username
				if bus.driver else 'Driver not assigned'
			),
			'route_name': route.route_name if route else 'Route not assigned',
			'location': BusLocationSerializer(location).data if location else None,
		})
	return Response({'buses': buses})