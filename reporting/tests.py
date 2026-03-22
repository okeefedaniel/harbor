"""Tests for the reporting app: Report CRUD, submit/review flow,
SF425 generation, and permission checks."""

import os
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

TEST_PASSWORD = os.environ.get('TEST_PASSWORD', 'testpass123!')

from applications.models import Application
from awards.models import Award
from core.models import Agency, Organization
from grants.models import FundingSource, GrantProgram
from reporting.models import Report, ReportTemplate, SF425Report

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _agency(**kw):
    defaults = {'name': 'Dept of Testing', 'abbreviation': kw.pop('abbreviation', 'DOT')}
    defaults.update(kw)
    return Agency.objects.create(**defaults)


def _full_setup():
    agency = _agency()
    fs = FundingSource.objects.create(name='State Fund', source_type='state')
    org = Organization.objects.create(name='Test Org', org_type='nonprofit')
    officer = User.objects.create_user(
        username='officer', password=TEST_PASSWORD, email='officer@example.com',
        role=User.Role.PROGRAM_OFFICER, agency=agency,
    )
    applicant = User.objects.create_user(
        username='applicant', password=TEST_PASSWORD, email='applicant@example.com',
        role=User.Role.APPLICANT, organization=org,
    )
    gp = GrantProgram.objects.create(
        agency=agency, title='Test Grant', description='Desc',
        funding_source=fs, total_funding=Decimal('500000'),
        min_award=Decimal('5000'), max_award=Decimal('50000'),
        fiscal_year='2025-2026', duration_months=12,
        application_deadline=timezone.now() + timedelta(days=30),
        posting_date=timezone.now(), created_by=officer,
    )
    app = Application.objects.create(
        grant_program=gp, applicant=applicant, organization=org,
        project_title='Test Project', project_description='Desc',
        requested_amount=Decimal('25000'),
        proposed_start_date=date.today(),
        proposed_end_date=date.today() + timedelta(days=365),
        status=Application.Status.APPROVED,
    )
    award = Award.objects.create(
        application=app, grant_program=gp, agency=agency,
        recipient=applicant, organization=org,
        award_number='CT-DOT-2025-0001', title='Test Award',
        award_amount=Decimal('25000'), terms_and_conditions='Standard terms.',
        status=Award.Status.ACTIVE,
        start_date=date.today(), end_date=date.today() + timedelta(days=365),
    )
    return {
        'agency': agency, 'org': org, 'officer': officer,
        'applicant': applicant, 'gp': gp, 'app': app, 'award': award,
    }


# ===========================================================================
# Model tests
# ===========================================================================
class ReportModelTests(TestCase):

    def setUp(self):
        self.data = _full_setup()

    def test_create_report(self):
        report = Report.objects.create(
            award=self.data['award'],
            report_type=Report.ReportType.PROGRESS,
            reporting_period_start=date.today(),
            reporting_period_end=date.today() + timedelta(days=90),
            due_date=date.today() + timedelta(days=100),
        )
        self.assertEqual(report.status, Report.Status.DRAFT)
        self.assertIn('Progress', str(report))

    def test_is_overdue_true(self):
        report = Report.objects.create(
            award=self.data['award'],
            report_type=Report.ReportType.FISCAL,
            reporting_period_start=date.today() - timedelta(days=120),
            reporting_period_end=date.today() - timedelta(days=30),
            due_date=date.today() - timedelta(days=10),
            status=Report.Status.DRAFT,
        )
        self.assertTrue(report.is_overdue)

    def test_is_overdue_false_when_submitted(self):
        report = Report.objects.create(
            award=self.data['award'],
            report_type=Report.ReportType.FISCAL,
            reporting_period_start=date.today() - timedelta(days=120),
            reporting_period_end=date.today() - timedelta(days=30),
            due_date=date.today() - timedelta(days=10),
            status=Report.Status.SUBMITTED,
        )
        self.assertFalse(report.is_overdue)


class SF425ReportModelTests(TestCase):

    def setUp(self):
        self.data = _full_setup()

    def test_create_sf425(self):
        sf425 = SF425Report.objects.create(
            award=self.data['award'],
            reporting_period_start=date.today(),
            reporting_period_end=date.today() + timedelta(days=90),
            generated_by=self.data['officer'],
        )
        self.assertEqual(sf425.status, SF425Report.Status.DRAFT)
        self.assertIn('SF-425', str(sf425))


# ===========================================================================
# View tests
# ===========================================================================
class ReportListViewTests(TestCase):

    def setUp(self):
        self.data = _full_setup()

    def test_list_accessible(self):
        self.client.force_login(self.data['officer'])
        resp = self.client.get(reverse('reporting:list'))
        self.assertEqual(resp.status_code, 200)


class ReportCreateViewTests(TestCase):

    def setUp(self):
        self.data = _full_setup()

    def test_create_form_loads(self):
        self.client.force_login(self.data['applicant'])
        url = reverse('reporting:create', kwargs={'award_id': self.data['award'].pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_create_report_post(self):
        self.client.force_login(self.data['applicant'])
        url = reverse('reporting:create', kwargs={'award_id': self.data['award'].pk})
        data = {
            'report_type': 'progress',
            'reporting_period_start': '2025-07-01',
            'reporting_period_end': '2025-09-30',
            'due_date': '2025-10-15',
            'data': '{}',
        }
        resp = self.client.post(url, data)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Report.objects.filter(award=self.data['award']).exists())


class ReportSubmitViewTests(TestCase):

    def setUp(self):
        self.data = _full_setup()
        self.report = Report.objects.create(
            award=self.data['award'],
            report_type=Report.ReportType.PROGRESS,
            reporting_period_start=date.today(),
            reporting_period_end=date.today() + timedelta(days=90),
            due_date=date.today() + timedelta(days=100),
            status=Report.Status.DRAFT,
        )

    def test_submit_report(self):
        self.client.force_login(self.data['applicant'])
        url = reverse('reporting:submit', kwargs={'pk': self.report.pk})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200)  # JSON response
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, Report.Status.SUBMITTED)
        self.assertIsNotNone(self.report.submitted_at)

    def test_submit_non_draft_fails(self):
        self.report.status = Report.Status.APPROVED
        self.report.save()
        self.client.force_login(self.data['applicant'])
        url = reverse('reporting:submit', kwargs={'pk': self.report.pk})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 400)


class ReportReviewViewTests(TestCase):

    def setUp(self):
        self.data = _full_setup()
        self.report = Report.objects.create(
            award=self.data['award'],
            report_type=Report.ReportType.PROGRESS,
            reporting_period_start=date.today(),
            reporting_period_end=date.today() + timedelta(days=90),
            due_date=date.today() + timedelta(days=100),
            status=Report.Status.SUBMITTED,
        )

    def test_approve_report(self):
        self.client.force_login(self.data['officer'])
        url = reverse('reporting:review', kwargs={'pk': self.report.pk})
        data = {'action': 'approve', 'comments': 'Looks good.'}
        resp = self.client.post(url, data)
        self.assertEqual(resp.status_code, 302)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, Report.Status.APPROVED)

    def test_request_revision(self):
        self.client.force_login(self.data['officer'])
        url = reverse('reporting:review', kwargs={'pk': self.report.pk})
        data = {'action': 'revision', 'comments': 'Needs more detail.'}
        resp = self.client.post(url, data)
        self.assertEqual(resp.status_code, 302)
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, Report.Status.REVISION_REQUESTED)

    def test_review_denied_for_applicant(self):
        self.client.force_login(self.data['applicant'])
        url = reverse('reporting:review', kwargs={'pk': self.report.pk})
        data = {'action': 'approve', 'comments': 'Sneaky.'}
        resp = self.client.post(url, data)
        self.assertEqual(resp.status_code, 403)


class SF425ViewTests(TestCase):

    def setUp(self):
        self.data = _full_setup()

    def test_sf425_generate_page_loads(self):
        self.client.force_login(self.data['officer'])
        url = reverse('reporting:sf425', kwargs={'award_id': self.data['award'].pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('award', resp.context)

    def test_sf425_submit(self):
        sf425 = SF425Report.objects.create(
            award=self.data['award'],
            reporting_period_start=date.today(),
            reporting_period_end=date.today() + timedelta(days=90),
            generated_by=self.data['officer'],
            status=SF425Report.Status.DRAFT,
        )
        self.client.force_login(self.data['officer'])
        url = reverse('reporting:sf425-submit', kwargs={'pk': sf425.pk})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)
        sf425.refresh_from_db()
        self.assertEqual(sf425.status, SF425Report.Status.SUBMITTED)
