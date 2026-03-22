"""Tests for the applications app: Application create, submit, status change,
withdraw, permission checks, and ApplicationDocument upload."""

import os
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from applications.models import Application, ApplicationDocument, ApplicationStatusHistory
from core.models import Agency, Organization
from grants.models import FundingSource, GrantProgram

User = get_user_model()

TEST_PASSWORD = os.environ.get('TEST_PASSWORD', 'test' + 'pass123!')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _agency(**kw):
    defaults = {'name': 'Dept of Testing', 'abbreviation': kw.pop('abbreviation', 'DOT')}
    defaults.update(kw)
    return Agency.objects.create(**defaults)


def _fs():
    return FundingSource.objects.create(name='State Fund', source_type='state')


def _org(**kw):
    defaults = {'name': 'Test Org', 'org_type': 'nonprofit'}
    defaults.update(kw)
    return Organization.objects.create(**defaults)


def _user(username, role, agency=None, organization=None, **kw):
    return User.objects.create_user(
        username=username, password=TEST_PASSWORD, email=f'{username}@example.com',
        role=role, agency=agency, organization=organization, **kw,
    )


def _grant_program(agency, fs, created_by, **kw):
    defaults = {
        'agency': agency, 'title': 'Test Grant', 'description': 'Desc',
        'funding_source': fs, 'total_funding': Decimal('500000'),
        'min_award': Decimal('5000'), 'max_award': Decimal('50000'),
        'fiscal_year': '2025-2026', 'duration_months': 12,
        'application_deadline': timezone.now() + timedelta(days=30),
        'posting_date': timezone.now(),
        'created_by': created_by,
        'status': GrantProgram.Status.ACCEPTING_APPLICATIONS,
        'is_published': True,
    }
    defaults.update(kw)
    return GrantProgram.objects.create(**defaults)


def _application(grant_program, applicant, organization, **kw):
    defaults = {
        'grant_program': grant_program,
        'applicant': applicant,
        'organization': organization,
        'project_title': 'Test Project',
        'project_description': 'A test project description.',
        'requested_amount': Decimal('10000.00'),
        'proposed_start_date': date.today(),
        'proposed_end_date': date.today() + timedelta(days=365),
        'status': Application.Status.DRAFT,
    }
    defaults.update(kw)
    return Application.objects.create(**defaults)


# ===========================================================================
# Model tests
# ===========================================================================
class ApplicationModelTests(TestCase):

    def setUp(self):
        self.agency = _agency()
        self.fs = _fs()
        self.org = _org()
        self.officer = _user('officer', User.Role.PROGRAM_OFFICER, agency=self.agency)
        self.applicant = _user('applicant', User.Role.APPLICANT, organization=self.org)
        self.gp = _grant_program(self.agency, self.fs, self.officer)

    def test_is_editable_draft(self):
        app = _application(self.gp, self.applicant, self.org)
        self.assertTrue(app.is_editable)

    def test_is_editable_revision_requested(self):
        app = _application(self.gp, self.applicant, self.org,
                           status=Application.Status.REVISION_REQUESTED)
        self.assertTrue(app.is_editable)

    def test_not_editable_submitted(self):
        app = _application(self.gp, self.applicant, self.org,
                           status=Application.Status.SUBMITTED)
        self.assertFalse(app.is_editable)

    def test_str(self):
        app = _application(self.gp, self.applicant, self.org, project_title='My Project')
        self.assertIn('My Project', str(app))


# ===========================================================================
# View tests
# ===========================================================================
class ApplicationCreateViewTests(TestCase):

    def setUp(self):
        self.agency = _agency()
        self.fs = _fs()
        self.org = _org()
        self.officer = _user('officer', User.Role.PROGRAM_OFFICER, agency=self.agency)
        self.applicant = _user('applicant', User.Role.APPLICANT, organization=self.org)
        self.gp = _grant_program(self.agency, self.fs, self.officer)

    def test_create_requires_login(self):
        url = reverse('applications:create', kwargs={'grant_program_id': self.gp.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)

    def test_create_redirects_if_no_org(self):
        no_org_user = _user('noorg', User.Role.APPLICANT)
        self.client.force_login(no_org_user)
        url = reverse('applications:create', kwargs={'grant_program_id': self.gp.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('organization/create', resp.url)

    def test_create_form_loads(self):
        self.client.force_login(self.applicant)
        url = reverse('applications:create', kwargs={'grant_program_id': self.gp.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_create_post(self):
        self.client.force_login(self.applicant)
        url = reverse('applications:create', kwargs={'grant_program_id': self.gp.pk})
        data = {
            'project_title': 'New App',
            'project_description': 'Description here',
            'requested_amount': '15000.00',
            'proposed_start_date': '2025-07-01',
            'proposed_end_date': '2026-06-30',
        }
        resp = self.client.post(url, data)
        self.assertEqual(resp.status_code, 302)
        app = Application.objects.get(project_title='New App')
        self.assertEqual(app.status, Application.Status.DRAFT)
        self.assertEqual(app.applicant, self.applicant)
        self.assertEqual(app.organization, self.org)


class ApplicationSubmitViewTests(TestCase):

    def setUp(self):
        self.agency = _agency()
        self.fs = _fs()
        self.org = _org()
        self.officer = _user('officer', User.Role.PROGRAM_OFFICER, agency=self.agency)
        self.applicant = _user('applicant', User.Role.APPLICANT, organization=self.org)
        self.gp = _grant_program(self.agency, self.fs, self.officer)
        self.app = _application(self.gp, self.applicant, self.org)

    def test_submit_draft_to_submitted(self):
        self.client.force_login(self.applicant)
        url = reverse('applications:submit', kwargs={'pk': self.app.pk})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, Application.Status.SUBMITTED)
        self.assertIsNotNone(self.app.submitted_at)
        # Check status history was created
        self.assertTrue(
            ApplicationStatusHistory.objects.filter(
                application=self.app, new_status=Application.Status.SUBMITTED
            ).exists()
        )

    def test_submit_non_editable_fails(self):
        self.app.status = Application.Status.SUBMITTED
        self.app.save()
        self.client.force_login(self.applicant)
        url = reverse('applications:submit', kwargs={'pk': self.app.pk})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)  # redirect with error message


class ApplicationWithdrawViewTests(TestCase):

    def setUp(self):
        self.agency = _agency()
        self.fs = _fs()
        self.org = _org()
        self.officer = _user('officer', User.Role.PROGRAM_OFFICER, agency=self.agency)
        self.applicant = _user('applicant', User.Role.APPLICANT, organization=self.org)
        self.gp = _grant_program(self.agency, self.fs, self.officer)
        self.app = _application(self.gp, self.applicant, self.org,
                                status=Application.Status.SUBMITTED)

    def test_withdraw_by_applicant(self):
        self.client.force_login(self.applicant)
        url = reverse('applications:withdraw', kwargs={'pk': self.app.pk})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, Application.Status.WITHDRAWN)

    def test_withdraw_already_withdrawn(self):
        self.app.status = Application.Status.WITHDRAWN
        self.app.save()
        self.client.force_login(self.applicant)
        url = reverse('applications:withdraw', kwargs={'pk': self.app.pk})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)


class ApplicationStatusChangeViewTests(TestCase):

    def setUp(self):
        self.agency = _agency()
        self.fs = _fs()
        self.org = _org()
        self.officer = _user('officer', User.Role.PROGRAM_OFFICER, agency=self.agency)
        self.applicant = _user('applicant', User.Role.APPLICANT, organization=self.org)
        self.gp = _grant_program(self.agency, self.fs, self.officer)
        self.app = _application(self.gp, self.applicant, self.org,
                                status=Application.Status.SUBMITTED)

    def test_status_change_by_staff(self):
        self.client.force_login(self.officer)
        url = reverse('applications:status-change', kwargs={'pk': self.app.pk})
        data = {
            'new_status': Application.Status.UNDER_REVIEW,
            'comment': 'Moving to review.',
        }
        resp = self.client.post(url, data)
        self.assertEqual(resp.status_code, 302)
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, Application.Status.UNDER_REVIEW)

    def test_status_change_denied_for_applicant(self):
        self.client.force_login(self.applicant)
        url = reverse('applications:status-change', kwargs={'pk': self.app.pk})
        data = {
            'new_status': Application.Status.UNDER_REVIEW,
            'comment': 'Trying to change status.',
        }
        resp = self.client.post(url, data)
        self.assertEqual(resp.status_code, 403)

    def test_invalid_transition_rejected(self):
        self.client.force_login(self.officer)
        url = reverse('applications:status-change', kwargs={'pk': self.app.pk})
        # submitted -> approved is not valid directly
        data = {
            'new_status': Application.Status.APPROVED,
            'comment': 'Skip the review.',
        }
        resp = self.client.post(url, data)
        self.assertEqual(resp.status_code, 302)
        self.app.refresh_from_db()
        # Status should remain submitted because transition is invalid
        self.assertEqual(self.app.status, Application.Status.SUBMITTED)


class ApplicationDetailViewTests(TestCase):

    def setUp(self):
        self.agency = _agency()
        self.fs = _fs()
        self.org = _org()
        self.officer = _user('officer', User.Role.PROGRAM_OFFICER, agency=self.agency)
        self.applicant = _user('applicant', User.Role.APPLICANT, organization=self.org)
        self.gp = _grant_program(self.agency, self.fs, self.officer)
        self.app = _application(self.gp, self.applicant, self.org)

    def test_detail_accessible(self):
        self.client.force_login(self.applicant)
        url = reverse('applications:detail', kwargs={'pk': self.app.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['application'], self.app)
