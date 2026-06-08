import base64
import hashlib
import hmac
import logging
import uuid
# defusedxml hardens the parser against billion-laughs / external-entity
# attacks. The DocuSign webhook is HMAC-gated, so reachability requires the
# secret, but defense-in-depth: an attacker who learns the secret should not
# be able to OOM the worker by posting an exponential-entity payload.
import defusedxml.ElementTree as ET
from datetime import date
from decimal import Decimal

from django.conf import settings as django_settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files.base import ContentFile
from django.db.models import Sum
from django.http import FileResponse, Http404, JsonResponse
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
from core.docusign import DocuSignService  # noqa: F401 — retained for legacy DocuSignWebhookView
from core.export import CSVExportMixin
from core.filters import AwardFilter
from core.mixins import AgencyObjectMixin, AgencyStaffRequiredMixin, GrantManagerRequiredMixin, SortableListMixin
from core.models import Agency, AuditLog
from django.contrib.auth import get_user_model; User = get_user_model()
from django.urls import reverse
from core.notifications import (
    notify_amendment_created,
    notify_award_created,
    notify_signature_completed,
    notify_signature_requested,
)
from keel.signatures.client import (
    is_available as manifest_is_available,
    local_sign,
    send_to_manifest,
)
from keel.signatures.models import ManifestHandoff

from .forms import (
    AwardAmendmentForm, AwardDocumentForm, AwardForm,
    AwardLocalSignForm, SignatureRequestForm,
)
from .models import Award, AwardAmendment, AwardAttachment, SignatureRequest

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
        if getattr(user, 'role', '') != 'system_admin' and user.agency_id:
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
class AwardAttachmentDownloadView(LoginRequiredMixin, View):
    """Stream an AwardAttachment via FileResponse behind the award ACL.

    CSO Wave 4: detail template was linking ``{{ doc.file.url }}`` which
    404s in prod (no /media/ handler) and would bypass the
    AwardDetailView ACL if /media/ ever started serving. Mirror the
    same ACL the parent detail view uses, plus an INTERNAL-visibility
    staff gate (matching the ApplicationAttachmentDownloadView pattern
    from Week 1).
    """

    def get(self, request, pk):
        doc = get_object_or_404(
            AwardAttachment.objects.select_related('award__agency'),
            pk=pk,
        )
        user = request.user
        award = doc.award
        allowed = (
            user.is_superuser
            or getattr(user, 'role', '') == 'system_admin'
            or (getattr(user, 'is_agency_staff', False) and award.agency_id == getattr(user, 'agency_id', None))
            or award.recipient_id == user.pk
        )
        if not allowed:
            raise Http404
        # INTERNAL-visibility attachments are staff-only.
        if doc.visibility == AwardAttachment.Visibility.INTERNAL:
            is_staff_actor = (
                user.is_superuser
                or getattr(user, 'role', '') == 'system_admin'
                or getattr(user, 'is_agency_staff', False)
            )
            if not is_staff_actor:
                raise Http404
        if not doc.file:
            raise Http404
        return FileResponse(
            doc.file.open('rb'),
            as_attachment=True,
            filename=doc.title or doc.filename or doc.file.name.rsplit('/', 1)[-1],
        )


class AwardDetailView(LoginRequiredMixin, DetailView):
    """Detailed view of a single award, including related objects."""

    model = Award
    template_name = 'awards/award_detail.html'
    context_object_name = 'award'

    def get_queryset(self):
        user = self.request.user
        qs = Award.objects.select_related(
            'application', 'grant_program', 'agency',
            'recipient', 'organization', 'approved_by',
        )
        if user.is_superuser or user.role == 'system_admin':
            return qs
        if user.is_agency_staff and user.agency:
            return qs.filter(agency=user.agency)
        return qs.filter(recipient=user)

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

        # Native signing flow (signatures app)
        from signatures.models import SignatureFlow, SigningPacket
        from django.contrib.contenttypes.models import ContentType
        context['signature_flow'] = (
            SignatureFlow.objects
            .filter(grant_program=award.grant_program, is_active=True)
            .first()
        )
        award_ct = ContentType.objects.get_for_model(Award)
        context['signing_packets'] = (
            SigningPacket.objects
            .filter(content_type=award_ct, object_id=str(award.pk))
            .select_related('flow', 'initiated_by')
            .order_by('-created_at')
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
        if getattr(user, 'role', '') != 'system_admin' and user.agency_id:
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
    """Upload a document to an award (agreement, amendment, correspondence, etc.)."""

    model = AwardAttachment
    form_class = AwardDocumentForm
    template_name = 'awards/document_upload_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.award = get_object_or_404(Award, pk=kwargs['award_id'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.award = self.award
        form.instance.uploaded_by = self.request.user
        form.instance.source = AwardAttachment.Source.UPLOAD
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
    """Send an award agreement to Manifest for e-signature.

    Post-0.14: this view routes signing through
    ``keel.signatures.client.send_to_manifest`` instead of the bespoke
    DocuSign client. The DocuSign path (``core.docusign.DocuSignService``,
    ``DocuSignWebhookView``, ``SignatureRequest`` model) remains in the
    codebase as dead code, kept for rollback; the new flow creates a
    ``ManifestHandoff`` row and the ``awards.packet_approved`` receiver
    (awards/signals.py) attaches the signed PDF to the award as an
    ``AwardAttachment`` and transitions ``Award.status`` to ``EXECUTED``.

    Standalone-mode fallback: when Manifest isn't configured, the UI
    routes users to ``AwardLocalSignView`` to upload a locally-signed PDF.

    CSO 2026-06-08: added agency-staff ACL gate — mirrors AwardLocalSignView
    fix; bare get_object_or_404 without ownership check was an IDOR path.
    """

    http_method_names = ['get', 'post']

    def _get_award_or_403(self, request, pk):
        """Return the award if the user is agency staff for it, otherwise Http404."""
        award = get_object_or_404(Award, pk=pk)
        user = request.user
        allowed = (
            user.is_superuser
            or getattr(user, 'role', '') == 'system_admin'
            or (
                getattr(user, 'is_agency_staff', False)
                and award.agency_id == getattr(user, 'agency_id', None)
            )
        )
        if not allowed:
            raise Http404
        return award

    def get(self, request, pk):
        award = self._get_award_or_403(request, pk)
        form = SignatureRequestForm(initial={
            'signer_name': award.recipient.get_full_name(),
            'signer_email': award.recipient.email,
        })
        return render(request, 'awards/signature_request.html', {
            'award': award,
            'form': form,
            'manifest_available': manifest_is_available(),
        })

    def post(self, request, pk):
        award = self._get_award_or_403(request, pk)
        form = SignatureRequestForm(request.POST)

        if not form.is_valid():
            return render(request, 'awards/signature_request.html', {
                'award': award,
                'form': form,
                'manifest_available': manifest_is_available(),
            })

        signer_name = form.cleaned_data['signer_name']
        signer_email = form.cleaned_data['signer_email']
        cc_email = form.cleaned_data.get('cc_email') or None
        notes = form.cleaned_data.get('notes', '')

        if not manifest_is_available():
            messages.error(
                request,
                _('Manifest is not configured. Use "Upload signed agreement" instead.'),
            )
            return redirect('awards:signature-local', pk=award.pk)

        signers = [{'email': signer_email, 'name': signer_name}]
        if cc_email:
            signers.append({'email': cc_email, 'name': 'CC', 'role': 'cc'})

        handoff = send_to_manifest(
            source_obj=award,
            packet_label=f'Award Agreement — {award.award_number}',
            signers=signers,
            attachment_model='awards.AwardAttachment',
            attachment_fk_name='award',
            on_approved_status=Award.Status.EXECUTED,
            created_by=request.user,
            callback_url=request.build_absolute_uri(
                reverse('keel_signatures:webhook'),
            ),
        )

        log_audit(
            user=request.user,
            action=AuditLog.Action.CREATE,
            entity_type='ManifestHandoff',
            entity_id=str(handoff.pk),
            description=(
                f'Award agreement sent to Manifest for signing: '
                f'"{award}" → {signer_name} ({signer_email}).'
                + (f' Notes: {notes}' if notes else '')
            ),
            ip_address=getattr(request, 'audit_ip', None),
        )

        # Preserve the legacy SignatureRequest record so existing
        # templates, notification helpers, and award_detail history
        # queries keep working during the cutover window. The
        # envelope_id slot now carries the Manifest packet UUID.
        sig_request = SignatureRequest.objects.create(
            award=award,
            envelope_id=handoff.manifest_packet_uuid or str(handoff.pk),
            status=(
                SignatureRequest.Status.SENT
                if handoff.status == ManifestHandoff.Status.SENT
                else SignatureRequest.Status.VOIDED
            ),
            signer_name=signer_name,
            signer_email=signer_email,
            sent_by=request.user,
            notes=notes,
        )
        notify_signature_requested(award, sig_request)

        if handoff.status == ManifestHandoff.Status.SENT:
            messages.success(
                request,
                _('Award agreement sent to %(name)s (%(email)s) via Manifest.') % {
                    'name': signer_name,
                    'email': signer_email,
                },
            )
        else:
            messages.error(
                request,
                _('Could not reach Manifest: %(err)s. The attempt is logged.') % {
                    'err': handoff.error_message or handoff.get_status_display(),
                },
            )
        return redirect('awards:detail', pk=award.pk)


class AwardLocalSignView(LoginRequiredMixin, View):
    """Upload a locally-signed award agreement when Manifest isn't deployed.

    Records a ``ManifestHandoff`` with status=LOCAL_SIGNED and fires the
    same ``packet_approved`` signal the real Manifest roundtrip does,
    so the award transitions to ``EXECUTED`` and the signed PDF is
    filed identically.

    CSO 2026-06-08: previously used a bare get_object_or_404(Award, pk=pk)
    with no ACL — any authenticated user could navigate to
    /awards/<any-pk>/local-sign/ and upload a PDF for an award they do not
    own, triggering the EXECUTED transition on an arbitrary award.  Gated
    to agency staff scoped to the award's agency (mirrors
    SignatureRequestView's implicit expectation and AwardDetailView's ACL).
    """

    http_method_names = ['get', 'post']

    def _get_award_or_403(self, request, pk):
        """Return the award if the user may act on it, otherwise Http404."""
        award = get_object_or_404(Award, pk=pk)
        user = request.user
        allowed = (
            user.is_superuser
            or getattr(user, 'role', '') == 'system_admin'
            or (
                getattr(user, 'is_agency_staff', False)
                and award.agency_id == getattr(user, 'agency_id', None)
            )
        )
        if not allowed:
            raise Http404
        return award

    def get(self, request, pk):
        award = self._get_award_or_403(request, pk)
        return render(request, 'awards/local_sign.html', {
            'award': award,
            'form': AwardLocalSignForm(),
        })

    def post(self, request, pk):
        award = self._get_award_or_403(request, pk)
        form = AwardLocalSignForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(request, 'awards/local_sign.html', {
                'award': award,
                'form': form,
            })
        local_sign(
            source_obj=award,
            signed_pdf=form.cleaned_data['signed_pdf'],
            attachment_model='awards.AwardAttachment',
            attachment_fk_name='award',
            on_approved_status=Award.Status.EXECUTED,
            packet_label=f'Award Agreement (local) — {award.award_number}',
            created_by=request.user,
        )
        messages.success(
            request,
            _('Signed award agreement recorded. Award moved to Executed.'),
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

    def _verify_hmac(self, request):
        """Verify DocuSign Connect HMAC signature.

        DocuSign sends one or more ``X-DocuSign-Signature-N`` headers containing
        base64(HMAC-SHA256(body, secret)). Any configured secret must match one.
        Returns True if the signature is valid (fail-closed when configured).
        """
        secret = getattr(django_settings, 'DOCUSIGN_HMAC_KEY', '') or ''
        if not secret:
            # Fail closed: if no secret is configured, refuse unsigned webhooks
            # in production. Keep the legacy bypass only in DEBUG for local dev.
            return bool(django_settings.DEBUG)

        expected = base64.b64encode(
            hmac.new(secret.encode('utf-8'), request.body, hashlib.sha256).digest()
        ).decode('ascii')

        # DocuSign numbers signature headers starting at 1; accept any match.
        for header, value in request.META.items():
            if not header.startswith('HTTP_X_DOCUSIGN_SIGNATURE'):
                continue
            if hmac.compare_digest(value.strip(), expected):
                return True
        return False

    def post(self, request):
        if not self._verify_hmac(request):
            logger.warning('DocuSign webhook: HMAC verification failed.')
            return JsonResponse({'status': 'error', 'message': 'Invalid signature'}, status=401)
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
