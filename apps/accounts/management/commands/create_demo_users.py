from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Create one demo account for each application role.'

    demo_users = (
        {
            'username': 'demo_admin',
            'name': 'Demo Admin',
            'role': 'admin',
            'phone': '555-0100',
            'password': 'DemoAdmin123!',
        },
        {
            'username': 'demo_driver',
            'name': 'Demo Driver',
            'role': 'driver',
            'phone': '555-0101',
            'password': 'DemoDriver123!',
        },
        {
            'username': 'demo_student',
            'name': 'Demo Student',
            'role': 'student',
            'phone': '555-0102',
            'password': 'DemoStudent123!',
        },
    )

    def handle(self, *args, **options):
        user_model = get_user_model()
        for demo_user in self.demo_users:
            user, created = user_model.objects.get_or_create(
                username=demo_user['username'],
                defaults={
                    'first_name': demo_user['name'],
                    'role': demo_user['role'],
                    'phone': demo_user['phone'],
                },
            )
            if created:
                user.set_password(demo_user['password'])
                user.save()
                status = 'Created'
            else:
                status = 'Already exists'
            self.stdout.write(f'{status}: {user.username} ({user.role})')