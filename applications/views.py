import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponseForbidden, JsonResponse

from core.audit import log_audit
from core.export import CSVExportMixin
from core.scanning import scan_file
from core.filters import ApplicationFilter
from core.mixins import AgencyStaffRequiredMixin, SortableListMixin
from core.models import AuditLog
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _, gettext_lazy as _lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from core.notifications import (
    notify_application_status_changed,
    notify_application_submitted,
)
from grants.models import GrantProgram

from .forms import (
    ApplicationAssignmentForm,
    ApplicationCommentForm,
    ApplicationDocumentForm,
    ApplicationForm,
    StaffDocumentForm,
    StatusChangeForm,
)
from .models import (
    Application,
    ApplicationAssignment,
    ApplicationComplianceItem,
    ApplicationStatusHistory,
    StaffDocument,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Application list (agency staff)
# ---------------------------------------------------------------------------
class ApplicationListView(AgencyStaffRequiredMixin, SortableListMixin, CSVExportMixin, ListView):
    """All applications visible to agency staff, filterable by program and status.

    If the requesting user is an applicant, they are redirected to the
    ``my-applications`` view instead.
    """

    model = Application
    template_name = 'applications/application_list.html'
    context_object_name = 'applications'
    paginate_by = 20
    csv_filename = 'applications.csv'
    csv_columns = [
        (_lazy('Application ID'), 'id'),
        (_lazy('Project Title'), 'project_title'),
        (_lazy('Applicant'), lambda o: o.applicant.get_full_name() or o.applicant.username),
        (_lazy('Organization'), 'organization.name'),
        (_lazy('Grant Program'), 'grant_program.title'),
        (_lazy('Status'), 'get_status_display'),
        (_lazy('Requested Amount'), 'requested_amount'),
        (_lazy('Submitted'), 'submitted_at'),
    ]

    sortable_fields = {
        'project_title': 'project_title',
        'applicant': 'applicant__last_name',
        'status': 'status',
        'requested_amount': 'requested_amount',
        'submitted_at': 'submitted_at',
    }
    default_sort = 'submitted_at'
    default_dir = 'desc'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role == 'applicant':
            return redirect('applications:my-applications')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = Application.objects.select_related(
            'grant_program', 'applicant', 'organization',
        )

        grant_program = self.request.GET.get('grant_program')
        if grant_program:
            qs = qs.filter(grant_program_id=grant_program)

        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)

        self.filterset = ApplicationFilter(self.request.GET, queryset=qs)
        return self.apply_sorting(self.filterset.qs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['grant_programs'] = GrantProgram.objects.all()
        context['status_choices'] = Application.Status.choices
        context['current_program'] = self.request.GET.get('grant_program', '')
        context['current_status'] = self.request.GET.get('status', '')
        context['view_mode'] = self.request.GET.get('view', 'list')
        context['filter'] = self.filterset

        # Build a dict mapping application_id → active assignment for the
        # "Assigned To" column and Claim/Assign buttons.
        active_assignments = ApplicationAssignment.objects.filter(
            status__in=[
                ApplicationAssignment.Status.ASSIGNED,
                ApplicationAssignment.Status.IN_PROGRESS,
            ],
        ).select_related('assigned_to')
        context['assignments_by_app'] = {
            str(a.application_id): a for a in active_assignments
        }

        # Can the current user assign staff? (managers only)
        from core.models import User
        context['can_assign'] = self.request.user.role in (
            User.Role.AGENCY_ADMIN,
            User.Role.PROGRAM_OFFICER,
            User.Role.SYSTEM_ADMIN,
        )

        return context


# ---------------------------------------------------------------------------
# My applications (applicant)
# ---------------------------------------------------------------------------
class MyApplicationsView(LoginRequiredMixin, ListView):
    """Applications belonging to the currently authenticated applicant."""

    model = Application
    template_name = 'applications/my_applications.html'
    context_object_name = 'applications'
    paginate_by = 20

    def get_queryset(self):
        return Application.objects.filter(
            applicant=self.request.user,
        ).select_related('grant_program', 'organization')


# ---------------------------------------------------------------------------
# Create application
# ---------------------------------------------------------------------------
class ApplicationCreateView(LoginRequiredMixin, CreateView):
    """Create a new draft application for a specific grant program.

    The ``grant_program_id`` is taken from the URL.  ``applicant``,
    ``organization``, and ``status`` are set automatically.
    """

    model = Application
    form_class = ApplicationForm
    template_name = 'applications/application_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.grant_program = get_object_or_404(
            GrantProgram, pk=kwargs['grant_program_id'],
        )
        # Guard: applicant must have an organization before applying
        if request.user.is_authenticated and not request.user.organization:
            messages.warning(
                request,
                _('You must set up your organization profile before applying '
                  'for a grant.'),
            )
            create_url = reverse('core:organization-create')
            apply_url = reverse(
                'applications:create',
                kwargs={'grant_program_id': self.grant_program.pk},
            )
            return redirect(f'{create_url}?next={apply_url}')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['grant_program'] = self.grant_program
        return context

    def form_valid(self, form):
        form.instance.grant_program = self.grant_program
        form.instance.applicant = self.request.user
        form.instance.organization = self.request.user.organization
        form.instance.status = Application.Status.DRAFT
        return super().form_valid(form)

    def get_success_url(self):
        return self.object.get_absolute_url()


# ---------------------------------------------------------------------------
# Update application
# ---------------------------------------------------------------------------
class ApplicationUpdateView(LoginRequiredMixin, UpdateView):
    """Edit an existing application.

    Only applications whose status is ``draft`` or ``revision_requested``
    may be edited.
    """

    model = Application
    form_class = ApplicationForm
    template_name = 'applications/application_form.html'

    def get_queryset(self):
        return Application.objects.filter(
            applicant=self.request.user,
            status__in=[
                Application.Status.DRAFT,
                Application.Status.REVISION_REQUESTED,
            ],
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['grant_program'] = self.object.grant_program
        return context

    def get_success_url(self):
        return self.object.get_absolute_url()


# ---------------------------------------------------------------------------
# Application detail
# ---------------------------------------------------------------------------
class ApplicationDetailView(LoginRequiredMixin, DetailView):
    """Display full application details with documents, comments, and status
    history.

    Internal (staff-only) comments are filtered out for non-staff users.
    """

    model = Application
    template_name = 'applications/application_detail.html'
    context_object_name = 'application'

    def get_queryset(self):
        return Application.objects.select_related(
            'grant_program', 'applicant', 'organization',
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        application = self.object

        context['documents'] = application.documents.all()

        # Filter internal comments for non-staff users
        comments = application.comments.select_related('author')
        if not self.request.user.is_agency_staff:
            comments = comments.filter(is_internal=False)
        context['comments'] = comments

        context['status_history'] = application.status_history.select_related(
            'changed_by',
        )

        context['comment_form'] = ApplicationCommentForm()
        context['document_form'] = ApplicationDocumentForm()

        # Due-diligence context (staff only)
        if self.request.user.is_agency_staff:
            context['compliance_items'] = (
                application.compliance_items
                .select_related('verified_by')
                .all()
            )
            context['staff_documents'] = (
                application.staff_documents
                .select_related('uploaded_by')
                .all()
            )
            context['staff_document_form'] = StaffDocumentForm()
            context['status_change_form'] = StatusChangeForm(
                current_status=application.status,
            )

            # Compliance summary
            total_items = application.compliance_items.count()
            verified_items = application.compliance_items.filter(
                is_verified=True,
            ).count()
            required_items = application.compliance_items.filter(
                is_required=True,
            ).count()
            required_verified = application.compliance_items.filter(
                is_required=True,
                is_verified=True,
            ).count()
            context['compliance_total'] = total_items
            context['compliance_verified'] = verified_items
            context['compliance_required'] = required_items
            context['compliance_required_verified'] = required_verified
            context['compliance_all_required_met'] = (
                required_items > 0 and required_verified == required_items
            )
            if total_items > 0:
                context['compliance_pct'] = int(
                    (verified_items / total_items) * 100
                )
            else:
                context['compliance_pct'] = 0

            # Current assignment for this application
            context['current_assignment'] = ApplicationAssignment.objects.filter(
                application=application,
                status__in=[
                    ApplicationAssignment.Status.ASSIGNED,
                    ApplicationAssignment.Status.IN_PROGRESS,
                ],
            ).select_related('assigned_to', 'assigned_by').first()

            # Can the current user assign staff? (managers only)
            from core.models import User
            context['can_assign'] = self.request.user.role in (
                User.Role.AGENCY_ADMIN,
                User.Role.PROGRAM_OFFICER,
                User.Role.SYSTEM_ADMIN,
            )

        return context


# ---------------------------------------------------------------------------
# Submit application
# ---------------------------------------------------------------------------
class ApplicationSubmitView(LoginRequiredMixin, View):
    """POST-only view that transitions an application to ``submitted``."""

    http_method_names = ['post']

    def post(self, request, pk):
        # Staff may view all applications; applicants only their own
        if request.user.is_agency_staff:
            application = get_object_or_404(Application, pk=pk)
        else:
            application = get_object_or_404(
                Application, pk=pk, applicant=request.user,
            )

        if not application.is_editable:
            messages.error(request, _('This application cannot be submitted.'))
            return redirect('applications:detail', pk=application.pk)

        old_status = application.status
        application.status = Application.Status.SUBMITTED
        application.submitted_at = timezone.now()
        application.save(update_fields=['status', 'submitted_at', 'updated_at'])

        ApplicationStatusHistory.objects.create(
            application=application,
            old_status=old_status,
            new_status=Application.Status.SUBMITTED,
            changed_by=request.user,
            comment=_('Application submitted by applicant.'),
        )

        # Seed compliance checklist
        ensure_compliance_items(application)

        messages.success(request, _('Your application has been submitted successfully.'))

        # Notify agency staff about the new submission
        notify_application_submitted(application)

        log_audit(
            user=request.user,
            action=AuditLog.Action.SUBMIT,
            entity_type='Application',
            entity_id=str(application.pk),
            description=f'Application "{application}" submitted.',
            changes={'old_status': old_status, 'new_status': Application.Status.SUBMITTED},
            ip_address=getattr(request, 'audit_ip', None),
        )

        return redirect('applications:detail', pk=application.pk)


# ---------------------------------------------------------------------------
# Withdraw application
# ---------------------------------------------------------------------------
class ApplicationWithdrawView(LoginRequiredMixin, View):
    """POST-only view that transitions an application to ``withdrawn``."""

    http_method_names = ['post']

    def post(self, request, pk):
        if request.user.is_agency_staff:
            application = get_object_or_404(Application, pk=pk)
        else:
            application = get_object_or_404(
                Application, pk=pk, applicant=request.user,
            )

        if application.status == Application.Status.WITHDRAWN:
            messages.warning(request, _('This application has already been withdrawn.'))
            return redirect('applications:detail', pk=application.pk)

        old_status = application.status
        application.status = Application.Status.WITHDRAWN
        application.save(update_fields=['status', 'updated_at'])

        ApplicationStatusHistory.objects.create(
            application=application,
            old_status=old_status,
            new_status=Application.Status.WITHDRAWN,
            changed_by=request.user,
            comment=_('Application withdrawn by applicant.'),
        )

        messages.success(request, _('Your application has been withdrawn.'))

        log_audit(
            user=request.user,
            action=AuditLog.Action.STATUS_CHANGE,
            entity_type='Application',
            entity_id=str(application.pk),
            description=f'Application "{application}" withdrawn.',
            changes={'old_status': old_status, 'new_status': Application.Status.WITHDRAWN},
            ip_address=getattr(request, 'audit_ip', None),
        )

        return redirect('applications:detail', pk=application.pk)


# ---------------------------------------------------------------------------
# Add comment
# ---------------------------------------------------------------------------
class AddCommentView(LoginRequiredMixin, View):
    """POST-only view for adding a comment to an application."""

    http_method_names = ['post']

    def post(self, request, pk):
        application = get_object_or_404(Application, pk=pk)
        form = ApplicationCommentForm(request.POST)

        if form.is_valid():
            comment = form.save(commit=False)
            comment.application = application
            comment.author = request.user

            # Non-staff users cannot create internal comments
            if not request.user.is_agency_staff:
                comment.is_internal = False

            comment.save()
            messages.success(request, _('Comment added.'))
        else:
            messages.error(request, _('There was an error adding your comment.'))

        return redirect('applications:detail', pk=application.pk)


# ---------------------------------------------------------------------------
# Upload document
# ---------------------------------------------------------------------------
class UploadDocumentView(LoginRequiredMixin, View):
    """View for uploading a document to an application."""

    def get(self, request, pk):
        """Redirect GET requests to the application detail page."""
        return redirect('applications:detail', pk=pk)

    def post(self, request, pk):
        application = get_object_or_404(Application, pk=pk)
        form = ApplicationDocumentForm(request.POST, request.FILES)

        if form.is_valid():
            uploaded = request.FILES.get('file')
            if uploaded:
                result = scan_file(uploaded)
                if not result.is_clean:
                    messages.error(request, _('File rejected: %(reason)s') % {'reason': result.message})
                    return redirect('applications:detail', pk=application.pk)
            try:
                document = form.save(commit=False)
                document.application = application
                document.uploaded_by = request.user
                document.save()
                messages.success(request, _('Document uploaded successfully.'))
            except Exception as e:
                logger.exception('Failed to save document for application %s', pk)
                messages.error(request, _('Error saving document: %(error)s') % {'error': e})
        else:
            messages.error(request, _('There was an error uploading the document.'))

        return redirect('applications:detail', pk=application.pk)


# ---------------------------------------------------------------------------
# Staff: change application status
# ---------------------------------------------------------------------------
class ApplicationStatusChangeView(AgencyStaffRequiredMixin, View):
    """POST-only view for staff to transition an application's status.

    Valid transitions:
        submitted        → under_review
        under_review     → approved | denied | revision_requested

    A comment is always required.  All required compliance items must be
    verified before an application can be approved.
    """

    http_method_names = ['post']

    def post(self, request, pk):
        application = get_object_or_404(Application, pk=pk)

        # Only agency staff may change status
        if not request.user.is_agency_staff:
            messages.error(request, _('You do not have permission to perform this action.'))
            return redirect('applications:detail', pk=application.pk)

        form = StatusChangeForm(
            request.POST,
            current_status=application.status,
        )

        if not form.is_valid():
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
            return redirect('applications:detail', pk=application.pk)

        new_status = form.cleaned_data['new_status']
        comment_text = form.cleaned_data['comment']

        # Block approval if required compliance items are not all verified
        if new_status == Application.Status.APPROVED:
            unverified = application.compliance_items.filter(
                is_required=True,
                is_verified=False,
            ).count()
            if unverified > 0:
                messages.error(
                    request,
                    _('Cannot approve: %(count)d required compliance '
                      'item(s) have not been verified.') % {'count': unverified},
                )
                return redirect('applications:detail', pk=application.pk)

        old_status = application.status
        application.status = new_status
        application.save(update_fields=['status', 'updated_at'])

        ApplicationStatusHistory.objects.create(
            application=application,
            old_status=old_status,
            new_status=new_status,
            changed_by=request.user,
            comment=comment_text,
        )

        # Notify applicant about the status change
        notify_application_status_changed(
            application, old_status, new_status, comment=comment_text,
        )

        status_display = dict(Application.Status.choices).get(
            new_status, new_status,
        )
        messages.success(
            request,
            _('Application status changed to "%(status)s".') % {'status': status_display},
        )

        log_audit(
            user=request.user,
            action=AuditLog.Action.STATUS_CHANGE,
            entity_type='Application',
            entity_id=str(application.pk),
            description=f'Application "{application}" status changed from {old_status} to {new_status}.',
            changes={'old_status': old_status, 'new_status': new_status, 'comment': comment_text},
            ip_address=getattr(request, 'audit_ip', None),
        )

        return redirect('applications:detail', pk=application.pk)


# ---------------------------------------------------------------------------
# Staff: toggle compliance item
# ---------------------------------------------------------------------------
class ToggleComplianceView(LoginRequiredMixin, View):
    """POST-only view to toggle a compliance checklist item."""

    http_method_names = ['post']

    def post(self, request, pk, item_pk):
        application = get_object_or_404(Application, pk=pk)

        if not request.user.is_agency_staff:
            messages.error(request, _('You do not have permission to perform this action.'))
            return redirect('applications:detail', pk=application.pk)

        item = get_object_or_404(
            ApplicationComplianceItem,
            pk=item_pk,
            application=application,
        )

        notes = request.POST.get('notes', '').strip()

        if item.is_verified:
            # Un-verify
            item.is_verified = False
            item.verified_by = None
            item.verified_at = None
            if notes:
                item.notes = notes
            item.save()
            messages.info(request, _('"%(label)s" marked as not verified.') % {'label': item.label})
        else:
            # Verify
            item.is_verified = True
            item.verified_by = request.user
            item.verified_at = timezone.now()
            if notes:
                item.notes = notes
            item.save()
            messages.success(request, _('"%(label)s" verified.') % {'label': item.label})

        return redirect('applications:detail', pk=application.pk)


# ---------------------------------------------------------------------------
# Staff: upload internal document
# ---------------------------------------------------------------------------
class UploadStaffDocumentView(AgencyStaffRequiredMixin, View):
    """View for staff to upload an internal due-diligence document."""

    def get(self, request, pk):
        """Redirect GET requests to the application detail page."""
        return redirect('applications:detail', pk=pk)

    def post(self, request, pk):
        application = get_object_or_404(Application, pk=pk)

        if not request.user.is_agency_staff:
            messages.error(request, _('You do not have permission to perform this action.'))
            return redirect('applications:detail', pk=application.pk)

        form = StaffDocumentForm(request.POST, request.FILES)

        if form.is_valid():
            uploaded = request.FILES.get('file')
            if uploaded:
                result = scan_file(uploaded)
                if not result.is_clean:
                    messages.error(request, _('File rejected: %(reason)s') % {'reason': result.message})
                    return redirect('applications:detail', pk=application.pk)
            try:
                doc = form.save(commit=False)
                doc.application = application
                doc.uploaded_by = request.user
                doc.save()
                messages.success(request, _('Staff document uploaded successfully.'))
            except Exception as e:
                logger.exception('Failed to save staff document for application %s', pk)
                messages.error(request, _('Error saving document: %(error)s') % {'error': e})
        else:
            messages.error(
                request,
                _('Error uploading document. Please check the form. ')
                + '; '.join(
                    f'{field}: {", ".join(errs)}'
                    for field, errs in form.errors.items()
                ),
            )

        return redirect('applications:detail', pk=application.pk)


# ---------------------------------------------------------------------------
# Staff: seed compliance checklist for an application
# ---------------------------------------------------------------------------
def ensure_compliance_items(application):
    """Create the default compliance checklist items for an application.

    Called automatically when an application moves to ``submitted``.
    Idempotent — existing items are not duplicated.
    """
    defaults = [
        (ApplicationComplianceItem.ItemType.SAM_REGISTRATION,
         _('SAM Registration Active')),
        (ApplicationComplianceItem.ItemType.TAX_EXEMPT,
         _('Tax-Exempt Status Verified')),
        (ApplicationComplianceItem.ItemType.AUDIT_CLEARANCE,
         _('Audit Clearance')),
        (ApplicationComplianceItem.ItemType.DEBARMENT_CHECK,
         _('Debarment / Suspension Check')),
        (ApplicationComplianceItem.ItemType.BUDGET_REVIEW,
         _('Budget Review Complete')),
        (ApplicationComplianceItem.ItemType.NARRATIVE_REVIEW,
         _('Narrative Review Complete')),
        (ApplicationComplianceItem.ItemType.INSURANCE_VERIFIED,
         _('Insurance Verification')),
        (ApplicationComplianceItem.ItemType.ELIGIBILITY_CONFIRMED,
         _('Eligibility Confirmed')),
    ]

    # Conditionally add match verification
    if application.match_amount and application.match_amount > 0:
        defaults.append(
            (ApplicationComplianceItem.ItemType.MATCH_VERIFIED,
             _('Match Funds Verified')),
        )

    # Always add conflict of interest
    defaults.append(
        (ApplicationComplianceItem.ItemType.CONFLICT_OF_INTEREST,
         _('Conflict of Interest Check')),
    )

    for item_type, label in defaults:
        ApplicationComplianceItem.objects.get_or_create(
            application=application,
            item_type=item_type,
            defaults={
                'label': label,
                'is_required': item_type not in [
                    ApplicationComplianceItem.ItemType.INSURANCE_VERIFIED,
                ],
            },
        )


# ---------------------------------------------------------------------------
# Staff Application Assignments (Claim / Assign)
# ---------------------------------------------------------------------------
class ClaimApplicationView(AgencyStaffRequiredMixin, View):
    """POST-only view for staff to self-claim an application."""

    http_method_names = ['post']

    def post(self, request, pk):
        application = get_object_or_404(Application, pk=pk)

        existing = ApplicationAssignment.objects.filter(
            application=application,
            status__in=[
                ApplicationAssignment.Status.ASSIGNED,
                ApplicationAssignment.Status.IN_PROGRESS,
            ],
        ).select_related('assigned_to').first()

        if existing:
            if existing.assigned_to == request.user:
                messages.info(request, _('You are already assigned to this application.'))
            else:
                messages.warning(
                    request,
                    _('This application is already assigned to %(name)s.') % {
                        'name': existing.assigned_to.get_full_name()
                        or existing.assigned_to.username,
                    },
                )
            return redirect('applications:detail', pk=application.pk)

        ApplicationAssignment.objects.create(
            application=application,
            assigned_to=request.user,
            assigned_by=None,
            assignment_type=ApplicationAssignment.AssignmentType.CLAIMED,
            status=ApplicationAssignment.Status.ASSIGNED,
        )

        messages.success(request, _('You have claimed this application.'))
        return redirect('applications:detail', pk=application.pk)


class AssignApplicationView(AgencyStaffRequiredMixin, CreateView):
    """Assign a staff member to process an application (managers only)."""

    model = ApplicationAssignment
    form_class = ApplicationAssignmentForm
    template_name = 'applications/assign_form.html'

    def dispatch(self, request, *args, **kwargs):
        from core.models import User
        self.application = get_object_or_404(Application, pk=kwargs['pk'])
        if request.user.role not in (
            User.Role.AGENCY_ADMIN,
            User.Role.PROGRAM_OFFICER,
            User.Role.SYSTEM_ADMIN,
        ):
            messages.error(request, _('Only managers can assign applications to staff.'))
            return redirect('applications:detail', pk=self.application.pk)
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        # Mark prior active assignments as reassigned
        ApplicationAssignment.objects.filter(
            application=self.application,
            status__in=[
                ApplicationAssignment.Status.ASSIGNED,
                ApplicationAssignment.Status.IN_PROGRESS,
            ],
        ).update(status=ApplicationAssignment.Status.REASSIGNED)

        form.instance.application = self.application
        form.instance.assigned_by = self.request.user
        form.instance.assignment_type = ApplicationAssignment.AssignmentType.MANAGER_ASSIGNED
        messages.success(
            self.request,
            _('Application assigned to %(name)s.') % {
                'name': form.instance.assigned_to.get_full_name()
                or form.instance.assigned_to.username,
            },
        )
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['application'] = self.application
        context['current_assignment'] = ApplicationAssignment.objects.filter(
            application=self.application,
            status__in=[
                ApplicationAssignment.Status.ASSIGNED,
                ApplicationAssignment.Status.IN_PROGRESS,
            ],
        ).select_related('assigned_to').first()
        return context

    def get_success_url(self):
        return reverse('applications:detail', kwargs={'pk': self.application.pk})


class UpdateAssignmentStatusView(AgencyStaffRequiredMixin, View):
    """POST-only view to update an assignment's status."""

    http_method_names = ['post']

    def post(self, request, pk):
        assignment = get_object_or_404(
            ApplicationAssignment, pk=pk, assigned_to=request.user,
        )
        new_status = request.POST.get('status')
        if new_status not in dict(ApplicationAssignment.Status.choices):
            messages.error(request, _('Invalid status.'))
            return redirect('applications:detail', pk=assignment.application.pk)

        assignment.status = new_status
        if new_status == ApplicationAssignment.Status.COMPLETED:
            assignment.completed_at = timezone.now()
        assignment.save(update_fields=['status', 'completed_at', 'updated_at'])

        messages.success(request, _('Assignment status updated.'))
        return redirect('applications:detail', pk=assignment.application.pk)


class MyAssignmentsView(AgencyStaffRequiredMixin, SortableListMixin, ListView):
    """List applications assigned to the current staff member."""

    model = ApplicationAssignment
    template_name = 'applications/my_assignments.html'
    context_object_name = 'assignments'
    paginate_by = 20

    sortable_fields = {
        'application': 'application__project_title',
        'app_status': 'application__status',
        'assignment_status': 'status',
        'assigned_at': 'assigned_at',
    }
    default_sort = 'assigned_at'
    default_dir = 'desc'

    def get_queryset(self):
        qs = ApplicationAssignment.objects.filter(
            assigned_to=self.request.user,
        ).select_related(
            'application', 'application__grant_program',
            'application__organization', 'application__applicant',
            'assigned_by',
        )

        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)

        return self.apply_sorting(qs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_choices'] = ApplicationAssignment.Status.choices
        context['current_status'] = self.request.GET.get('status', '')
        context['active_count'] = ApplicationAssignment.objects.filter(
            assigned_to=self.request.user,
            status__in=['assigned', 'in_progress'],
        ).count()
        return context
