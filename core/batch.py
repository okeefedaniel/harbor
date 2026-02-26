"""Batch / bulk operations for agency staff."""
import csv
import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views import View

from applications.models import Application, ApplicationStatusHistory
from awards.models import Award
from core.audit import log_audit
from core.mixins import AgencyStaffRequiredMixin, FiscalOfficerRequiredMixin, GrantManagerRequiredMixin
from core.models import AuditLog
from financial.models import DrawdownRequest

logger = logging.getLogger(__name__)


class BulkApplicationStatusChangeView(GrantManagerRequiredMixin, View):
    """POST-only: change status for multiple applications at once.

    Expects POST body with:
    - application_ids: comma-separated UUIDs
    - new_status: target status string
    - comment: required comment for the change
    """
    http_method_names = ['post']

    VALID_TRANSITIONS = {
        'submitted': ['under_review'],
        'under_review': ['approved', 'denied', 'revision_requested'],
    }

    def post(self, request):
        ids_raw = request.POST.get('application_ids', '')
        new_status = request.POST.get('new_status', '')
        comment = request.POST.get('comment', '').strip()

        if not ids_raw or not new_status:
            messages.error(request, _('Missing required fields.'))
            return redirect('applications:list')

        if not comment:
            messages.error(request, _('A comment is required for bulk status changes.'))
            return redirect('applications:list')

        app_ids = [uid.strip() for uid in ids_raw.split(',') if uid.strip()]
        applications = Application.objects.filter(pk__in=app_ids)

        success_count = 0
        skip_count = 0

        for app in applications:
            allowed = self.VALID_TRANSITIONS.get(app.status, [])
            if new_status not in allowed:
                skip_count += 1
                continue

            old_status = app.status
            app.status = new_status
            app.save(update_fields=['status', 'updated_at'])

            ApplicationStatusHistory.objects.create(
                application=app,
                old_status=old_status,
                new_status=new_status,
                changed_by=request.user,
                comment=_('[Bulk action] %(comment)s') % {'comment': comment},
            )

            log_audit(
                user=request.user,
                action=AuditLog.Action.STATUS_CHANGE,
                entity_type='Application',
                entity_id=str(app.pk),
                description=f'Bulk status change: {old_status} -> {new_status}',
                changes={'old_status': old_status, 'new_status': new_status},
                ip_address=getattr(request, 'audit_ip', None),
            )

            success_count += 1

        if success_count:
            messages.success(
                request,
                _('Successfully updated %(count)d application(s).') % {'count': success_count},
            )
        if skip_count:
            messages.warning(
                request,
                _('Skipped %(count)d application(s) due to invalid transition.') % {'count': skip_count},
            )

        return redirect('applications:list')


class BulkDrawdownApproveView(FiscalOfficerRequiredMixin, View):
    """POST-only: approve multiple drawdown requests at once.

    Expects POST body with:
    - drawdown_ids: comma-separated UUIDs
    """
    http_method_names = ['post']

    def post(self, request):
        ids_raw = request.POST.get('drawdown_ids', '')
        if not ids_raw:
            messages.error(request, _('No drawdown requests selected.'))
            return redirect('financial:drawdown-list')

        dr_ids = [uid.strip() for uid in ids_raw.split(',') if uid.strip()]
        drawdowns = DrawdownRequest.objects.filter(
            pk__in=dr_ids,
            status=DrawdownRequest.Status.SUBMITTED,
        )

        count = 0
        for dr in drawdowns:
            dr.status = DrawdownRequest.Status.APPROVED
            dr.reviewed_by = request.user
            dr.reviewed_at = timezone.now()
            dr.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'updated_at'])

            log_audit(
                user=request.user,
                action=AuditLog.Action.APPROVE,
                entity_type='DrawdownRequest',
                entity_id=str(dr.pk),
                description=f'Bulk approval: drawdown "{dr.request_number}" approved.',
                ip_address=getattr(request, 'audit_ip', None),
            )
            count += 1

        messages.success(request, _('Successfully approved %(count)d drawdown request(s).') % {'count': count})
        return redirect('financial:drawdown-list')


class BulkAwardExportView(AgencyStaffRequiredMixin, View):
    """Export multiple awards to CSV with full financial details."""
    http_method_names = ['get', 'post']

    def get(self, request):
        return self._export(request)

    def post(self, request):
        return self._export(request)

    def _export(self, request):
        from django.db.models import Sum

        ids_raw = request.GET.get('award_ids', '') or request.POST.get('award_ids', '')

        qs = Award.objects.select_related(
            'grant_program', 'agency', 'recipient', 'organization',
        )

        if ids_raw:
            award_ids = [uid.strip() for uid in ids_raw.split(',') if uid.strip()]
            qs = qs.filter(pk__in=award_ids)

        # Agency scoping for non-system-admins
        user = request.user
        if user.role != 'system_admin' and user.agency_id:
            qs = qs.filter(agency=user.agency)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="awards_export.csv"'

        writer = csv.writer(response)
        writer.writerow([
            _('Award Number'), _('Title'), _('Grant Program'), _('Agency'),
            _('Recipient'), _('Organization'), _('Status'), _('Award Amount'),
            _('Start Date'), _('End Date'), _('Total Spent'), _('Remaining'),
        ])

        for award in qs:
            total_spent = award.transactions.filter(
                transaction_type__in=['payment', 'drawdown'],
            ).aggregate(total=Sum('amount'))['total'] or 0
            remaining = award.award_amount - total_spent

            writer.writerow([
                award.award_number,
                award.title,
                award.grant_program.title,
                award.agency.abbreviation if award.agency else '',
                award.recipient.get_full_name() if award.recipient else '',
                award.organization.name if award.organization else '',
                award.get_status_display(),
                award.award_amount,
                award.start_date,
                award.end_date,
                total_spent,
                remaining,
            ])

        return response
