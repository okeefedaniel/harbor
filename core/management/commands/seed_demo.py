"""
Management command to seed the database with demo data.

Demo users are passwordless — login is exclusively via /demo-login/ (the
one-click role buttons). See keel CLAUDE.md → "Demo authentication —
passwordless contract" for the full rationale.

Usage:
    python manage.py seed_demo           # Seed data + create admin
    python manage.py seed_demo --reset   # Wipe all data first, then seed
"""
import subprocess
import sys
from pathlib import Path

from django.core.management.base import BaseCommand

from django.contrib.auth import get_user_model; User = get_user_model()


class Command(BaseCommand):
    help = 'Seed the database with demo data for Harbor'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Flush the database before seeding (destructive!)',
        )

    def handle(self, *args, **options):
        if options['reset']:
            self.stdout.write(self.style.WARNING('Flushing database...'))
            from django.core.management import call_command
            call_command('flush', '--noinput')

        # Create superuser if it doesn't exist
        if not User.objects.filter(username='admin').exists():
            self.stdout.write('Creating admin superuser...')
            su = User.objects.create_superuser(
                username='admin',
                email='admin@dok.gov',
                password=None,
                first_name='System',
                last_name='Admin',
            )
            su.set_unusable_password()
            su.save()
            # Role lives on ProductAccess, not on KeelUser.
            from keel.accounts.models import ProductAccess
            ProductAccess.objects.update_or_create(
                user=su, product='harbor',
                defaults={'role': 'system_admin', 'is_active': True},
            )
            self.stdout.write(self.style.SUCCESS('  admin user created (passwordless demo)'))
        else:
            self.stdout.write('Admin user already exists, skipping.')

        # Run the seed script
        seed_script = Path(__file__).resolve().parent.parent.parent.parent / 'seed_data.py'
        if seed_script.exists():
            self.stdout.write(f'Running seed script: {seed_script}')
            exec(open(seed_script).read(), {'__name__': '__seed__'})

            # Seed compliance items for submitted apps
            from applications.models import Application
            from applications.views import ensure_compliance_items

            apps = Application.objects.exclude(status='draft')
            for app in apps:
                ensure_compliance_items(app)
            self.stdout.write(
                self.style.SUCCESS(
                    f'  Compliance items seeded for {apps.count()} applications'
                )
            )

            # Verify some compliance items for approved/under_review apps
            from django.utils import timezone
            from applications.models import ApplicationComplianceItem

            from keel.accounts.models import ProductAccess
            staff_access = ProductAccess.objects.filter(
                product='harbor',
                role__in=['system_admin', 'program_officer'],
                is_active=True,
            ).select_related('user').first()
            staff = staff_access.user if staff_access else None

            if staff:
                # Fully verify approved apps
                for app in Application.objects.filter(status='approved'):
                    app.compliance_items.update(
                        is_verified=True,
                        verified_by=staff,
                        verified_at=timezone.now(),
                    )

                # Partially verify under_review apps
                for app in Application.objects.filter(status='under_review'):
                    items = list(app.compliance_items.all()[:5])
                    for item in items:
                        item.is_verified = True
                        item.verified_by = staff
                        item.verified_at = timezone.now()
                        item.save()

            self.stdout.write(self.style.SUCCESS('\nDemo data seeded successfully!'))
            self.stdout.write('  Sign in at /demo-login/ — one-click role buttons (no password).')
        else:
            self.stdout.write(
                self.style.ERROR(f'Seed script not found at {seed_script}')
            )
