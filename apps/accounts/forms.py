from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import User


class StudentRegistrationForm(UserCreationForm):
    name = forms.CharField(max_length=150)
    phone = forms.CharField(max_length=20, required=False)

    class Meta:
        model = User
        fields = ('name', 'username', 'phone')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data['name'].strip()
        user.phone = self.cleaned_data['phone'].strip()
        user.role = User.Role.STUDENT
        if commit:
            user.save()
        return user