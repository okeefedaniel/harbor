import logging
import uuid
import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal

from django.conf import settings as django_settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.base import ContentFile
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _, gettext_lazy as _lazy
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from applications.models import Application
from core.audit import log_audit
from core.docusign import DocuSignService
from core.export import CSVExportMixin
from core.filters import AwardFilter
from core.mixins import AgencyObjectMixin, AgencyStaffRequiredMixin, GrantManagerRequiredMixin, SortableListMixin
from core.models import Agency, AuditLog, User
from core.notifications import (
    notify_amendment_created,
    notify_award_created,
    notify_signature_completed,
    notify_signature_requested,
)

from .forms import AwardAmendmentForm, AwardDocumentForm, AwardForm, SignatureRequestForm
from .models import Award, AwardAmendment, AwardDocument, SignatureRequest

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Award List  (agency staff)
# ---------------------------------------------------------------------------
class AwardListView(AgencyStaffRequiredMixin, SortableListMixin, CSVExportMixin, ListView):
    """List awards for agency staff.

    System admins see all awards; other agency staff see only their
    own agency's awards.  Supports filtering by ``status`` and ``agency``
    via query parameters.
    """

    model = Award
    template_name = 'awards/award_list.html'
    context_object_name = 'awards'
    paginate_by = 20
    csv_filename = 'awards.csv'
    csv_columns = [
        (_lazy('Award Number'), 'award_number'),
        (_lazy('Title'), 'title'),
        (_lazy('Recipient'), lambda o: o.recipient.get_full_name() or o.recipient.username),
        (_lazy('Organization'), 'organization.name'),
        (_lazy('Grant Program'), 'grant_program.title'),
        (_lazy('Status'), 'get_status_display'),
        (_lazy('Award Amount'), 'award_amount'),
        (_lazy('Start Date'), 'start_date'),
        (_lazy('End Date'), 'end_date'),
    ]

    sortable_fields = {
        'award_number': 'award_number',
        'title': 'title',
        'recipient': 'organization__name',
        'award_amount': 'award_amount',
        'status': 'status',
        'start_date': 'start_date',
        'end_date': 'end_date',
    }
    default_sort = 'start_date'
    default_dir = 'desc'

    def get_queryset(self):
        qs = Award.objects.select_related(
            'grant_program', 'agency', 'recipient', 'organization',
        )

        user = self.request.user
        if user.role != User.Role.SYSTEM_ADMIN and user.agency_id:
            qs = qs.filter(agency=user.agency)

        # Optional filters from query params (supports multiple values,
        # e.g. ?status=active&status=executed)
        statuses = self.request.GET.getlist('status')
        if statuses:
            qs = qs.filter(status__in=statuses)

        agency_id = self.request.GET.get('agency')
        if agency_id:
            qs = qs.filter(agency_id=agency_id)

        self.filterset = AwardFilter(self.request.GET, queryset=qs)
        return self.apply_sorting(self.filterset.qs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['agencies'] = Agency.objects.filter(is_active=True)
        context['filter'] = self.filterset
        return context


# ---------------------------------------------------------------------------
# My Awards  (subrecipients / applicants)
# ---------------------------------------------------------------------------
class MyAwardsView(LoginRequiredMixin, ListView):
    """List awards belonging to the currently authenticated user."""

    model = Award
    template_name = 'awards/my_awards.html'
    context_object_name = 'awards'

    def get_queryset(self):
        return (
            Award.objects
            .filter(recipient=self.request.user)
            .select_related('grant_program', 'agency', 'organization')
        )


# ---------------------------------------------------------------------------
# Award Detail
# ---------------------------------------------------------------------------
class AwardDetailView(LoginRequiredMixin, DetailView):
    """Detailed view of a single award, including related objects."""

    model = Award
    template_name = 'awards/award_detail.html'
    context_object_name = 'award'

    def get_queryset(self):
        return Award.objects.select_related(
            'application', 'grant_program', 'agency',
            'recipient', 'organization', 'approved_by',
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        award = self.object
        context['amendments'] = award.amendments.select_related(
            'requested_by', 'approved_by',
        ).all()
        context['documents'] = award.documents.all()
        context['budgets'] = award.budgets.all()
        context['drawdowns'] = award.drawdown_requests.select_related(
            'submitted_by', 'reviewed_by',
        ).all()
        context['recent_transactions'] = award.transactions.all()[:10]
        context['reports'] = award.reports.all()[:10]

        # Financial summary
        total_spent = award.transactions.filter(
            transaction_type__in=['payment', 'drawdown'],
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0')
        context['total_spent'] = total_spent
        context['remaining'] = award.award_amount - total_spent
        if award.award_amount:
            context['spent_pct'] = int((total_spent / award.award_amount) * 100)
        else:
            context['spent_pct'] = 0

        # Closeout
        context['closeout'] = getattr(award, 'closeout', None)

        # Signature requests (DocuSign)
        context['signature_requests'] = award.signature_requests.select_related(
            'sent_by',
        ).all()
        context['signature_form'] = SignatureRequestForm(
            initial={
                'signer_name': award.recipient.get_full_name(),
                'signer_email': award.recipient.email,
            }
        )

        return context


# ---------------------------------------------------------------------------
# Award Create  (from an approved application)
# ---------------------------------------------------------------------------
class AwardCreateView(GrantManagerRequiredMixin, CreateView):
    """Create a new award from an approved application.

    The application is identified by the ``application_id`` URL kwarg.
    Fields such as ``application``, ``grant_program``, ``agency``,
    ``recipient``, and ``organization`` are populated from the
    application automatically.
    """

    model = Award
    form_class = AwardForm
    template_name = 'awards/award_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.application = get_object_or_404(
            Application.objects.select_related(
                'grant_program', 'grant_program__agency',
                'applicant', 'organization',
            ),
            pk=kwargs['application_id'],
            status=Application.Status.APPROVED,
        )
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        app = self.application
        initial['title'] = app.project_title
        initial['award_amount'] = app.requested_amount
        initial['start_date'] = app.proposed_start_date
        initial['end_date'] = app.proposed_end_date
        initial['match_amount'] = app.match_amount
        initial['requires_match'] = app.match_amount is not None and app.match_amount > 0
        return initial

    def _generate_award_number(self):
        """Generate a unique award number.

        Format: CT-{agency abbreviation}-{fiscal year}-{sequential 4-digit}
        """
        agency = self.application.grant_program.agency
        fiscal_year = date.today().year
        prefix = f"CT-{agency.abbreviation}-{fiscal_year}"

        last = (
            Award.objects
            .filter(award_number__startswith=prefix)
            .order_by('-award_number')
            .values_list('award_number', flat=True)
            .first()
        )

        if last:
            try:
                seq = int(last.rsplit('-', 1)[-1]) + 1
            except (ValueError, IndexError):
                seq = 1
        else:
            seq = 1

        return f"{prefix}-{seq:04d}"

    def form_valid(self, form):
        app = self.application
        form.instance.application = app
        form.instance.grant_program = app.grant_program
        form.instance.agency = app.grant_program.agency
        form.instance.recipient = app.applicant
        form.instance.organization = app.organization

        # Auto-generate award number if not provided
        if not form.instance.award_number:
            form.instance.award_number = self._generate_award_number()

        response = super().form_valid(form)

        # Notify the applicant about the new award
        notify_award_created(self.object)

        log_audit(
            user=self.request.user,
            action=AuditLog.Action.CREATE,
            entity_type='Award',
            entity_id=str(self.object.pk),
            description=f'Award "{self.object}" created from application "{app}".',
            ip_address=getattr(self.request, 'audit_ip', None),
        )

        messages.success(self.request, _('Award created successfully.'))
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['application'] = self.application
        return context

    def get_success_url(self):
        return reverse_lazy('awards:detail', kwargs={'pk': self.object.pk})


# ---------------------------------------------------------------------------
# Award Update
# ---------------------------------------------------------------------------
class AwardUpdateView(GrantManagerRequiredMixin, AgencyObjectMixin, UpdateView):
    """Edit an existing award."""

    model = Award
    form_class = AwardForm
    template_name = 'awards/award_form.html'

    def get_queryset(self):
        qs = Award.objects.select_related(
            'grant_program', 'agency', 'recipient', 'organization',
        )
        user = self.request.user
        if user.role != User.Role.SYSTEM_ADMIN and user.agency_id:
            qs = qs.filter(agency=user.agency)
        return qs

    def form_valid(self, form):
        messages.success(self.request, _('Award updated successfully.'))
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('awards:detail', kwargs={'pk': self.object.pk})


# ---------------------------------------------------------------------------
# Award Amendment Create
# ---------------------------------------------------------------------------
class AwardAmendmentCreateView(AgencyStaffRequiredMixin, CreateView):
    """Create an amendment for an existing award."""

    model = AwardAmendment
    form_class = AwardAmendmentForm
    template_name = 'awards/amendment_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.award = get_object_or_404(Award, pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.award = self.award
        form.instance.requested_by = self.request.user

        # Auto-increment amendment number
        last_number = (
            AwardAmendment.objects
            .filter(award=self.award)
            .order_by('-amendment_number')
            .values_list('amendment_number', flat=True)
            .first()
        ) or 0
        form.instance.amendment_number = last_number + 1

        messages.success(self.request, _('Amendment submitted successfully.'))
        response = super().form_valid(form)

        notify_amendment_created(self.object)

        log_audit(
            user=self.request.user,
            action=AuditLog.Action.CREATE,
            entity_type='AwardAmendment',
            entity_id=str(self.object.pk),
            description=f'Amendment #{self.object.amendment_number} created for award "{self.award}".',
            ip_address=getattr(self.request, 'audit_ip', None),
        )

        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['award'] = self.award
        return context

    def get_success_url(self):
        return reverse_lazy('awards:detail', kwargs={'pk': self.award.pk})


# ---------------------------------------------------------------------------
# Award Amendment Detail
# ---------------------------------------------------------------------------
class AwardAmendmentDetailView(AgencyStaffRequiredMixin, DetailView):
    """Show details of a single award amendment."""

    model = AwardAmendment
    template_name = 'awards/amendment_detail.html'
    context_object_name = 'amendment'

    def get_queryset(self):
        return AwardAmendment.objects.select_related(
            'award', 'requested_by', 'approved_by',
        )


# ---------------------------------------------------------------------------
# Award Document Upload
# ---------------------------------------------------------------------------
class AwardDocumentUploadView(AgencyStaffRequiredMixin, CreateView):
    """Upload a document to an award."""

    model = AwardDocument
    form_class = AwardDocumentForm
    template_name = 'awards/document_upload_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.award = get_object_or_404(Award, pk=kwargs['award_id'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.award = self.award
        form.instance.uploaded_by = self.request.user
        messages.success(self.request, _('Document uploaded successfully.'))
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['award'] = self.award
        return context

    def get_success_url(self):
        return reverse_lazy('awards:detail', kwargs={'pk': self.award.pk})


# ---------------------------------------------------------------------------
# Award Amendment Approve  (POST only)
# ---------------------------------------------------------------------------
class AwardAmendmentApproveView(AgencyStaffRequiredMixin, View):
    """POST-only endpoint to approve an amendment."""

    http_method_names = ['post']

    def post(self, request, pk):
        amendment = get_object_or_404(AwardAmendment, pk=pk)

        if amendment.status not in (
            AwardAmendment.Status.DRAFT,
            AwardAmendment.Status.SUBMITTED,
        ):
            messages.error(
                request,
                _('This amendment cannot be approved in its current state.'),
            )
            return redirect('awards:amendment-detail', pk=amendment.pk)

        amendment.status = AwardAmendment.Status.APPROVED
        amendment.approved_by = request.user
        amendment.approved_at = timezone.now()
        amendment.save(update_fields=[
            'status', 'approved_by', 'approved_at',
        ])

        messages.success(request, _('Amendment approved successfully.'))
        return redirect('awards:amendment-detail', pk=amendment.pk)


# ---------------------------------------------------------------------------
# Award Amendment Deny  (POST only)
# ---------------------------------------------------------------------------
class AwardAmendmentDenyView(AgencyStaffRequiredMixin, View):
    """POST-only endpoint to deny an amendment."""

    http_method_names = ['post']

    def post(self, request, pk):
        amendment = get_object_or_404(AwardAmendment, pk=pk)

        if amendment.status not in (
            AwardAmendment.Status.DRAFT,
            AwardAmendment.Status.SUBMITTED,
        ):
            messages.error(
                request,
                _('This amendment cannot be denied in its current state.'),
            )
            return redirect('awards:amendment-detail', pk=amendment.pk)

        amendment.status = AwardAmendment.Status.DENIED
        amendment.save(update_fields=['status'])

        messages.success(request, _('Amendment denied.'))
        return redirect('awards:amendment-detail', pk=amendment.pk)


# ---------------------------------------------------------------------------
# Signature Request  (DocuSign e-Signature)
# ---------------------------------------------------------------------------
class SignatureRequestView(LoginRequiredMixin, View):
    """Send an award agreement for e-signature via DocuSign."""

    http_method_names = ['get', 'post']

    def get(self, request, pk):
        award = get_object_or_404(Award, pk=pk)
        form = SignatureRequestForm(initial={
            'signer_name': award.recipient.get_full_name(),
            'signer_email': award.recipient.email,
        })
        return render(request, 'awards/signature_request.html', {
            'award': award,
            'form': form,
        })

    def post(self, request, pk):
        award = get_object_or_404(Award, pk=pk)
        form = SignatureRequestForm(request.POST)

        if not form.is_valid():
            return render(request, 'awards/signature_request.html', {
                'award': award,
                'form': form,
            })

        signer_name = form.cleaned_data['signer_name']
        signer_email = form.cleaned_data['signer_email']
        cc_email = form.cleaned_data.get('cc_email') or None
        notes = form.cleaned_data.get('notes', '')

        try:
            ds_service = DocuSignService()
            envelope_id = ds_service.create_envelope(
                award=award,
                signer_name=signer_name,
                signer_email=signer_email,
                cc_email=cc_email,
            )
        except Exception:
            logger.exception(
                'DocuSign envelope creation failed for award %s', award.pk,
            )
            messages.error(
                request,
                _('Failed to send the document for signature. Please try again later.'),
            )
            return redirect('awards:detail', pk=award.pk)

        sig_request = SignatureRequest.objects.create(
            award=award,
            envelope_id=envelope_id,
            status=SignatureRequest.Status.SENT,
            signer_name=signer_name,
            signer_email=signer_email,
            sent_by=request.user,
            notes=notes,
        )

        log_audit(
            user=request.user,
            action=AuditLog.Action.CREATE,
            entity_type='SignatureRequest',
            entity_id=str(sig_request.pk),
            description=(
                f'Signature request sent for award "{award}" '
                f'to {signer_name} ({signer_email}).'
            ),
            ip_address=getattr(request, 'audit_ip', None),
        )

        notify_signature_requested(award, sig_request)

        messages.success(
            request,
            _('Award agreement sent to %(name)s (%(email)s) for signature.') % {
                'name': signer_name,
                'email': signer_email,
            },
        )
        return redirect('awards:detail', pk=award.pk)


# ---------------------------------------------------------------------------
# DocuSign Webhook (Connect callback)
# ---------------------------------------------------------------------------
@method_decorator(csrf_exempt, name='dispatch')
class DocuSignWebhookView(View):
    """Receive DocuSign Connect webhook notifications.

    DocuSign sends XML payloads with envelope status updates.
    This endpoint updates the corresponding ``SignatureRequest`` record
    and, when completed, downloads the signed document.
    """

    http_method_names = ['post']

    # Mapping from DocuSign envelope statuses to our model statuses
    STATUS_MAP = {
        'sent': SignatureRequest.Status.SENT,
        'delivered': SignatureRequest.Status.DELIVERED,
        'completed': SignatureRequest.Status.SIGNED,
        'declined': SignatureRequest.Status.DECLINED,
        'voided': SignatureRequest.Status.VOIDED,
    }

    def post(self, request):
        try:
            body = request.body.decode('utf-8')
            root = ET.fromstring(body)

            # DocuSign XML namespaces
            ns = {'ds': 'http://www.docusign.net/API/3.0'}

            # Try with namespace first, then without
            envelope_id_el = root.find('.//ds:EnvelopeStatus/ds:EnvelopeID', ns)
            status_el = root.find('.//ds:EnvelopeStatus/ds:Status', ns)

            if envelope_id_el is None:
                envelope_id_el = root.find('.//EnvelopeID')
                status_el = root.find('.//Status')

            if envelope_id_el is None or status_el is None:
                logger.warning('DocuSign webhook: could not parse envelope ID or status.')
                return JsonResponse({'status': 'error', 'message': 'Invalid payload'}, status=400)

            envelope_id = envelope_id_el.text
            docusign_status = status_el.text.lower()

            logger.info(
                'DocuSign webhook received: envelope=%s status=%s',
                envelope_id, docusign_status,
            )

            try:
                sig_request = SignatureRequest.objects.select_related(
                    'award', 'sent_by',
                ).get(envelope_id=envelope_id)
            except SignatureRequest.DoesNotExist:
                logger.warning(
                    'DocuSign webhook: no SignatureRequest found for envelope %s',
                    envelope_id,
                )
                return JsonResponse({'status': 'ok', 'message': 'Unknown envelope'})

            new_status = self.STATUS_MAP.get(docusign_status)
            if new_status:
                sig_request.status = new_status
                update_fields = ['status', 'updated_at']

                if new_status == SignatureRequest.Status.SIGNED:
                    sig_request.completed_at = timezone.now()
                    update_fields.append('completed_at')

                    # Download the signed document
                    try:
                        ds_service = DocuSignService()
                        pdf_bytes = ds_service.download_signed_document(envelope_id)
                        filename = f'signed_{sig_request.award.award_number}_{envelope_id[:8]}.pdf'
                        sig_request.signed_document.save(
                            filename,
                            ContentFile(pdf_bytes),
                            save=False,
                        )
                        update_fields.append('signed_document')
                    except Exception:
                        logger.exception(
                            'Failed to download signed document for envelope %s',
                            envelope_id,
                        )

                    # Update award status to EXECUTED
                    award = sig_request.award
                    award.status = Award.Status.EXECUTED
                    award.executed_at = timezone.now()
                    award.save(update_fields=['status', 'executed_at', 'updated_at'])

                    notify_signature_completed(award, sig_request)

                sig_request.save(update_fields=update_fields)

            return JsonResponse({'status': 'ok'})

        except Exception:
            logger.exception('DocuSign webhook processing failed.')
            return JsonResponse(
                {'status': 'error', 'message': 'Internal server error'},
                status=500,
            )


# ---------------------------------------------------------------------------
# Signature Status  (AJAX polling)
# ---------------------------------------------------------------------------
class SignatureStatusView(LoginRequiredMixin, View):
    """Return JSON with the current status of a signature request.

    Used by the frontend for AJAX polling to update the UI
    when a signer completes signing.
    """

    http_method_names = ['get']

    def get(self, request, pk):
        sig_request = get_object_or_404(
            SignatureRequest.objects.select_related('award'),
            pk=pk,
        )
        return JsonResponse({
            'id': str(sig_request.pk),
            'envelope_id': sig_request.envelope_id,
            'status': sig_request.status,
            'status_display': sig_request.get_status_display(),
            'signer_name': sig_request.signer_name,
            'signer_email': sig_request.signer_email,
            'sent_at': sig_request.sent_at.isoformat() if sig_request.sent_at else None,
            'completed_at': sig_request.completed_at.isoformat() if sig_request.completed_at else None,
            'has_signed_document': bool(sig_request.signed_document),
        })
