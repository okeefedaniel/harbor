"""Management command to purge expired archived records.

Usage:
    python manage.py purge_expired_archives
    python manage.py purge_expired_archives --dry-run
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import ArchivedRecord


class Command(BaseCommand):
    help = 'Mark expired archived records as purged'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be purged without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        now = timezone.now()

        expired = ArchivedRecord.objects.filter(
            retention_expires_at__lt=now,
            is_purged=False,
        ).exclude(
            retention_policy=ArchivedRecord.RetentionPolicy.PERMANENT,
        )

        count = expired.count()
        self.stdout.write(f'Found {count} expired archived record(s).')

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — no changes will be made'))
            for record in expired[:20]:
                self.stdout.write(
                    f'  Would purge: {record.get_entity_type_display()} '
                    f'{record.entity_id} (expired {record.retention_expires_at.date()})'
                )
            if count > 20:
                self.stdout.write(f'  ... and {count - 20} more')
        else:
            updated = expired.update(is_purged=True, purged_at=now)
            self.stdout.write(self.style.SUCCESS(
                f'Marked {updated} archived record(s) as purged.'
            ))
