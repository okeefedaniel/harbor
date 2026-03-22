"""Tests for the financial app: Budget CRUD, DrawdownRequest flow,
Transaction creation, and permission checks (FiscalOfficer only)."""

import os
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from applications.models import Application
from awards.models import Award
from core.models import Agency, Organization
from financial.models import Budget, BudgetLineItem, DrawdownRequest, Transaction
from grants.models import FundingSource, GrantProgram

User = get_user_model()

TEST_PASSWORD = os.environ.get('TEST_PASSWORD', 'testpass123!')


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
        username=username, password=TEST_PASSWORD, email=f'{username}@example.com',
        role=role, agency=agency, organization=organization, **kw,
    )


def _full_setup():
    """Create agency, funding source, org, users, grant program, application, and award."""
    agency = _agency()
    fs = _fs()
    org = _org()
    officer = _user('officer', User.Role.PROGRAM_OFFICER, agency=agency)
    fiscal = _user('fiscal', User.Role.FISCAL_OFFICER, agency=agency)
    applicant = _user('applicant', User.Role.APPLICANT, organization=org)
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
        'agency': agency, 'org': org, 'officer': officer, 'fiscal': fiscal,
        'applicant': applicant, 'gp': gp, 'app': app, 'award': award,
    }


# ===========================================================================
# Model tests
# ===========================================================================
class BudgetModelTests(TestCase):

    def setUp(self):
        self.data = _full_setup()

    def test_create_budget(self):
        budget = Budget.objects.create(
            award=self.data['award'], fiscal_year=2025,
            total_amount=Decimal('25000'),
        )
        self.assertEqual(budget.status, Budget.Status.DRAFT)
        self.assertIn('FY2025', str(budget))

    def test_create_budget_line_item(self):
        budget = Budget.objects.create(
            award=self.data['award'], fiscal_year=2025,
            total_amount=Decimal('25000'),
        )
        item = BudgetLineItem.objects.create(
            budget=budget, category=BudgetLineItem.Category.PERSONNEL,
            description='Staff salaries', amount=Decimal('15000'),
        )
        self.assertIn('Personnel', str(item))


class DrawdownRequestModelTests(TestCase):

    def setUp(self):
        self.data = _full_setup()

    def test_create_drawdown(self):
        dr = DrawdownRequest.objects.create(
            award=self.data['award'], request_number='DR-001',
            amount=Decimal('5000'),
            period_start=date.today(), period_end=date.today() + timedelta(days=30),
            submitted_by=self.data['applicant'],
        )
        self.assertEqual(dr.status, DrawdownRequest.Status.DRAFT)
        self.assertIn('DR-001', str(dr))


class TransactionModelTests(TestCase):

    def setUp(self):
        self.data = _full_setup()

    def test_create_transaction(self):
        txn = Transaction.objects.create(
            award=self.data['award'],
            transaction_type=Transaction.TransactionType.PAYMENT,
            amount=Decimal('5000'),
            transaction_date=date.today(),
            created_by=self.data['fiscal'],
        )
        self.assertIn('Payment', str(txn))
        self.assertEqual(txn.amount, Decimal('5000'))


# ===========================================================================
# View tests
# ===========================================================================
class BudgetViewTests(TestCase):

    def setUp(self):
        self.data = _full_setup()

    def test_budget_create_accessible_by_staff(self):
        self.client.force_login(self.data['officer'])
        url = reverse('financial:budget-create', kwargs={'award_id': self.data['award'].pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_budget_create_denied_for_applicant(self):
        self.client.force_login(self.data['applicant'])
        url = reverse('financial:budget-create', kwargs={'award_id': self.data['award'].pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)

    def test_budget_create_post(self):
        self.client.force_login(self.data['officer'])
        url = reverse('financial:budget-create', kwargs={'award_id': self.data['award'].pk})
        data = {'fiscal_year': '2025', 'total_amount': '25000.00'}
        resp = self.client.post(url, data)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Budget.objects.filter(award=self.data['award']).exists())

    def test_budget_detail(self):
        budget = Budget.objects.create(
            award=self.data['award'], fiscal_year=2025,
            total_amount=Decimal('25000'),
        )
        self.client.force_login(self.data['officer'])
        url = reverse('financial:budget-detail', kwargs={'pk': budget.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)


class DrawdownViewTests(TestCase):

    def setUp(self):
        self.data = _full_setup()

    def test_drawdown_create(self):
        self.client.force_login(self.data['applicant'])
        url = reverse('financial:drawdown-create', kwargs={'award_id': self.data['award'].pk})
        data = {
            'amount': '5000.00',
            'period_start': '2025-07-01',
            'period_end': '2025-07-31',
            'description': 'July expenses',
        }
        resp = self.client.post(url, data)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(DrawdownRequest.objects.filter(award=self.data['award']).exists())

    def test_drawdown_list(self):
        self.client.force_login(self.data['applicant'])
        resp = self.client.get(reverse('financial:drawdown-list'))
        self.assertEqual(resp.status_code, 200)


class DrawdownApproveViewTests(TestCase):

    def setUp(self):
        self.data = _full_setup()
        self.drawdown = DrawdownRequest.objects.create(
            award=self.data['award'], request_number='DR-001',
            amount=Decimal('5000'),
            period_start=date.today(), period_end=date.today() + timedelta(days=30),
            submitted_by=self.data['applicant'],
            status=DrawdownRequest.Status.SUBMITTED,
        )

    def test_approve_by_fiscal_officer(self):
        self.client.force_login(self.data['fiscal'])
        url = reverse('financial:drawdown-approve', kwargs={'pk': self.drawdown.pk})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200)  # JSON response
        self.drawdown.refresh_from_db()
        self.assertEqual(self.drawdown.status, DrawdownRequest.Status.APPROVED)

    def test_approve_denied_for_applicant(self):
        self.client.force_login(self.data['applicant'])
        url = reverse('financial:drawdown-approve', kwargs={'pk': self.drawdown.pk})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 403)

    def test_approve_not_submitted_fails(self):
        self.drawdown.status = DrawdownRequest.Status.DRAFT
        self.drawdown.save()
        self.client.force_login(self.data['fiscal'])
        url = reverse('financial:drawdown-approve', kwargs={'pk': self.drawdown.pk})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 400)


class DrawdownDenyViewTests(TestCase):

    def setUp(self):
        self.data = _full_setup()
        self.drawdown = DrawdownRequest.objects.create(
            award=self.data['award'], request_number='DR-002',
            amount=Decimal('3000'),
            period_start=date.today(), period_end=date.today() + timedelta(days=30),
            submitted_by=self.data['applicant'],
            status=DrawdownRequest.Status.SUBMITTED,
        )

    def test_deny_by_fiscal_officer(self):
        self.client.force_login(self.data['fiscal'])
        url = reverse('financial:drawdown-deny', kwargs={'pk': self.drawdown.pk})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)
        self.drawdown.refresh_from_db()
        self.assertEqual(self.drawdown.status, DrawdownRequest.Status.DENIED)

    def test_deny_denied_for_applicant(self):
        self.client.force_login(self.data['applicant'])
        url = reverse('financial:drawdown-deny', kwargs={'pk': self.drawdown.pk})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 403)


class TransactionViewTests(TestCase):

    def setUp(self):
        self.data = _full_setup()

    def test_transaction_create_by_fiscal(self):
        self.client.force_login(self.data['fiscal'])
        url = reverse('financial:transaction-create', kwargs={'award_id': self.data['award'].pk})
        data = {
            'transaction_type': 'payment',
            'amount': '5000.00',
            'transaction_date': '2025-07-15',
            'description': 'Payment for services.',
        }
        resp = self.client.post(url, data)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Transaction.objects.filter(award=self.data['award']).exists())

    def test_transaction_create_denied_for_applicant(self):
        self.client.force_login(self.data['applicant'])
        url = reverse('financial:transaction-create', kwargs={'award_id': self.data['award'].pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)

    def test_transaction_list_accessible_by_staff(self):
        self.client.force_login(self.data['officer'])
        resp = self.client.get(reverse('financial:transaction-list'))
        self.assertEqual(resp.status_code, 200)
