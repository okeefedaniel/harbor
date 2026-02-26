import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


# ---------------------------------------------------------------------------
# ReviewRubric
# ---------------------------------------------------------------------------
class ReviewRubric(models.Model):
    """Scoring rubric template attached to a grant program."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    grant_program = models.ForeignKey(
        'grants.GrantProgram',
        on_delete=models.CASCADE,
        related_name='rubrics',
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_rubrics',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = _('Review Rubric')
        verbose_name_plural = _('Review Rubrics')

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# RubricCriterion
# ---------------------------------------------------------------------------
class RubricCriterion(models.Model):
    """Individual scoring criterion within a rubric."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rubric = models.ForeignKey(
        ReviewRubric,
        on_delete=models.CASCADE,
        related_name='criteria',
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    max_score = models.IntegerField()
    weight = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=1.0,
    )
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']
        verbose_name = _('Rubric Criterion')
        verbose_name_plural = _('Rubric Criteria')

    def __str__(self):
        return f"{self.rubric.name} - {self.name}"


# ---------------------------------------------------------------------------
# ReviewAssignment
# ---------------------------------------------------------------------------
class ReviewAssignment(models.Model):
    """Assignment of a reviewer to evaluate an application using a rubric."""

    class Status(models.TextChoices):
        ASSIGNED = 'assigned', _('Assigned')
        IN_PROGRESS = 'in_progress', _('In Progress')
        COMPLETED = 'completed', _('Completed')
        RECUSED = 'recused', _('Recused')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        'applications.Application',
        on_delete=models.CASCADE,
        related_name='review_assignments',
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='review_assignments',
    )
    rubric = models.ForeignKey(
        ReviewRubric,
        on_delete=models.CASCADE,
        related_name='assignments',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ASSIGNED,
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    conflict_of_interest = models.BooleanField(default=False)
    conflict_notes = models.TextField(blank=True)

    class Meta:
        verbose_name = _('Review Assignment')
        verbose_name_plural = _('Review Assignments')

    def __str__(self):
        return f"Review: {self.reviewer} -> {self.application}"


# ---------------------------------------------------------------------------
# ReviewScore
# ---------------------------------------------------------------------------
class ReviewScore(models.Model):
    """Score given by a reviewer for a single criterion."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assignment = models.ForeignKey(
        ReviewAssignment,
        on_delete=models.CASCADE,
        related_name='scores',
    )
    criterion = models.ForeignKey(
        RubricCriterion,
        on_delete=models.CASCADE,
        related_name='scores',
    )
    score = models.IntegerField()
    comment = models.TextField(blank=True)

    class Meta:
        unique_together = ['assignment', 'criterion']
        verbose_name = _('Review Score')
        verbose_name_plural = _('Review Scores')

    def __str__(self):
        return f"{self.assignment} - {self.criterion.name}: {self.score}"


# ---------------------------------------------------------------------------
# ReviewSummary
# ---------------------------------------------------------------------------
class ReviewSummary(models.Model):
    """Aggregated review outcome for an application."""

    class Recommendation(models.TextChoices):
        FUND = 'fund', _('Fund')
        DO_NOT_FUND = 'do_not_fund', _('Do Not Fund')
        FUND_WITH_CONDITIONS = 'fund_with_conditions', _('Fund with Conditions')
        NEEDS_DISCUSSION = 'needs_discussion', _('Needs Discussion')

    class RiskLevel(models.TextChoices):
        LOW = 'low', _('Low')
        MEDIUM = 'medium', _('Medium')
        HIGH = 'high', _('High')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.OneToOneField(
        'applications.Application',
        on_delete=models.CASCADE,
        related_name='review_summary',
    )
    average_score = models.DecimalField(max_digits=5, decimal_places=2)
    total_reviews = models.IntegerField(default=0)
    recommendation = models.CharField(
        max_length=25,
        choices=Recommendation.choices,
        blank=True,
    )
    risk_level = models.CharField(
        max_length=10,
        choices=RiskLevel.choices,
        blank=True,
    )
    risk_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Review Summary')
        verbose_name_plural = _('Review Summaries')

    def __str__(self):
        return f"Summary: {self.application} ({self.average_score})"
