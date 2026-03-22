"""Tests for the portal app: public-facing views including home page,
opportunity listing, opportunity detail, about, and help pages."""

import os
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Agency
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


def _funding_source():
    return FundingSource.objects.create(name='State Fund', source_type='state')


def _user(username, role, agency=None, **kw):
    return User.objects.create_user(
        username=username, password=TEST_PASSWORD, email=f'{username}@example.com',
        role=role, agency=agency, **kw,
    )


def _published_program(agency, fs, created_by, **kw):
    defaults = {
        'agency': agency, 'title': 'Public Grant', 'description': 'Desc',
        'funding_source': fs, 'total_funding': Decimal('500000'),
        'min_award': Decimal('5000'), 'max_award': Decimal('50000'),
        'fiscal_year': '2025-2026', 'duration_months': 12,
        'application_deadline': timezone.now() + timedelta(days=30),
        'posting_date': timezone.now(),
        'created_by': created_by,
        'is_published': True,
        'status': GrantProgram.Status.POSTED,
    }
    defaults.update(kw)
    return GrantProgram.objects.create(**defaults)


# ===========================================================================
# View tests
# ===========================================================================
class HomeViewTests(TestCase):
    """Test the public landing page."""

    def test_home_page_loads(self):
        resp = self.client.get(reverse('portal:home'))
        self.assertEqual(resp.status_code, 200)

    def test_home_shows_recent_opportunities(self):
        agency = _agency()
        fs = _funding_source()
        officer = _user('officer', User.Role.PROGRAM_OFFICER, agency=agency)
        _published_program(agency, fs, officer, title='Visible Grant')
        resp = self.client.get(reverse('portal:home'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('recent_opportunities', resp.context)
        self.assertEqual(resp.context['active_programs_count'], 1)

    def test_home_excludes_unpublished(self):
        agency = _agency()
        fs = _funding_source()
        officer = _user('officer', User.Role.PROGRAM_OFFICER, agency=agency)
        _published_program(agency, fs, officer, is_published=False,
                           status=GrantProgram.Status.DRAFT, title='Hidden Grant')
        resp = self.client.get(reverse('portal:home'))
        self.assertEqual(resp.context['active_programs_count'], 0)


class OpportunityListViewTests(TestCase):
    """Test the public opportunity listing."""

    def setUp(self):
        self.agency = _agency()
        self.fs = _funding_source()
        self.officer = _user('officer', User.Role.PROGRAM_OFFICER, agency=self.agency)
        self.program = _published_program(self.agency, self.fs, self.officer)

    def test_list_loads(self):
        resp = self.client.get(reverse('portal:opportunities'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context['opportunities']), 1)

    def test_list_excludes_unpublished(self):
        GrantProgram.objects.create(
            agency=self.agency, title='Draft Program', description='Desc',
            funding_source=self.fs, total_funding=Decimal('100000'),
            min_award=Decimal('1000'), max_award=Decimal('10000'),
            fiscal_year='2025-2026', duration_months=6,
            application_deadline=timezone.now() + timedelta(days=30),
            posting_date=timezone.now(), created_by=self.officer,
            is_published=False, status=GrantProgram.Status.DRAFT,
        )
        resp = self.client.get(reverse('portal:opportunities'))
        # Should still only show the one published program
        self.assertEqual(len(resp.context['opportunities']), 1)

    def test_filter_by_grant_type(self):
        resp = self.client.get(
            reverse('portal:opportunities') + '?grant_type=competitive'
        )
        self.assertEqual(resp.status_code, 200)


class OpportunityDetailViewTests(TestCase):
    """Test the public opportunity detail page."""

    def setUp(self):
        self.agency = _agency()
        self.fs = _funding_source()
        self.officer = _user('officer', User.Role.PROGRAM_OFFICER, agency=self.agency)
        self.program = _published_program(self.agency, self.fs, self.officer)

    def test_detail_loads(self):
        resp = self.client.get(
            reverse('portal:opportunity-detail', kwargs={'pk': self.program.pk})
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['opportunity'], self.program)

    def test_detail_404_for_unpublished(self):
        unpublished = GrantProgram.objects.create(
            agency=self.agency, title='Hidden', description='Desc',
            funding_source=self.fs, total_funding=Decimal('100000'),
            min_award=Decimal('1000'), max_award=Decimal('10000'),
            fiscal_year='2025-2026', duration_months=6,
            application_deadline=timezone.now() + timedelta(days=30),
            posting_date=timezone.now(), created_by=self.officer,
            is_published=False, status=GrantProgram.Status.DRAFT,
        )
        resp = self.client.get(
            reverse('portal:opportunity-detail', kwargs={'pk': unpublished.pk})
        )
        self.assertEqual(resp.status_code, 404)


class StaticPageViewTests(TestCase):
    """Test the about and help static pages."""

    def test_about_page_loads(self):
        resp = self.client.get(reverse('portal:about'))
        self.assertEqual(resp.status_code, 200)

    def test_help_page_loads(self):
        resp = self.client.get(reverse('portal:help'))
        self.assertEqual(resp.status_code, 200)
