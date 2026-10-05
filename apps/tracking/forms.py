from django import forms
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db.models import Q

from apps.accounts.models import User

from .models import Bus, Route, Stop, StudentProfile


class StyledModelForm(forms.ModelForm):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		for field in self.fields.values():
			field.widget.attrs.setdefault('class', 'form-control')


class BusForm(StyledModelForm):
	class Meta:
		model = Bus
		fields = ('bus_number', 'capacity', 'driver', 'is_active')
		widgets = {'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})}

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields['driver'].queryset = User.objects.filter(role=User.Role.DRIVER).order_by('username')
		self.fields['driver'].required = True


class RouteForm(StyledModelForm):
	class Meta:
		model = Route
		fields = ('route_name', 'bus')


class StopForm(StyledModelForm):
	latitude = forms.DecimalField(
		max_digits=9,
		decimal_places=6,
		validators=[MinValueValidator(-90), MaxValueValidator(90)],
		widget=forms.NumberInput(attrs={'step': '0.000001', 'inputmode': 'decimal'}),
	)
	longitude = forms.DecimalField(
		max_digits=9,
		decimal_places=6,
		validators=[MinValueValidator(-180), MaxValueValidator(180)],
		widget=forms.NumberInput(attrs={'step': '0.000001', 'inputmode': 'decimal'}),
	)

	class Meta:
		model = Stop
		fields = ('route', 'stop_name', 'latitude', 'longitude', 'stop_order')

	def clean(self):
		cleaned_data = super().clean()
		route = cleaned_data.get('route')
		stop_order = cleaned_data.get('stop_order')
		if route is not None and stop_order is not None:
			duplicate = Stop.objects.filter(route=route, stop_order=stop_order)
			if self.instance.pk:
				duplicate = duplicate.exclude(pk=self.instance.pk)
			if duplicate.exists():
				self.add_error('stop_order', 'This order number is already used on this route.')
		return cleaned_data


class DriverForm(StyledModelForm):
	password1 = forms.CharField(label='Password', widget=forms.PasswordInput, strip=False)
	password2 = forms.CharField(label='Confirm password', widget=forms.PasswordInput, strip=False)

	class Meta:
		model = User
		fields = ('first_name', 'username', 'phone', 'is_active')
		widgets = {'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})}

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		if self.instance.pk:
			self.fields['password1'].required = False
			self.fields['password2'].required = False

	def clean(self):
		cleaned_data = super().clean()
		password1 = cleaned_data.get('password1')
		password2 = cleaned_data.get('password2')
		if password1 or password2:
			if password1 != password2:
				self.add_error('password2', 'The passwords do not match.')
		elif not self.instance.pk:
			self.add_error('password1', 'A password is required for a new driver.')
		return cleaned_data

	def save(self, commit=True):
		user = super().save(commit=False)
		user.role = User.Role.DRIVER
		password = self.cleaned_data.get('password1')
		if password:
			user.set_password(password)
		if commit:
			user.save()
		return user


class StudentProfileForm(StyledModelForm):
	class Meta:
		model = StudentProfile
		fields = ('user', 'route', 'pickup_stop')

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		students = User.objects.filter(role=User.Role.STUDENT)
		if self.instance.pk:
			students = students.filter(Q(student_profile__isnull=True) | Q(pk=self.instance.user_id))
		else:
			students = students.filter(student_profile__isnull=True)
		self.fields['user'].queryset = students.order_by('username')
		self.fields['route'].required = True
		self.fields['pickup_stop'].required = True

	def clean(self):
		cleaned_data = super().clean()
		route = cleaned_data.get('route')
		pickup_stop = cleaned_data.get('pickup_stop')
		if route and pickup_stop and pickup_stop.route_id != route.pk:
			self.add_error('pickup_stop', 'Choose a pickup stop from the selected route.')
		return cleaned_data


class StudentAssignmentForm(StyledModelForm):
	class Meta:
		model = StudentProfile
		fields = ('route', 'pickup_stop')

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.fields['route'].required = True
		self.fields['pickup_stop'].required = True

	def clean(self):
		cleaned_data = super().clean()
		route = cleaned_data.get('route')
		pickup_stop = cleaned_data.get('pickup_stop')
		if route and pickup_stop and pickup_stop.route_id != route.pk:
			self.add_error('pickup_stop', 'Choose a pickup stop from the selected route.')
		return cleaned_data