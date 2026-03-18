"""
Management command to seed the database with demo data.

Usage:
    python manage.py seed_demo           # Seed data + create admin
    python manage.py seed_demo --reset   # Wipe all data first, then seed
"""
import subprocess
import sys
from pathlib import Path

from django.core.management.base import BaseCommand

from core.models import User


class Command(BaseCommand):
    help = 'Seed the database with demo data for Beacon'

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
            User.objects.create_superuser(
                username='admin',
                email='admin@dok.gov',
                password='admin123',
                first_name='System',
                last_name='Admin',
                role='system_admin',
            )
            self.stdout.write(self.style.SUCCESS('  admin / admin123 created'))
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

            staff = User.objects.filter(
                role__in=['system_admin', 'program_officer']
            ).first()

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
            self.stdout.write('  Login: admin / admin123')
            self.stdout.write('  Demo users password: demo2026')
        else:
            self.stdout.write(
                self.style.ERROR(f'Seed script not found at {seed_script}')
            )
