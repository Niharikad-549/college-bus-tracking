from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class CustomUserManager(UserManager):
	def create_superuser(self, username, email=None, password=None, **extra_fields):
		extra_fields.setdefault('role', User.Role.ADMIN)
		return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
	class Role(models.TextChoices):
		ADMIN = 'admin', 'Admin'
		DRIVER = 'driver', 'Driver'
		STUDENT = 'student', 'Student'

	role = models.CharField(max_length=10, choices=Role.choices, default=Role.STUDENT)
	phone = models.CharField(max_length=20, blank=True)

	objects = CustomUserManager()

	def __str__(self):
		return self.username

# Create your models here.
