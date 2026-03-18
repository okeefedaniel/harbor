"""Management command to generate a data retention compliance report.

Usage:
    python manage.py retention_report
"""
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone

from core.models import ArchivedRecord


class Command(BaseCommand):
    help = 'Generate a data retention compliance summary report'

    def handle(self, *args, **options):
        now = timezone.now()

        self.stdout.write('=' * 60)
        self.stdout.write('  BEACON DATA RETENTION COMPLIANCE REPORT')
        self.stdout.write(f'  Generated: {now.strftime("%Y-%m-%d %H:%M:%S")}')
        self.stdout.write('=' * 60)
        self.stdout.write('')

        # Summary by entity type
        self.stdout.write('  Archived Records by Entity Type:')
        self.stdout.write('  ' + '-' * 40)
        by_type = (
            ArchivedRecord.objects
            .values('entity_type')
            .annotate(count=Count('id'))
            .order_by('entity_type')
        )
        total = 0
        for row in by_type:
            display = dict(ArchivedRecord.EntityType.choices).get(
                row['entity_type'], row['entity_type']
            )
            self.stdout.write(f'    {display:<25} {row["count"]:>6}')
            total += row['count']
        self.stdout.write(f'    {"TOTAL":<25} {total:>6}')
        self.stdout.write('')

        # Summary by retention policy
        self.stdout.write('  Archived Records by Retention Policy:')
        self.stdout.write('  ' + '-' * 40)
        by_policy = (
            ArchivedRecord.objects
            .values('retention_policy')
            .annotate(count=Count('id'))
            .order_by('retention_policy')
        )
        for row in by_policy:
            display = dict(ArchivedRecord.RetentionPolicy.choices).get(
                row['retention_policy'], row['retention_policy']
            )
            self.stdout.write(f'    {display:<25} {row["count"]:>6}')
        self.stdout.write('')

        # Expiration summary
        expired = ArchivedRecord.objects.filter(
            retention_expires_at__lt=now,
            is_purged=False,
        ).count()
        purged = ArchivedRecord.objects.filter(is_purged=True).count()
        pending = ArchivedRecord.objects.filter(
            retention_expires_at__gte=now,
            is_purged=False,
        ).count()
        permanent = ArchivedRecord.objects.filter(
            retention_policy=ArchivedRecord.RetentionPolicy.PERMANENT,
        ).count()

        self.stdout.write('  Retention Status:')
        self.stdout.write('  ' + '-' * 40)
        self.stdout.write(f'    {"Pending retention":<25} {pending:>6}')
        self.stdout.write(f'    {"Expired (awaiting purge)":<25} {expired:>6}')
        self.stdout.write(f'    {"Already purged":<25} {purged:>6}')
        self.stdout.write(f'    {"Permanent retention":<25} {permanent:>6}')
        self.stdout.write('')
        self.stdout.write('=' * 60)
