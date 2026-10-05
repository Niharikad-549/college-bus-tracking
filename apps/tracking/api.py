from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from apps.accounts.models import User

from .models import Bus, BusLocation, StudentProfile, Trip
from .services import record_bus_location


class IsDriver(BasePermission):
	message = 'Only driver accounts can use this endpoint.'

	def has_permission(self, request, view):
		return request.user.is_authenticated and request.user.role == User.Role.DRIVER


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
	user = request.user
	can_view = user.role == User.Role.ADMIN or (
		user.role == User.Role.DRIVER and bus.driver_id == user.pk
	)
	if user.role == User.Role.STUDENT:
		try:
			can_view = user.student_profile.route.bus_id == bus.pk
		except (StudentProfile.DoesNotExist, AttributeError):
			can_view = False
	if not can_view:
		return Response({'detail': 'You do not have access to this bus location.'}, status=status.HTTP_403_FORBIDDEN)

	location = BusLocation.objects.filter(bus=bus).order_by('-timestamp', '-pk').first()
	trip = Trip.objects.filter(bus=bus, is_active=True).first()
	if trip is None:
		trip = Trip.objects.filter(bus=bus).order_by('-started_at', '-pk').first()
	return Response({
		'bus_id': bus.pk,
		'bus_number': bus.bus_number,
		'location': BusLocationSerializer(location).data if location else None,
		'trip_status': TripStatusSerializer(trip).data if trip else {
			'is_active': False,
			'started_at': None,
			'ended_at': None,
		},
	})