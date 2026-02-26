from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Avg
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import CreateView, DetailView, TemplateView

from core.mixins import AgencyStaffRequiredMixin, ReviewerRequiredMixin

from applications.models import Application

from .forms import ReviewAssignmentForm, ReviewScoreForm
from .models import (
    ReviewAssignment,
    ReviewScore,
    ReviewSummary,
    RubricCriterion,
)


# ---------------------------------------------------------------------------
# Reviewer dashboard
# ---------------------------------------------------------------------------
class ReviewDashboardView(ReviewerRequiredMixin, TemplateView):
    """Dashboard showing all review assignments for the current reviewer."""

    template_name = 'reviews/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        assignments = ReviewAssignment.objects.filter(
            reviewer=self.request.user,
        ).select_related(
            'application', 'application__grant_program',
            'application__organization', 'rubric',
        ).prefetch_related('scores')

        pending = assignments.filter(
            status__in=[
                ReviewAssignment.Status.ASSIGNED,
                ReviewAssignment.Status.IN_PROGRESS,
            ],
        )
        completed = assignments.filter(
            status=ReviewAssignment.Status.COMPLETED,
        )

        context['assignments'] = assignments
        context['pending_assignments'] = pending
        context['completed_assignments'] = completed
        context['total_assigned'] = assignments.count()
        context['completed'] = completed.count()
        context['pending'] = pending.count()
        return context


# ---------------------------------------------------------------------------
# Review application (score form)
# ---------------------------------------------------------------------------
class ReviewApplicationView(ReviewerRequiredMixin, DetailView):
    """Display rubric criteria and allow the reviewer to enter scores.

    The ``pk`` in the URL refers to the :model:`applications.Application`.
    The view locates the matching :model:`reviews.ReviewAssignment` for the
    current user and supplies the rubric criteria together with any
    previously saved scores.
    """

    model = Application
    template_name = 'reviews/review_form.html'
    context_object_name = 'application'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        application = self.object

        assignment = get_object_or_404(
            ReviewAssignment,
            application=application,
            reviewer=self.request.user,
        )
        context['assignment'] = assignment

        criteria = assignment.rubric.criteria.all()
        existing_scores = {
            score.criterion_id: score
            for score in assignment.scores.all()
        }

        # Build a list of (criterion, form) tuples for the template
        criteria_forms = []
        for criterion in criteria:
            existing = existing_scores.get(criterion.pk)
            initial = {
                'criterion_id': criterion.pk,
            }
            if existing:
                initial['score'] = existing.score
                initial['comment'] = existing.comment

            form = ReviewScoreForm(initial=initial, prefix=str(criterion.pk))
            criteria_forms.append((criterion, form))

        context['criteria_forms'] = criteria_forms
        return context


# ---------------------------------------------------------------------------
# Submit review scores
# ---------------------------------------------------------------------------
class SubmitReviewView(ReviewerRequiredMixin, View):
    """POST-only view that saves scores for all rubric criteria.

    The ``pk`` in the URL refers to the :model:`applications.Application`.
    """

    http_method_names = ['post']

    def post(self, request, pk):
        application = get_object_or_404(Application, pk=pk)
        assignment = get_object_or_404(
            ReviewAssignment,
            application=application,
            reviewer=request.user,
        )

        criteria = assignment.rubric.criteria.all()
        forms = []
        all_valid = True

        for criterion in criteria:
            form = ReviewScoreForm(request.POST, prefix=str(criterion.pk))
            if form.is_valid():
                forms.append(form)
            else:
                all_valid = False

        if not all_valid:
            messages.error(request, _('Please correct the errors in your scores.'))
            return redirect('reviews:review-application', pk=application.pk)

        with transaction.atomic():
            for form in forms:
                criterion_id = form.cleaned_data['criterion_id']
                ReviewScore.objects.update_or_create(
                    assignment=assignment,
                    criterion_id=criterion_id,
                    defaults={
                        'score': form.cleaned_data['score'],
                        'comment': form.cleaned_data.get('comment', ''),
                    },
                )

            assignment.status = ReviewAssignment.Status.COMPLETED
            assignment.completed_at = timezone.now()
            assignment.save(update_fields=['status', 'completed_at'])

            # Auto-create/update ReviewSummary when all assignments are done
            all_assignments = ReviewAssignment.objects.filter(
                application=application,
            )
            completed = all_assignments.filter(
                status=ReviewAssignment.Status.COMPLETED,
            )
            if completed.count() == all_assignments.count():
                avg = ReviewScore.objects.filter(
                    assignment__application=application,
                    assignment__status=ReviewAssignment.Status.COMPLETED,
                ).aggregate(avg=Avg('score'))['avg'] or 0

                ReviewSummary.objects.update_or_create(
                    application=application,
                    defaults={
                        'average_score': avg,
                        'total_reviews': completed.count(),
                    },
                )

        messages.success(request, _('Your review has been submitted successfully.'))
        return redirect('reviews:dashboard')


# ---------------------------------------------------------------------------
# Review summary
# ---------------------------------------------------------------------------
class ReviewSummaryView(AgencyStaffRequiredMixin, DetailView):
    """View the aggregated review summary for an application.

    The ``pk`` in the URL refers to the :model:`applications.Application`.
    """

    model = Application
    template_name = 'reviews/summary.html'
    context_object_name = 'application'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        application = self.object

        context['summary'] = ReviewSummary.objects.filter(
            application=application,
        ).first()

        assignments = ReviewAssignment.objects.filter(
            application=application,
            status=ReviewAssignment.Status.COMPLETED,
        ).select_related('reviewer', 'rubric').prefetch_related(
            'scores', 'scores__criterion',
        )
        context['assignments'] = assignments

        return context


# ---------------------------------------------------------------------------
# Review Assignment Create (staff assigns reviewers)
# ---------------------------------------------------------------------------
class ReviewAssignmentCreateView(AgencyStaffRequiredMixin, CreateView):
    """Assign a reviewer to evaluate an application.

    Only accessible by agency staff.  The ``application_pk`` URL kwarg
    identifies the application to be reviewed.
    """

    model = ReviewAssignment
    form_class = ReviewAssignmentForm
    template_name = 'reviews/assign_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.application = get_object_or_404(
            Application.objects.select_related('grant_program'),
            pk=kwargs['application_pk'],
        )
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['application'] = self.application
        return kwargs

    def form_valid(self, form):
        form.instance.application = self.application
        messages.success(
            self.request,
            _('Reviewer %(reviewer)s assigned successfully.') % {'reviewer': form.instance.reviewer},
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['application'] = self.application
        return context

    def get_success_url(self):
        return reverse_lazy(
            'reviews:summary', kwargs={'pk': self.application.pk}
        )
