"""Tests for the reviews app: ReviewAssignment creation, score submission,
review summary generation, and permission checks."""

import os
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from applications.models import Application
from core.models import Agency, Organization
from grants.models import FundingSource, GrantProgram
from reviews.models import (
    ReviewAssignment,
    ReviewRubric,
    ReviewScore,
    ReviewSummary,
    RubricCriterion,
)

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


def _org():
    return Organization.objects.create(name='Test Org', org_type='nonprofit')


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
        'posting_date': timezone.now(), 'created_by': created_by,
    }
    defaults.update(kw)
    return GrantProgram.objects.create(**defaults)


def _application(gp, applicant, org, **kw):
    defaults = {
        'grant_program': gp, 'applicant': applicant, 'organization': org,
        'project_title': 'Test Project', 'project_description': 'Desc',
        'requested_amount': Decimal('10000'),
        'proposed_start_date': date.today(),
        'proposed_end_date': date.today() + timedelta(days=365),
        'status': Application.Status.SUBMITTED,
    }
    defaults.update(kw)
    return Application.objects.create(**defaults)


# ===========================================================================
# Model tests
# ===========================================================================
class ReviewAssignmentModelTests(TestCase):

    def setUp(self):
        self.agency = _agency()
        self.fs = _fs()
        self.org = _org()
        self.officer = _user('officer', User.Role.PROGRAM_OFFICER, agency=self.agency)
        self.reviewer = _user('reviewer', User.Role.REVIEWER)
        self.applicant = _user('applicant', User.Role.APPLICANT, organization=self.org)
        self.gp = _grant_program(self.agency, self.fs, self.officer)
        self.app = _application(self.gp, self.applicant, self.org)
        self.rubric = ReviewRubric.objects.create(
            grant_program=self.gp, name='Default Rubric', created_by=self.officer,
        )

    def test_create_assignment(self):
        assignment = ReviewAssignment.objects.create(
            application=self.app, reviewer=self.reviewer, rubric=self.rubric,
        )
        self.assertEqual(assignment.status, ReviewAssignment.Status.ASSIGNED)
        self.assertIn('reviewer', str(assignment))

    def test_str(self):
        assignment = ReviewAssignment.objects.create(
            application=self.app, reviewer=self.reviewer, rubric=self.rubric,
        )
        self.assertIn('Review:', str(assignment))


class ReviewScoreModelTests(TestCase):

    def setUp(self):
        self.agency = _agency()
        self.fs = _fs()
        self.org = _org()
        self.officer = _user('officer', User.Role.PROGRAM_OFFICER, agency=self.agency)
        self.reviewer = _user('reviewer', User.Role.REVIEWER)
        self.applicant = _user('applicant', User.Role.APPLICANT, organization=self.org)
        self.gp = _grant_program(self.agency, self.fs, self.officer)
        self.app = _application(self.gp, self.applicant, self.org)
        self.rubric = ReviewRubric.objects.create(
            grant_program=self.gp, name='Rubric', created_by=self.officer,
        )
        self.criterion = RubricCriterion.objects.create(
            rubric=self.rubric, name='Quality', max_score=10, weight=Decimal('1.0'),
        )
        self.assignment = ReviewAssignment.objects.create(
            application=self.app, reviewer=self.reviewer, rubric=self.rubric,
        )

    def test_create_score(self):
        score = ReviewScore.objects.create(
            assignment=self.assignment, criterion=self.criterion,
            score=8, comment='Good quality.',
        )
        self.assertEqual(score.score, 8)
        self.assertIn('Quality', str(score))


class ReviewSummaryModelTests(TestCase):

    def setUp(self):
        self.agency = _agency()
        self.fs = _fs()
        self.org = _org()
        self.officer = _user('officer', User.Role.PROGRAM_OFFICER, agency=self.agency)
        self.applicant = _user('applicant', User.Role.APPLICANT, organization=self.org)
        self.gp = _grant_program(self.agency, self.fs, self.officer)
        self.app = _application(self.gp, self.applicant, self.org)

    def test_create_summary(self):
        summary = ReviewSummary.objects.create(
            application=self.app, average_score=Decimal('7.50'),
            total_reviews=3, recommendation=ReviewSummary.Recommendation.FUND,
        )
        self.assertEqual(summary.total_reviews, 3)
        self.assertIn('7.50', str(summary))


# ===========================================================================
# View tests
# ===========================================================================
class ReviewDashboardViewTests(TestCase):

    def setUp(self):
        self.agency = _agency()
        self.reviewer = _user('reviewer', User.Role.REVIEWER)
        self.applicant = _user('applicant', User.Role.APPLICANT)

    def test_dashboard_accessible_by_reviewer(self):
        self.client.force_login(self.reviewer)
        resp = self.client.get(reverse('reviews:dashboard'))
        self.assertEqual(resp.status_code, 200)

    def test_dashboard_denied_for_applicant(self):
        self.client.force_login(self.applicant)
        resp = self.client.get(reverse('reviews:dashboard'))
        self.assertEqual(resp.status_code, 403)


class SubmitReviewViewTests(TestCase):

    def setUp(self):
        self.agency = _agency()
        self.fs = _fs()
        self.org = _org()
        self.officer = _user('officer', User.Role.PROGRAM_OFFICER, agency=self.agency)
        self.reviewer = _user('reviewer', User.Role.REVIEWER)
        self.applicant = _user('applicant', User.Role.APPLICANT, organization=self.org)
        self.gp = _grant_program(self.agency, self.fs, self.officer)
        self.app = _application(self.gp, self.applicant, self.org)
        self.rubric = ReviewRubric.objects.create(
            grant_program=self.gp, name='Rubric', created_by=self.officer,
        )
        self.c1 = RubricCriterion.objects.create(
            rubric=self.rubric, name='Quality', max_score=10, weight=Decimal('1.0'), order=1,
        )
        self.c2 = RubricCriterion.objects.create(
            rubric=self.rubric, name='Feasibility', max_score=10, weight=Decimal('1.0'), order=2,
        )
        self.assignment = ReviewAssignment.objects.create(
            application=self.app, reviewer=self.reviewer, rubric=self.rubric,
        )

    def test_submit_scores(self):
        self.client.force_login(self.reviewer)
        url = reverse('reviews:submit-review', kwargs={'pk': self.app.pk})
        data = {
            f'{self.c1.pk}-criterion_id': str(self.c1.pk),
            f'{self.c1.pk}-score': '8',
            f'{self.c1.pk}-comment': 'Good',
            f'{self.c2.pk}-criterion_id': str(self.c2.pk),
            f'{self.c2.pk}-score': '7',
            f'{self.c2.pk}-comment': 'OK',
        }
        resp = self.client.post(url, data)
        self.assertEqual(resp.status_code, 302)
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, ReviewAssignment.Status.COMPLETED)
        self.assertEqual(ReviewScore.objects.filter(assignment=self.assignment).count(), 2)

    def test_submit_review_creates_summary_when_all_done(self):
        """When the only assignment completes, a ReviewSummary is created."""
        self.client.force_login(self.reviewer)
        url = reverse('reviews:submit-review', kwargs={'pk': self.app.pk})
        data = {
            f'{self.c1.pk}-criterion_id': str(self.c1.pk),
            f'{self.c1.pk}-score': '9',
            f'{self.c1.pk}-comment': '',
            f'{self.c2.pk}-criterion_id': str(self.c2.pk),
            f'{self.c2.pk}-score': '7',
            f'{self.c2.pk}-comment': '',
        }
        self.client.post(url, data)
        self.assertTrue(ReviewSummary.objects.filter(application=self.app).exists())
        summary = ReviewSummary.objects.get(application=self.app)
        self.assertEqual(summary.total_reviews, 1)


class ReviewSummaryViewTests(TestCase):

    def setUp(self):
        self.agency = _agency()
        self.fs = _fs()
        self.org = _org()
        self.officer = _user('officer', User.Role.PROGRAM_OFFICER, agency=self.agency)
        self.applicant = _user('applicant', User.Role.APPLICANT, organization=self.org)
        self.gp = _grant_program(self.agency, self.fs, self.officer)
        self.app = _application(self.gp, self.applicant, self.org)

    def test_summary_view_accessible_by_staff(self):
        self.client.force_login(self.officer)
        url = reverse('reviews:summary', kwargs={'pk': self.app.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_summary_view_denied_for_applicant(self):
        self.client.force_login(self.applicant)
        url = reverse('reviews:summary', kwargs={'pk': self.app.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)
