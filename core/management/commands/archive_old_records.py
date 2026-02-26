"""Management command to archive old completed/closed records.

Usage:
    python manage.py archive_old_records --days 2555  # ~7 years
    python manage.py archive_old_records --dry-run
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from applications.models import Application
from awards.models import Award
from core.models import ArchivedRecord
from financial.models import DrawdownRequest
from reporting.models import Report


class Command(BaseCommand):
    help = 'Archive old completed/closed records based on retention policies'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=2555,  # ~7 years
            help='Archive records older than this many days (default: 2555 / ~7 years)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be archived without making changes',
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        cutoff = timezone.now() - timedelta(days=days)

        self.stdout.write(
            f'Archiving records older than {days} days '
            f'(before {cutoff.date()})...'
        )
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — no changes will be made'))

        total = 0

        # Archive old completed/withdrawn applications
        old_apps = Application.objects.filter(
            updated_at__lt=cutoff,
            status__in=['approved', 'denied', 'withdrawn'],
        ).exclude(
            pk__in=ArchivedRecord.objects.filter(
                entity_type=ArchivedRecord.EntityType.APPLICATION,
            ).values_list('entity_id', flat=True),
        )

        app_count = old_apps.count()
        self.stdout.write(f'  Applications to archive: {app_count}')

        if not dry_run:
            for app in old_apps.iterator():
                ArchivedRecord.objects.create(
                    entity_type=ArchivedRecord.EntityType.APPLICATION,
                    entity_id=str(app.pk),
                    entity_description=f'{app.project_title} ({app.get_status_display()})',
                    retention_policy=ArchivedRecord.RetentionPolicy.STANDARD,
                    original_created_at=app.created_at,
                    retention_expires_at=app.updated_at + timedelta(days=2555),
                    metadata={
                        'project_title': app.project_title,
                        'status': app.status,
                        'applicant_id': str(app.applicant_id),
                        'grant_program_id': str(app.grant_program_id),
                        'requested_amount': str(app.requested_amount),
                    },
                )
        total += app_count

        # Archive old completed/terminated awards
        old_awards = Award.objects.filter(
            updated_at__lt=cutoff,
            status__in=['completed', 'terminated', 'cancelled'],
        ).exclude(
            pk__in=ArchivedRecord.objects.filter(
                entity_type=ArchivedRecord.EntityType.AWARD,
            ).values_list('entity_id', flat=True),
        )

        award_count = old_awards.count()
        self.stdout.write(f'  Awards to archive: {award_count}')

        if not dry_run:
            for award in old_awards.iterator():
                ArchivedRecord.objects.create(
                    entity_type=ArchivedRecord.EntityType.AWARD,
                    entity_id=str(award.pk),
                    entity_description=f'{award.award_number} - {award.title}',
                    retention_policy=ArchivedRecord.RetentionPolicy.FEDERAL,
                    original_created_at=award.created_at,
                    retention_expires_at=award.updated_at + timedelta(days=1095),  # 3 years post-closeout
                    metadata={
                        'award_number': award.award_number,
                        'title': award.title,
                        'status': award.status,
                        'award_amount': str(award.award_amount),
                        'agency_id': str(award.agency_id),
                    },
                )
        total += award_count

        # Archive old drawdown requests
        old_drawdowns = DrawdownRequest.objects.filter(
            updated_at__lt=cutoff,
            status__in=['paid', 'denied'],
        ).exclude(
            pk__in=ArchivedRecord.objects.filter(
                entity_type=ArchivedRecord.EntityType.DRAWDOWN,
            ).values_list('entity_id', flat=True),
        )

        dr_count = old_drawdowns.count()
        self.stdout.write(f'  Drawdown requests to archive: {dr_count}')

        if not dry_run:
            for dr in old_drawdowns.iterator():
                ArchivedRecord.objects.create(
                    entity_type=ArchivedRecord.EntityType.DRAWDOWN,
                    entity_id=str(dr.pk),
                    entity_description=f'{dr.request_number} - ${dr.amount}',
                    retention_policy=ArchivedRecord.RetentionPolicy.STANDARD,
                    original_created_at=dr.created_at,
                    retention_expires_at=dr.updated_at + timedelta(days=2555),
                    metadata={
                        'request_number': dr.request_number,
                        'status': dr.status,
                        'amount': str(dr.amount),
                        'award_id': str(dr.award_id),
                    },
                )
        total += dr_count

        # Archive old approved reports
        old_reports = Report.objects.filter(
            updated_at__lt=cutoff,
            status__in=['approved', 'rejected'],
        ).exclude(
            pk__in=ArchivedRecord.objects.filter(
                entity_type=ArchivedRecord.EntityType.REPORT,
            ).values_list('entity_id', flat=True),
        )

        report_count = old_reports.count()
        self.stdout.write(f'  Reports to archive: {report_count}')

        if not dry_run:
            for report in old_reports.iterator():
                ArchivedRecord.objects.create(
                    entity_type=ArchivedRecord.EntityType.REPORT,
                    entity_id=str(report.pk),
                    entity_description=f'{report.get_report_type_display()} report for {report.award}',
                    retention_policy=ArchivedRecord.RetentionPolicy.STANDARD,
                    original_created_at=report.created_at,
                    retention_expires_at=report.updated_at + timedelta(days=2555),
                    metadata={
                        'report_type': report.report_type,
                        'status': report.status,
                        'award_id': str(report.award_id),
                    },
                )
        total += report_count

        self.stdout.write(self.style.SUCCESS(
            f'{"Would archive" if dry_run else "Archived"} {total} records total.'
        ))
