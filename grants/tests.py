"""Tests for the grants app: GrantProgram CRUD, permission checks,
publish/unpublish toggle, and is_accepting_applications property."""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Agency, Organization
from grants.models import FundingSource, GrantProgram

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _agency(**kw):
    defaults = {'name': 'Dept of Testing', 'abbreviation': kw.pop('abbreviation', 'DOT')}
    defaults.update(kw)
    return Agency.objects.create(**defaults)


def _funding_source(**kw):
    defaults = {'name': 'State General Fund', 'source_type': FundingSource.SourceType.STATE}
    defaults.update(kw)
    return FundingSource.objects.create(**defaults)


def _user(username, role, agency=None, **kw):
    return User.objects.create_user(
        username=username, password='testpass123!', email=f'{username}@example.com',
        role=role, agency=agency, **kw,
    )


def _grant_program(agency, funding_source, created_by, **kw):
    defaults = {
        'agency': agency,
        'title': 'Test Grant Program',
        'description': 'A test grant program.',
        'funding_source': funding_source,
        'total_funding': Decimal('500000.00'),
        'min_award': Decimal('5000.00'),
        'max_award': Decimal('50000.00'),
        'fiscal_year': '2025-2026',
        'duration_months': 12,
        'application_deadline': timezone.now() + timedelta(days=30),
        'posting_date': timezone.now(),
        'created_by': created_by,
    }
    defaults.update(kw)
    return GrantProgram.objects.create(**defaults)


# ===========================================================================
# Model tests
# ===========================================================================
class GrantProgramModelTests(TestCase):

    def setUp(self):
        self.agency = _agency()
        self.fs = _funding_source()
        self.officer = _user('officer', User.Role.PROGRAM_OFFICER, agency=self.agency)

    def test_is_accepting_applications_true(self):
        gp = _grant_program(
            self.agency, self.fs, self.officer,
            status=GrantProgram.Status.ACCEPTING_APPLICATIONS,
            application_deadline=timezone.now() + timedelta(days=10),
        )
        self.assertTrue(gp.is_accepting_applications)

    def test_is_accepting_applications_false_past_deadline(self):
        gp = _grant_program(
            self.agency, self.fs, self.officer,
            status=GrantProgram.Status.ACCEPTING_APPLICATIONS,
            application_deadline=timezone.now() - timedelta(days=1),
        )
        self.assertFalse(gp.is_accepting_applications)

    def test_is_accepting_applications_false_wrong_status(self):
        gp = _grant_program(
            self.agency, self.fs, self.officer,
            status=GrantProgram.Status.DRAFT,
            application_deadline=timezone.now() + timedelta(days=10),
        )
        self.assertFalse(gp.is_accepting_applications)

    def test_days_until_deadline(self):
        gp = _grant_program(
            self.agency, self.fs, self.officer,
            application_deadline=timezone.now() + timedelta(days=15),
        )
        self.assertIsNotNone(gp.days_until_deadline)
        self.assertGreaterEqual(gp.days_until_deadline, 14)

    def test_days_until_deadline_past(self):
        gp = _grant_program(
            self.agency, self.fs, self.officer,
            application_deadline=timezone.now() - timedelta(days=1),
        )
        self.assertIsNone(gp.days_until_deadline)

    def test_str(self):
        gp = _grant_program(self.agency, self.fs, self.officer, title='My Grant')
        self.assertEqual(str(gp), 'My Grant')


# ===========================================================================
# View tests
# ===========================================================================
class GrantProgramListViewTests(TestCase):

    def setUp(self):
        self.agency = _agency()
        self.fs = _funding_source()
        self.officer = _user('officer', User.Role.PROGRAM_OFFICER, agency=self.agency)
        self.applicant = _user('applicant', User.Role.APPLICANT)
        _grant_program(self.agency, self.fs, self.officer)

    def test_list_requires_agency_staff(self):
        self.client.login(username='applicant', password='testpass123!')
        resp = self.client.get(reverse('grants:program-list'))
        self.assertEqual(resp.status_code, 403)

    def test_list_accessible_by_staff(self):
        self.client.login(username='officer', password='testpass123!')
        resp = self.client.get(reverse('grants:program-list'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context['programs']), 1)


class GrantProgramCreateViewTests(TestCase):

    def setUp(self):
        self.agency = _agency()
        self.fs = _funding_source()
        self.officer = _user('officer', User.Role.PROGRAM_OFFICER, agency=self.agency)
        self.applicant = _user('applicant', User.Role.APPLICANT)
        self.fiscal = _user('fiscal', User.Role.FISCAL_OFFICER, agency=self.agency)

    def test_create_denied_for_applicant(self):
        self.client.login(username='applicant', password='testpass123!')
        resp = self.client.get(reverse('grants:program-create'))
        self.assertEqual(resp.status_code, 403)

    def test_create_denied_for_fiscal_officer(self):
        self.client.login(username='fiscal', password='testpass123!')
        resp = self.client.get(reverse('grants:program-create'))
        self.assertEqual(resp.status_code, 403)

    def test_create_accessible_by_grant_manager(self):
        self.client.login(username='officer', password='testpass123!')
        resp = self.client.get(reverse('grants:program-create'))
        self.assertEqual(resp.status_code, 200)

    def test_create_grant_program_post(self):
        self.client.login(username='officer', password='testpass123!')
        deadline = (timezone.now() + timedelta(days=30)).strftime('%Y-%m-%dT%H:%M')
        posting = timezone.now().strftime('%Y-%m-%dT%H:%M')
        data = {
            'title': 'New Program',
            'description': 'Desc',
            'funding_source': str(self.fs.pk),
            'grant_type': 'competitive',
            'total_funding': '100000',
            'min_award': '1000',
            'max_award': '50000',
            'fiscal_year': '2025-2026',
            'duration_months': '12',
            'application_deadline': deadline,
            'posting_date': posting,
        }
        resp = self.client.post(reverse('grants:program-create'), data)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(GrantProgram.objects.filter(title='New Program').exists())


class GrantProgramDetailViewTests(TestCase):

    def setUp(self):
        self.agency = _agency()
        self.fs = _funding_source()
        self.officer = _user('officer', User.Role.PROGRAM_OFFICER, agency=self.agency)
        self.program = _grant_program(self.agency, self.fs, self.officer)

    def test_detail_accessible_by_staff(self):
        self.client.login(username='officer', password='testpass123!')
        resp = self.client.get(
            reverse('grants:program-detail', kwargs={'pk': self.program.pk})
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['program'], self.program)


class PublishGrantProgramViewTests(TestCase):

    def setUp(self):
        self.agency = _agency()
        self.fs = _funding_source()
        self.officer = _user('officer', User.Role.PROGRAM_OFFICER, agency=self.agency)
        self.program = _grant_program(self.agency, self.fs, self.officer)

    def test_publish_toggle(self):
        self.client.login(username='officer', password='testpass123!')
        url = reverse('grants:program-publish', kwargs={'pk': self.program.pk})
        # Publish
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200)
        self.program.refresh_from_db()
        self.assertTrue(self.program.is_published)
        self.assertEqual(self.program.status, GrantProgram.Status.POSTED)
        # Unpublish
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200)
        self.program.refresh_from_db()
        self.assertFalse(self.program.is_published)
        self.assertEqual(self.program.status, GrantProgram.Status.DRAFT)

    def test_publish_denied_for_applicant(self):
        applicant = _user('applicant', User.Role.APPLICANT)
        self.client.login(username='applicant', password='testpass123!')
        url = reverse('grants:program-publish', kwargs={'pk': self.program.pk})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 403)
