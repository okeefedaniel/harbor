"""Tests for the closeout app: Closeout initiation, checklist management,
closeout completion (sets award status), and permission checks."""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from applications.models import Application
from awards.models import Award
from closeout.models import Closeout, CloseoutChecklist, FundReturn
from core.models import Agency, Organization
from grants.models import FundingSource, GrantProgram

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _full_setup():
    agency = Agency.objects.create(
        name='Dept of Testing', abbreviation='DOT', description='Test agency',
    )
    fs = FundingSource.objects.create(name='State Fund', source_type='state')
    org = Organization.objects.create(name='Test Org', org_type='nonprofit')
    officer = User.objects.create_user(
        username='officer', password='testpass123!', email='officer@example.com',
        role=User.Role.PROGRAM_OFFICER, agency=agency,
    )
    fiscal = User.objects.create_user(
        username='fiscal', password='testpass123!', email='fiscal@example.com',
        role=User.Role.FISCAL_OFFICER, agency=agency,
    )
    applicant = User.objects.create_user(
        username='applicant', password='testpass123!', email='applicant@example.com',
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
        'agency': agency, 'org': org, 'officer': officer, 'fiscal': fiscal,
        'applicant': applicant, 'gp': gp, 'app': app, 'award': award,
    }


# ===========================================================================
# Model tests
# ===========================================================================
class CloseoutModelTests(TestCase):

    def setUp(self):
        self.data = _full_setup()

    def test_create_closeout(self):
        closeout = Closeout.objects.create(
            award=self.data['award'],
            status=Closeout.Status.IN_PROGRESS,
            initiated_by=self.data['officer'],
        )
        self.assertEqual(closeout.status, Closeout.Status.IN_PROGRESS)
        self.assertIn('Closeout', str(closeout))

    def test_create_checklist_item(self):
        closeout = Closeout.objects.create(
            award=self.data['award'],
            status=Closeout.Status.IN_PROGRESS,
            initiated_by=self.data['officer'],
        )
        item = CloseoutChecklist.objects.create(
            closeout=closeout, item_name='Final Report',
            item_description='Submit the final progress report.',
            is_required=True,
        )
        self.assertFalse(item.is_completed)
        self.assertIn('Pending', str(item))

    def test_fund_return_creation(self):
        closeout = Closeout.objects.create(
            award=self.data['award'],
            status=Closeout.Status.IN_PROGRESS,
            initiated_by=self.data['officer'],
        )
        fr = FundReturn.objects.create(
            closeout=closeout,
            amount=Decimal('1000'),
            reason='Unspent funds.',
        )
        self.assertEqual(fr.status, FundReturn.Status.PENDING)
        self.assertIn('$1000', str(fr))


# ===========================================================================
# View tests
# ===========================================================================
class CloseoutInitiateViewTests(TestCase):

    def setUp(self):
        self.data = _full_setup()

    def test_initiate_closeout(self):
        self.client.login(username='officer', password='testpass123!')
        url = reverse('closeout:initiate', kwargs={'award_id': self.data['award'].pk})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 200)  # JSON response
        self.assertTrue(Closeout.objects.filter(award=self.data['award']).exists())
        closeout = Closeout.objects.get(award=self.data['award'])
        self.assertEqual(closeout.status, Closeout.Status.IN_PROGRESS)
        # Default checklist items should be created
        self.assertGreaterEqual(closeout.checklist_items.count(), 5)

    def test_initiate_duplicate_fails(self):
        Closeout.objects.create(
            award=self.data['award'],
            status=Closeout.Status.IN_PROGRESS,
            initiated_by=self.data['officer'],
        )
        self.client.login(username='officer', password='testpass123!')
        url = reverse('closeout:initiate', kwargs={'award_id': self.data['award'].pk})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 400)

    def test_initiate_denied_for_applicant(self):
        self.client.login(username='applicant', password='testpass123!')
        url = reverse('closeout:initiate', kwargs={'award_id': self.data['award'].pk})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 403)


class CloseoutChecklistViewTests(TestCase):

    def setUp(self):
        self.data = _full_setup()
        self.closeout = Closeout.objects.create(
            award=self.data['award'],
            status=Closeout.Status.IN_PROGRESS,
            initiated_by=self.data['officer'],
        )
        self.item = CloseoutChecklist.objects.create(
            closeout=self.closeout, item_name='Final Report',
            is_required=True,
        )

    def test_toggle_checklist_item(self):
        self.client.login(username='officer', password='testpass123!')
        url = reverse('closeout:checklist-toggle', kwargs={'pk': self.item.pk})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)
        self.item.refresh_from_db()
        self.assertTrue(self.item.is_completed)
        self.assertIsNotNone(self.item.completed_at)

    def test_toggle_back_to_incomplete(self):
        self.item.is_completed = True
        self.item.completed_by = self.data['officer']
        self.item.completed_at = timezone.now()
        self.item.save()
        self.client.login(username='officer', password='testpass123!')
        url = reverse('closeout:checklist-toggle', kwargs={'pk': self.item.pk})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)
        self.item.refresh_from_db()
        self.assertFalse(self.item.is_completed)

    def test_toggle_denied_for_applicant(self):
        self.client.login(username='applicant', password='testpass123!')
        url = reverse('closeout:checklist-toggle', kwargs={'pk': self.item.pk})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 403)


class CloseoutCompleteViewTests(TestCase):

    def setUp(self):
        self.data = _full_setup()
        self.closeout = Closeout.objects.create(
            award=self.data['award'],
            status=Closeout.Status.IN_PROGRESS,
            initiated_by=self.data['officer'],
        )
        self.item1 = CloseoutChecklist.objects.create(
            closeout=self.closeout, item_name='Final Report', is_required=True,
        )
        self.item2 = CloseoutChecklist.objects.create(
            closeout=self.closeout, item_name='Equipment Inventory', is_required=False,
        )

    def test_complete_fails_with_incomplete_required_items(self):
        self.client.login(username='officer', password='testpass123!')
        url = reverse('closeout:complete', kwargs={'pk': self.closeout.pk})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)
        self.closeout.refresh_from_db()
        # Should NOT be completed
        self.assertNotEqual(self.closeout.status, Closeout.Status.COMPLETED)

    def test_complete_succeeds_when_required_items_done(self):
        self.item1.is_completed = True
        self.item1.completed_by = self.data['officer']
        self.item1.completed_at = timezone.now()
        self.item1.save()
        self.client.login(username='officer', password='testpass123!')
        url = reverse('closeout:complete', kwargs={'pk': self.closeout.pk})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 302)
        self.closeout.refresh_from_db()
        self.assertEqual(self.closeout.status, Closeout.Status.COMPLETED)
        self.assertIsNotNone(self.closeout.completed_at)
        # Award should also be completed
        self.data['award'].refresh_from_db()
        self.assertEqual(self.data['award'].status, Award.Status.COMPLETED)

    def test_complete_denied_for_applicant(self):
        self.client.login(username='applicant', password='testpass123!')
        url = reverse('closeout:complete', kwargs={'pk': self.closeout.pk})
        resp = self.client.post(url)
        self.assertEqual(resp.status_code, 403)


class CloseoutDetailViewTests(TestCase):

    def setUp(self):
        self.data = _full_setup()
        self.closeout = Closeout.objects.create(
            award=self.data['award'],
            status=Closeout.Status.IN_PROGRESS,
            initiated_by=self.data['officer'],
        )

    def test_detail_accessible_by_staff(self):
        self.client.login(username='officer', password='testpass123!')
        url = reverse('closeout:detail', kwargs={'pk': self.closeout.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['closeout'], self.closeout)

    def test_detail_denied_for_applicant(self):
        self.client.login(username='applicant', password='testpass123!')
        url = reverse('closeout:detail', kwargs={'pk': self.closeout.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)
