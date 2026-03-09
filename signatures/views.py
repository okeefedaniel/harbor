import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)

from .compat import (
    AgencyStaffRequiredMixin,
    GrantManagerRequiredMixin,
    SortableListMixin,
    get_audit_log_model,
)

from .forms import (
    DeclineForm,
    FlowStepForm,
    PacketInitiateForm,
    SignatureDocumentForm,
    SignatureFlowForm,
    SignatureRoleForm,
    SigningForm,
    UserSignatureForm,
)
from .models import (
    SignatureDocument,
    SignatureFlow,
    SignatureFlowStep,
    SignaturePlacement,
    SignatureRole,
    SigningPacket,
    SigningStep,
    UserSignature,
)
from . import services


# ===========================================================================
# Flow Administration (admin-only)
# ===========================================================================

class FlowListView(GrantManagerRequiredMixin, SortableListMixin, ListView):
    model = SignatureFlow
    template_name = 'signatures/flow_list.html'
    context_object_name = 'flows'
    paginate_by = 20
    sortable_fields = {
        'name': 'name',
        'created_at': 'created_at',
    }
    default_sort = 'name'
    default_dir = 'asc'


class FlowCreateView(GrantManagerRequiredMixin, CreateView):
    model = SignatureFlow
    form_class = SignatureFlowForm
    template_name = 'signatures/flow_form.html'

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('signatures:flow-detail', kwargs={'pk': self.object.pk})


class FlowDetailView(AgencyStaffRequiredMixin, DetailView):
    model = SignatureFlow
    template_name = 'signatures/flow_detail.html'
    context_object_name = 'flow'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['steps'] = self.object.steps.order_by('order')
        context['documents'] = self.object.documents.all()
        context['packets'] = self.object.packets.order_by('-created_at')[:10]
        return context


class FlowUpdateView(GrantManagerRequiredMixin, UpdateView):
    model = SignatureFlow
    form_class = SignatureFlowForm
    template_name = 'signatures/flow_form.html'

    def get_success_url(self):
        return reverse('signatures:flow-detail', kwargs={'pk': self.object.pk})


class FlowDeleteView(GrantManagerRequiredMixin, DeleteView):
    model = SignatureFlow
    template_name = 'signatures/flow_confirm_delete.html'
    success_url = reverse_lazy('signatures:flow-list')


# ===========================================================================
# Role Management (admin-only, used in standalone mode)
# ===========================================================================

class RoleListView(GrantManagerRequiredMixin, SortableListMixin, ListView):
    model = SignatureRole
    template_name = 'signatures/role_list.html'
    context_object_name = 'roles'
    paginate_by = 20
    sortable_fields = {
        'label': 'label',
        'key': 'key',
        'created_at': 'created_at',
    }
    default_sort = 'label'
    default_dir = 'asc'


class RoleCreateView(GrantManagerRequiredMixin, CreateView):
    model = SignatureRole
    form_class = SignatureRoleForm
    template_name = 'signatures/role_form.html'
    success_url = reverse_lazy('signatures:role-list')

    def form_valid(self, form):
        messages.success(self.request, _('Role created successfully.'))
        return super().form_valid(form)


class RoleUpdateView(GrantManagerRequiredMixin, UpdateView):
    model = SignatureRole
    form_class = SignatureRoleForm
    template_name = 'signatures/role_form.html'
    success_url = reverse_lazy('signatures:role-list')

    def form_valid(self, form):
        messages.success(self.request, _('Role updated successfully.'))
        return super().form_valid(form)


class RoleDeleteView(GrantManagerRequiredMixin, DeleteView):
    model = SignatureRole
    template_name = 'signatures/role_confirm_delete.html'
    success_url = reverse_lazy('signatures:role-list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['usage_count'] = SignatureFlowStep.objects.filter(
            assigned_role=self.object.key,
        ).count()
        return context

    def form_valid(self, form):
        messages.success(self.request, _('Role deleted.'))
        return super().form_valid(form)


# ===========================================================================
# Step CRUD (admin-only)
# ===========================================================================

class StepCreateView(GrantManagerRequiredMixin, CreateView):
    model = SignatureFlowStep
    form_class = FlowStepForm
    template_name = 'signatures/step_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['flow'] = get_object_or_404(SignatureFlow, pk=self.kwargs['flow_id'])
        return kwargs

    def form_valid(self, form):
        form.instance.flow = get_object_or_404(SignatureFlow, pk=self.kwargs['flow_id'])
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['flow'] = get_object_or_404(SignatureFlow, pk=self.kwargs['flow_id'])
        return context

    def get_success_url(self):
        return reverse('signatures:flow-detail', kwargs={'pk': self.kwargs['flow_id']})


class StepUpdateView(GrantManagerRequiredMixin, UpdateView):
    model = SignatureFlowStep
    form_class = FlowStepForm
    template_name = 'signatures/step_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['flow'] = self.object.flow
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['flow'] = self.object.flow
        return context

    def get_success_url(self):
        return reverse('signatures:flow-detail', kwargs={'pk': self.object.flow.pk})


class StepDeleteView(GrantManagerRequiredMixin, DeleteView):
    model = SignatureFlowStep
    template_name = 'signatures/step_confirm_delete.html'

    def get_success_url(self):
        return reverse('signatures:flow-detail', kwargs={'pk': self.object.flow.pk})


# ===========================================================================
# Document management
# ===========================================================================

class DocumentUploadView(GrantManagerRequiredMixin, CreateView):
    model = SignatureDocument
    form_class = SignatureDocumentForm
    template_name = 'signatures/document_upload.html'

    def form_valid(self, form):
        flow = get_object_or_404(SignatureFlow, pk=self.kwargs['flow_id'])
        form.instance.flow = flow
        form.instance.uploaded_by = self.request.user

        # Try to get page count from the PDF
        try:
            from pypdf import PdfReader
            reader = PdfReader(form.cleaned_data['file'])
            form.instance.page_count = len(reader.pages)
        except Exception:
            form.instance.page_count = 0

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['flow'] = get_object_or_404(SignatureFlow, pk=self.kwargs['flow_id'])
        return context

    def get_success_url(self):
        return reverse('signatures:flow-detail', kwargs={'pk': self.kwargs['flow_id']})


class DocumentDeleteView(GrantManagerRequiredMixin, DeleteView):
    model = SignatureDocument
    template_name = 'signatures/document_confirm_delete.html'

    def get_success_url(self):
        return reverse('signatures:flow-detail', kwargs={'pk': self.object.flow.pk})


# ===========================================================================
# Placement editor (any authenticated user)
# ===========================================================================

class PlacementEditorView(LoginRequiredMixin, TemplateView):
    template_name = 'signatures/placement_editor.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        document = get_object_or_404(SignatureDocument, pk=self.kwargs['document_id'])
        context['document'] = document
        context['flow'] = document.flow
        context['steps'] = document.flow.steps.order_by('order')
        context['placements_json'] = json.dumps([
            {
                'id': str(p.pk),
                'step_id': str(p.step_id),
                'step_label': p.step.label,
                'step_order': p.step.order,
                'field_type': p.field_type,
                'page_number': p.page_number,
                'x': p.x,
                'y': p.y,
                'width': p.width,
                'height': p.height,
            }
            for p in document.placements.select_related('step')
        ])
        context['steps_json'] = json.dumps([
            {
                'id': str(s.pk),
                'order': s.order,
                'label': s.label,
            }
            for s in document.flow.steps.order_by('order')
        ])
        return context


class PlacementAPIView(LoginRequiredMixin, View):
    """AJAX endpoint for managing signature placements on a document."""

    def get(self, request, document_id):
        document = get_object_or_404(SignatureDocument, pk=document_id)
        placements = [
            {
                'id': str(p.pk),
                'step_id': str(p.step_id),
                'field_type': p.field_type,
                'page_number': p.page_number,
                'x': p.x,
                'y': p.y,
                'width': p.width,
                'height': p.height,
            }
            for p in document.placements.all()
        ]
        return JsonResponse({'placements': placements})

    def post(self, request, document_id):
        document = get_object_or_404(SignatureDocument, pk=document_id)
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        placements_data = data.get('placements', [])
        created = []

        # Delete existing placements and recreate
        document.placements.all().delete()

        for p in placements_data:
            step = get_object_or_404(SignatureFlowStep, pk=p['step_id'])
            placement = SignaturePlacement.objects.create(
                document=document,
                step=step,
                field_type=p.get('field_type', 'signature'),
                page_number=p['page_number'],
                x=p['x'],
                y=p['y'],
                width=p.get('width', 20.0),
                height=p.get('height', 5.0),
            )
            created.append(str(placement.pk))

        return JsonResponse({'created': created, 'count': len(created)})

    def delete(self, request, document_id):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        placement_id = data.get('placement_id')
        if placement_id:
            SignaturePlacement.objects.filter(pk=placement_id, document_id=document_id).delete()
        return JsonResponse({'deleted': True})


# ===========================================================================
# Signing Packets
# ===========================================================================

class PacketListView(AgencyStaffRequiredMixin, SortableListMixin, ListView):
    model = SigningPacket
    template_name = 'signatures/packet_list.html'
    context_object_name = 'packets'
    paginate_by = 20
    sortable_fields = {
        'title': 'title',
        'status': 'status',
        'created_at': 'created_at',
    }
    default_sort = 'created_at'
    default_dir = 'desc'

    def get_queryset(self):
        qs = super().get_queryset().select_related('flow', 'initiated_by')
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return self.apply_sorting(qs)


class PacketInitiateView(AgencyStaffRequiredMixin, View):
    template_name = 'signatures/packet_initiate.html'

    def get(self, request, flow_id):
        flow = get_object_or_404(SignatureFlow, pk=flow_id, is_active=True)
        form = PacketInitiateForm(flow=flow)
        return self._render(request, flow, form)

    def post(self, request, flow_id):
        flow = get_object_or_404(SignatureFlow, pk=flow_id, is_active=True)
        form = PacketInitiateForm(request.POST, flow=flow)

        if not form.is_valid():
            return self._render(request, flow, form)

        # Build signer assignments
        signer_assignments = {}
        for step in flow.steps.all():
            field_name = f'signer_{step.pk}'
            user = form.cleaned_data.get(field_name)
            if user:
                signer_assignments[step.pk] = user

        packet = services.initiate_packet(
            flow=flow,
            title=form.cleaned_data['title'],
            initiated_by=request.user,
            signer_assignments=signer_assignments,
        )

        messages.success(request, _('Signing packet initiated successfully.'))
        return redirect('signatures:packet-detail', pk=packet.pk)

    def _render(self, request, flow, form):
        from django.template.response import TemplateResponse
        return TemplateResponse(request, self.template_name, {
            'flow': flow,
            'form': form,
        })


class PacketDetailView(LoginRequiredMixin, DetailView):
    model = SigningPacket
    template_name = 'signatures/packet_detail.html'
    context_object_name = 'packet'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['steps'] = self.object.steps.select_related(
            'signer', 'flow_step',
        ).order_by('order')
        return context


class PacketCancelView(AgencyStaffRequiredMixin, View):
    def post(self, request, pk):
        packet = get_object_or_404(SigningPacket, pk=pk)
        if packet.status not in [SigningPacket.Status.DRAFT, SigningPacket.Status.IN_PROGRESS]:
            messages.error(request, _('This packet cannot be cancelled.'))
            return redirect('signatures:packet-detail', pk=pk)

        reason = request.POST.get('cancel_reason', '')
        services.cancel_packet(packet, request.user, reason)
        messages.success(request, _('Signing packet has been cancelled.'))
        return redirect('signatures:packet-detail', pk=pk)


class PacketAuditView(AgencyStaffRequiredMixin, DetailView):
    model = SigningPacket
    template_name = 'signatures/packet_audit.html'
    context_object_name = 'packet'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        AuditLog = get_audit_log_model()
        if AuditLog is not None:
            context['audit_entries'] = AuditLog.objects.filter(
                entity_type__in=['SigningPacket', 'SigningStep'],
                entity_id__in=[str(self.object.pk)] + [
                    str(s.pk) for s in self.object.steps.all()
                ],
            ).order_by('-timestamp')
        else:
            context['audit_entries'] = []
        return context


# ===========================================================================
# Signing Interface (for signers)
# ===========================================================================

class SigningView(LoginRequiredMixin, TemplateView):
    template_name = 'signatures/sign.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        step = get_object_or_404(
            SigningStep.objects.select_related(
                'packet', 'packet__flow', 'flow_step', 'signer',
            ),
            pk=self.kwargs['step_id'],
        )
        context['step'] = step
        context['packet'] = step.packet
        context['form'] = SigningForm()
        context['decline_form'] = DeclineForm()

        # Get documents and their placements for this step
        documents = step.packet.flow.documents.all()
        context['documents'] = documents
        context['placements_json'] = json.dumps([
            {
                'document_id': str(p.document_id),
                'field_type': p.field_type,
                'page_number': p.page_number,
                'x': p.x,
                'y': p.y,
                'width': p.width,
                'height': p.height,
            }
            for doc in documents
            for p in doc.placements.filter(step=step.flow_step)
        ])

        # User's saved signatures
        context['saved_signatures'] = UserSignature.objects.filter(
            user=self.request.user,
        )
        return context

    def dispatch(self, request, *args, **kwargs):
        step = get_object_or_404(SigningStep, pk=kwargs['step_id'])
        if step.signer != request.user:
            messages.error(request, _('You are not authorized to sign this step.'))
            return redirect('signatures:my-signatures')
        if step.status != SigningStep.Status.ACTIVE:
            messages.error(request, _('This step is not currently active for signing.'))
            return redirect('signatures:packet-detail', pk=step.packet.pk)
        return super().dispatch(request, *args, **kwargs)


class SigningCompleteView(LoginRequiredMixin, View):
    def post(self, request, step_id):
        step = get_object_or_404(SigningStep, pk=step_id)

        # Validate access
        if step.signer != request.user:
            messages.error(request, _('You are not authorized to sign this step.'))
            return redirect('signatures:my-signatures')
        if step.status != SigningStep.Status.ACTIVE:
            messages.error(request, _('This step is not currently active for signing.'))
            return redirect('signatures:packet-detail', pk=step.packet.pk)

        form = SigningForm(request.POST, request.FILES)
        if not form.is_valid():
            messages.error(request, _('Please provide a valid signature.'))
            return redirect('signatures:sign', step_id=step_id)

        sig_type = form.cleaned_data['signature_type']
        ip_address = getattr(request, 'audit_ip', request.META.get('REMOTE_ADDR'))

        if sig_type == 'typed':
            signature_data = form.cleaned_data['typed_name']
        elif sig_type == 'uploaded':
            signature_data = form.cleaned_data['signature_image']
        elif sig_type == 'drawn':
            signature_data = form.cleaned_data['drawn_data']
        else:
            messages.error(request, _('Invalid signature type.'))
            return redirect('signatures:sign', step_id=step_id)

        services.complete_step(step, sig_type, signature_data, ip_address)

        messages.success(request, _('Your signature has been recorded. Thank you.'))

        # Check if packet is now completed
        step.refresh_from_db()
        if step.packet.status == SigningPacket.Status.COMPLETED:
            return redirect('signatures:packet-detail', pk=step.packet.pk)
        return redirect('signatures:my-signatures')


class SigningDeclineView(LoginRequiredMixin, View):
    def post(self, request, step_id):
        step = get_object_or_404(SigningStep, pk=step_id)

        if step.signer != request.user:
            messages.error(request, _('You are not authorized for this step.'))
            return redirect('signatures:my-signatures')
        if step.status != SigningStep.Status.ACTIVE:
            messages.error(request, _('This step is not currently active.'))
            return redirect('signatures:packet-detail', pk=step.packet.pk)

        form = DeclineForm(request.POST)
        if not form.is_valid():
            messages.error(request, _('Please provide a reason for declining.'))
            return redirect('signatures:sign', step_id=step_id)

        ip_address = getattr(request, 'audit_ip', request.META.get('REMOTE_ADDR'))
        services.decline_step(step, form.cleaned_data['decline_reason'], ip_address)

        messages.info(request, _('You have declined to sign this document.'))
        return redirect('signatures:my-signatures')


# ===========================================================================
# My Signatures
# ===========================================================================

class MySignaturesView(LoginRequiredMixin, ListView):
    template_name = 'signatures/my_signatures.html'
    context_object_name = 'steps'

    def get_queryset(self):
        return (
            SigningStep.objects
            .filter(signer=self.request.user)
            .select_related('packet', 'packet__flow', 'flow_step')
            .order_by('-created_at')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = self.get_queryset()
        context['pending_steps'] = qs.filter(status=SigningStep.Status.ACTIVE)
        context['completed_steps'] = qs.filter(
            status__in=[SigningStep.Status.SIGNED, SigningStep.Status.DECLINED],
        )
        return context


# ===========================================================================
# User Signature Management
# ===========================================================================

class UserSignatureListView(LoginRequiredMixin, ListView):
    template_name = 'signatures/user_signature_list.html'
    context_object_name = 'signatures'

    def get_queryset(self):
        return UserSignature.objects.filter(user=self.request.user)


class UserSignatureCreateView(LoginRequiredMixin, CreateView):
    model = UserSignature
    form_class = UserSignatureForm
    template_name = 'signatures/user_signature_form.html'
    success_url = reverse_lazy('signatures:user-signature-list')

    def form_valid(self, form):
        form.instance.user = self.request.user

        # Handle drawn signature from hidden field
        drawn_data = self.request.POST.get('drawn_data', '')
        if form.instance.signature_type == 'drawn' and drawn_data:
            import base64
            from django.core.files.base import ContentFile
            img_data = drawn_data
            if ',' in img_data:
                img_data = img_data.split(',', 1)[1]
            decoded = base64.b64decode(img_data)
            filename = f'saved_sig_{self.request.user.pk}.png'
            form.instance.signature_image.save(filename, ContentFile(decoded), save=False)

        return super().form_valid(form)


class UserSignatureDeleteView(LoginRequiredMixin, DeleteView):
    model = UserSignature
    template_name = 'signatures/user_signature_confirm_delete.html'
    success_url = reverse_lazy('signatures:user-signature-list')

    def get_queryset(self):
        return UserSignature.objects.filter(user=self.request.user)


class UserSignatureSetDefaultView(LoginRequiredMixin, View):
    def post(self, request, pk):
        sig = get_object_or_404(UserSignature, pk=pk, user=request.user)
        # Clear all defaults for this user, then set this one
        UserSignature.objects.filter(user=request.user).update(is_default=False)
        sig.is_default = True
        sig.save(update_fields=['is_default', 'updated_at'])
        messages.success(request, _('Default signature updated.'))
        return redirect('signatures:user-signature-list')


# ===========================================================================
# AJAX endpoints
# ===========================================================================

class PacketStatusAPIView(LoginRequiredMixin, View):
    def get(self, request, pk):
        packet = get_object_or_404(SigningPacket, pk=pk)
        signed, total = packet.progress
        steps = [
            {
                'order': s.order,
                'label': s.flow_step.label,
                'signer': s.signer.get_full_name(),
                'status': s.status,
                'signed_at': s.signed_at.isoformat() if s.signed_at else None,
            }
            for s in packet.steps.select_related('signer', 'flow_step').order_by('order')
        ]
        return JsonResponse({
            'status': packet.status,
            'progress': {'signed': signed, 'total': total},
            'steps': steps,
        })


class StepRemindAPIView(AgencyStaffRequiredMixin, View):
    def post(self, request, pk):
        step = get_object_or_404(SigningStep, pk=pk, status=SigningStep.Status.ACTIVE)
        services.send_reminder(step)
        return JsonResponse({'reminded': True})


# ===========================================================================
# Template Builder Wizard
# ===========================================================================

class TemplateBuilderView(GrantManagerRequiredMixin, TemplateView):
    """Single-page wizard for creating/editing a complete signature flow."""
    template_name = 'signatures/template_builder.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        flow_id = self.kwargs.get('pk')

        if flow_id:
            # Edit mode
            flow = get_object_or_404(SignatureFlow, pk=flow_id)
            context['flow'] = flow
            context['flow_json'] = json.dumps({
                'id': str(flow.pk),
                'name': flow.name,
                'description': flow.description,
                'is_active': flow.is_active,
            })
            context['steps_json'] = json.dumps([
                {
                    'id': str(s.pk),
                    'order': s.order,
                    'label': s.label,
                    'assignment_type': s.assignment_type,
                    'assigned_user': str(s.assigned_user_id) if s.assigned_user_id else '',
                    'assigned_user_name': (
                        s.assigned_user.get_full_name() if s.assigned_user else ''
                    ),
                    'assigned_role': s.assigned_role,
                    'is_required': s.is_required,
                }
                for s in flow.steps.order_by('order').select_related('assigned_user')
            ])
            documents = flow.documents.all()
            context['documents_json'] = json.dumps([
                {
                    'id': str(d.pk),
                    'title': d.title,
                    'description': d.description,
                    'file_url': d.file.url if d.file else '',
                    'page_count': d.page_count,
                    'placements': [
                        {
                            'id': str(p.pk),
                            'step_id': str(p.step_id),
                            'step_label': p.step.label,
                            'step_order': p.step.order,
                            'field_type': p.field_type,
                            'page_number': p.page_number,
                            'x': float(p.x),
                            'y': float(p.y),
                            'width': float(p.width),
                            'height': float(p.height),
                        }
                        for p in d.placements.select_related('step')
                    ],
                }
                for d in documents.prefetch_related('placements__step')
            ])
        else:
            # Create mode
            context['flow'] = None
            context['flow_json'] = json.dumps(None)
            context['steps_json'] = json.dumps([])
            context['documents_json'] = json.dumps([])

        # Provide assignable users and roles for step assignment
        from .compat import get_assignable_users, get_role_choices
        context['users_json'] = json.dumps([
            {'id': str(u.pk), 'name': u.get_full_name() or u.username}
            for u in get_assignable_users()
        ])
        context['roles_json'] = json.dumps(get_role_choices())
        return context


class TemplateBuilderSaveAPIView(GrantManagerRequiredMixin, View):
    """AJAX endpoint that saves the entire template in one transaction."""

    def post(self, request, pk=None):
        try:
            payload = json.loads(request.POST.get('payload', '{}'))
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON payload'}, status=400)

        errors = self._validate(payload, request.FILES, pk)
        if errors:
            return JsonResponse({'errors': errors}, status=400)

        from django.db import transaction
        try:
            with transaction.atomic():
                flow = self._save_flow(payload, request.user, pk)
                step_id_map = self._save_steps(flow, payload.get('steps', []))
                self._save_document_and_placements(
                    flow, payload, request.FILES, request.user, step_id_map,
                )
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

        return JsonResponse({
            'success': True,
            'flow_id': str(flow.pk),
            'redirect_url': reverse(
                'signatures:flow-detail', kwargs={'pk': flow.pk},
            ),
        })

    def _validate(self, payload, files, existing_pk):
        errors = []
        if not payload.get('name', '').strip():
            errors.append({'field': 'name', 'message': _('Flow name is required.')})
        steps = payload.get('steps', [])
        if len(steps) < 1:
            errors.append({
                'field': 'steps',
                'message': _('At least one signing step is required.'),
            })
        for i, step in enumerate(steps):
            if not step.get('label', '').strip():
                errors.append({
                    'field': f'steps[{i}].label',
                    'message': _('Step %(num)s label is required.') % {'num': i + 1},
                })
        if not existing_pk and 'document' not in files:
            if not payload.get('existing_document_id'):
                errors.append({
                    'field': 'document',
                    'message': _('A PDF document is required.'),
                })
        return errors

    def _save_flow(self, payload, user, existing_pk):
        if existing_pk:
            flow = get_object_or_404(SignatureFlow, pk=existing_pk)
            flow.name = payload['name'].strip()
            flow.description = payload.get('description', '')
            flow.is_active = payload.get('is_active', True)
            flow.save()
        else:
            flow = SignatureFlow.objects.create(
                name=payload['name'].strip(),
                description=payload.get('description', ''),
                is_active=payload.get('is_active', True),
                created_by=user,
            )
        return flow

    def _save_steps(self, flow, steps_data):
        """Delete existing steps and recreate.  Returns temp_id -> real UUID map."""
        flow.steps.all().delete()
        step_id_map = {}
        for i, s in enumerate(steps_data):
            step = SignatureFlowStep.objects.create(
                flow=flow,
                order=i + 1,
                label=s['label'].strip(),
                assignment_type=s.get('assignment_type', 'role'),
                assigned_user_id=s.get('assigned_user') or None,
                assigned_role=s.get('assigned_role', ''),
                is_required=s.get('is_required', True),
            )
            temp_id = s.get('temp_id') or s.get('id', '')
            step_id_map[temp_id] = str(step.pk)
        return step_id_map

    def _save_document_and_placements(
        self, flow, payload, files, user, step_id_map,
    ):
        pdf_file = files.get('document')
        existing_doc_id = payload.get('existing_document_id')

        if pdf_file:
            flow.documents.all().delete()
            page_count = 0
            try:
                from pypdf import PdfReader
                reader = PdfReader(pdf_file)
                page_count = len(reader.pages)
                pdf_file.seek(0)
            except Exception:
                pass
            doc = SignatureDocument.objects.create(
                flow=flow,
                title=payload.get('document_title') or pdf_file.name,
                description=payload.get('document_description', ''),
                file=pdf_file,
                page_count=page_count,
                uploaded_by=user,
            )
        elif existing_doc_id:
            doc = get_object_or_404(
                SignatureDocument, pk=existing_doc_id, flow=flow,
            )
            doc.placements.all().delete()
        else:
            return

        for p in payload.get('placements', []):
            real_step_id = step_id_map.get(p['step_id'], p['step_id'])
            SignaturePlacement.objects.create(
                document=doc,
                step_id=real_step_id,
                field_type=p.get('field_type', 'signature'),
                page_number=p['page_number'],
                x=p['x'],
                y=p['y'],
                width=p.get('width', 20.0),
                height=p.get('height', 5.0),
            )
