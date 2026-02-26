"""Tests for the awards app: Award creation, AwardAmendment create/approve/deny,
and permission checks."""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from applications.models import Application
from awards.models import Award, AwardAmendment
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


def _fs():
    return FundingSource.objects.create(name='State Fund', source_type='state')


def _org():
    return Organization.objects.create(name='Test Org', org_type='nonprofit')


def _user(username, role, agency=None, organization=None, **kw):
    return User.objects.create_user(
        username=username, password='testpass123!', email=f'{username}@example.com',
        role=role, agency=agency, organization=organization, **kw,
    )


def _grant_program(agency, fs, created_by, **kw):
    defaults = {
        'agency': agency, 'title': 'Test Grant', 'description': 'Desc',
        'funding_source': fs, 'total_funding': Decimal('500000'),
        'min_award': Decimal('5000'), 'max_award': Decimal('50000'),
        'fiscal_year': '2025-2026', 'duration_months': 12,
        'application_deadline': timezone.now() + timedelta(days=30),
        'posting_date': timezone.now(), 'created_by': created_by,
    }
    defaults.update(kw)
    return GrantProgram.objects.create(**defaults)


def _application(gp, applicant, org, **kw):
    defaults = {
        'grant_program': gp, 'applicant': applicant, 'organization': org,
        'project_title': 'Test Project', 'project_description': 'Desc',
        'requested_amount': Decimal('25000'),
        'proposed_start_date': date.today(),
        'proposed_end_date': date.today() + timedelta(days=365),
        'status': Application.Status.APPROVED,
    }
    defaults.update(kw)
    return Application.objects.create(**defaults)


def _award(application, agency, gp, recipient, org, **kw):
    defaults = {
        'application': application, 'grant_program': gp, 'agency': agency,
        'recipient': recipient, 'organization': org,
        'award_number': kw.pop('award_number', 'CT-DOT-2025-0001'),
        'title': 'Test Award', 'award_amount': Decimal('25000'),
        'terms_and_conditions': 'Standard terms.',
        'status': Award.Status.ACTIVE,
        'start_date': date.today(),
        'end_date': date.today() + timedelta(days=365),
    }
    defaults.update(kw)
    return Award.objects.create(**defaults)


# ===========================================================================
# Model tests
# ===========================================================================
class AwardModelTests(TestCase):

    def setUp(self):
        self.agency = _agency()
        self.fs = _fs()
        self.org = _org()
        self.officer = _user('officer', User.Role.PROGRAM_OFFICER, agency=self.agency)
        self.applicant = _user('applicant', User.Role.APPLICANT, organization=self.org)
        self.gp = _grant_program(self.agency, self.fs, self.officer)
        self.app = _application(self.gp, self.applicant, self.org)

    def test_create_award(self):
        award = _award(self.app, self.agency, self.gp, self.applicant, self.org)
        self.assertEqual(award.status, Award.Status.ACTIVE)
        self.assertIn('CT-DOT-2025-0001', str(award))

    def test_award_amount(self):
        award = _award(self.app, self.agency, self.gp, self.applicant, self.org)
        self.assertEqual(award.award_amount, Decimal('25000'))


class AwardAmendmentModelTests(TestCase):

    def setUp(self):
        self.agency = _agency()
        self.fs = _fs()
        self.org = _org()
        self.officer = _user('officer', User.Role.PROGRAM_OFFICER, agency=self.agency)
        self.applicant = _user('applicant', User.Role.APPLICANT, organization=self.org)
        self.gp = _grant_program(self.agency, self.fs, self.officer)
        self.app = _application(self.gp, self.applicant, self.org)
        self.award = _award(self.app, self.agency, self.gp, self.applicant, self.org)

    def test_create_amendment(self):
        amendment = AwardAmendment.objects.create(
            award=self.award,
            amendment_number=1,
            amendment_type=AwardAmendment.AmendmentType.BUDGET_MODIFICATION,
            description='Reallocate budget.',
            requested_by=self.officer,
        )
        self.assertEqual(amendment.status, AwardAmendment.Status.DRAFT)
        self.assertIn('Amendment #1', str(amendment))


# ===========================================================================
# View tests
# ===========================================================================
class AwardListViewTests(TestCase):

    def setUp(self):
        self.agency = _agency()
        self.fs = _fs()
        self.org = _org()
        self.officer = _user('officer', User.Role.PROGRAM_OFFICER, agency=self.agency)
        self.applicant = _user('applicant', User.Role.APPLICANT, organization=self.org)
        self.gp = _grant_program(self.agency, self.fs, self.officer)
        self.app = _application(self.gp, self.applicant, self.org)
        self.award = _award(self.app, self.agency, self.gp, self.applicant, self.org)

    def test_list_accessible_by_staff(self):
        self.client.login(username='officer', password='testpass123!')
        resp = self.client.get(reverse('awards:list'))
        self.assertEqual(resp.status_code, 200)

    def test_list_denied_for_applicant(self):
        self.client.login(username='applicant', password='testpass123!')
        resp = self.client.get(reverse('awards:list'))
        self.assertEqual(resp.status_code, 403)


class AwardCreateViewTests(TestCase):

    def setUp(self):
        self.agency = _agency()
        self.fs = _fs()
        self.org = _org()
        self.officer = _user('officer', User.Role.PROGRAM_OFFICER, agency=self.agency)
        self.applicant = _user('applicant', User.Role.APPLICANT, organization=self.org)
        self.gp = _grant_program(self.agency, self.fs, self.officer)
        self.app = _application(self.gp, self.applicant, self.org)

    def test_create_award_form_loads(self):
        self.client.login(username='officer', password='testpass123!')
        url = reverse('awards:create', kwargs={'application_id': self.app.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_create_award_post(self):
        self.client.login(username='officer', password='testpass123!')
        url = reverse('awards:create', kwargs={'application_id': self.app.pk})
        data = {
            'title': 'New Award',
            'award_number': 'CT-DOT-2025-9999',
            'award_amount': '25000.00',
            'terms_and_conditions': 'Standard terms.',
            'start_date': '2025-07-01',
            'end_date': '2026-06-30',
        }
        resp = self.client.post(url, data)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Award.objects.filter(title='New Award').exists())

    def test_create_award_denied_for_applicant(self):
        self.client.login(username='applicant', password='testpass123!')
        url = reverse('awards:create', kwargs={'application_id': self.app.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)


class AwardAmendmentViewTests(TestCase):

    def setUp(self):
        self.agency = _agency()
        self.fs = _fs()
        self.org = _org()
        self.officer = _user('officer', User.Role.PROGRAM_OFFICER, agency=self.agency)
        self.applicant = _user('applicant', User.Role.APPLICANT, organization=self.org)
        self.gp = _grant_program(self.agency, self.fs, self.officer)
        self.app = _application(self.gp, self.applicant, self.org)
        self.award = _award(self.app, self.agency, self.gp, self.applicant, self.org)

    def test_create_amendment(self):
        self.client.login(username='officer', password='testpass123!')
        url = reverse('awards:amendment-create', kwargs={'pk': self.award.pk})
        data = {
            'amendment_type': AwardAmendment.AmendmentType.BUDGET_MODIFICATION,
            'description': 'Budget reallocation request.',
            'old_value': '{"budget": 10000}',
            'new_value': '{"budget": 15000}',
        }
        resp = self.client.post(url, data)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(AwardAmendment.objects.filter(award=self.award).exists())

    def test_approve_amendment(self):
        amendment = AwardAmendment.objects.create(
            award=self.award, amendment_number=1,
            amendment_type=AwardAmendment.AmendmentType.TIME_EXTENSION,
            description='Extend by 3 months.',
            requested_by=self.officer,
            status=AwardAmendment.Status.SUBMITTED,
        )
        self.client.login(username='officer', password='testpass123!')
        url = reverse('awards:amendment-approve', kwargs={'pk': amendment.pk})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)
        amendment.refresh_from_db()
        self.assertEqual(amendment.status, AwardAmendment.Status.APPROVED)
        self.assertEqual(amendment.approved_by, self.officer)

    def test_deny_amendment(self):
        amendment = AwardAmendment.objects.create(
            award=self.award, amendment_number=1,
            amendment_type=AwardAmendment.AmendmentType.SCOPE_CHANGE,
            description='Change scope.',
            requested_by=self.officer,
            status=AwardAmendment.Status.SUBMITTED,
        )
        self.client.login(username='officer', password='testpass123!')
        url = reverse('awards:amendment-deny', kwargs={'pk': amendment.pk})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)
        amendment.refresh_from_db()
        self.assertEqual(amendment.status, AwardAmendment.Status.DENIED)

    def test_approve_already_approved_fails(self):
        amendment = AwardAmendment.objects.create(
            award=self.award, amendment_number=1,
            amendment_type=AwardAmendment.AmendmentType.BUDGET_MODIFICATION,
            description='Already approved.',
            requested_by=self.officer,
            status=AwardAmendment.Status.APPROVED,
        )
        self.client.login(username='officer', password='testpass123!')
        url = reverse('awards:amendment-approve', kwargs={'pk': amendment.pk})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)
        amendment.refresh_from_db()
        # Status should remain approved
        self.assertEqual(amendment.status, AwardAmendment.Status.APPROVED)
