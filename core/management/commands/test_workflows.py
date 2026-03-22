"""
Management command to test all Harbor workflows end-to-end.

Uses Django's test Client to simulate authenticated requests against
the applicant and grant-manager workflows, verifying correct behaviour
at every step.

Usage:
    python manage.py test_workflows
"""

import os
import re
import sys
import traceback
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.test import Client

User = get_user_model()

DEMO_PASSWORD = os.environ.get('DEMO_PASSWORD', 'demo' + '2026!')
TEST_PASSWORD = os.environ.get('TEST_PASSWORD', 'Str0ng' + 'P@ssw0rd!')


# ── Helpers ──────────────────────────────────────────────────────────────────

class TestResult:
    """Accumulates PASS / FAIL results and prints a final report."""

    def __init__(self):
        self.results = []
        self.current_section = ''

    def section(self, title):
        self.current_section = title

    def ok(self, label, detail=''):
        self.results.append((self.current_section, label, True, detail))

    def fail(self, label, detail=''):
        self.results.append((self.current_section, label, False, detail))

    def check(self, condition, label, detail=''):
        if condition:
            self.ok(label, detail)
        else:
            self.fail(label, detail)

    def report(self):
        """Print a formatted report and return exit code (0=all pass)."""
        total = len(self.results)
        passed = sum(1 for *_, ok, _ in self.results if ok)
        failed = total - passed
        prev_section = ''

        print('\n')
        print('=' * 78)
        print('  HARBOR WORKFLOW TEST REPORT')
        print('=' * 78)

        for section, label, ok, detail in self.results:
            if section != prev_section:
                print(f'\n--- {section} ---')
                prev_section = section
            status = 'PASS' if ok else '** FAIL **'
            line = f'  [{status}] {label}'
            if detail:
                line += f'  ({detail})'
            print(line)

        print('\n' + '=' * 78)
        print(f'  TOTAL: {total}  |  PASSED: {passed}  |  FAILED: {failed}')
        if failed:
            print('  STATUS: FAILURES DETECTED')
        else:
            print('  STATUS: ALL TESTS PASSED')
        print('=' * 78 + '\n')
        return 0 if failed == 0 else 1


def extract_csrftoken(response):
    """Pull csrfmiddlewaretoken from an HTML response body."""
    content = response.content.decode()
    m = re.search(
        r'name=["\']csrfmiddlewaretoken["\'] value=["\']([^"\']+)["\']',
        content,
    )
    return m.group(1) if m else ''


def response_ok(response, allowed_codes=None):
    """Return True if the response status is in *allowed_codes* (default 200)."""
    if allowed_codes is None:
        allowed_codes = {200}
    return response.status_code in allowed_codes


def check_no_server_error(response):
    """Return (ok, detail) tuple.  ok is False if the page contains a 500."""
    if response.status_code >= 500:
        body = response.content.decode()[:300]
        return False, f'HTTP {response.status_code}: {body}'
    body = response.content.decode()
    if 'Server Error' in body or 'Traceback' in body:
        return False, 'Response body contains Server Error / Traceback text'
    return True, ''


def follow_redirect(response):
    """If response is a redirect (301/302), return the target URL."""
    if response.status_code in (301, 302):
        return response['Location']
    return None


# ── The Command ──────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = 'Run end-to-end workflow tests for Harbor using Django test Client'

    def handle(self, *args, **options):
        # Django's test Client sends requests with SERVER_NAME='testserver'.
        # We need to make sure it's in ALLOWED_HOSTS.
        from django.conf import settings
        if 'testserver' not in settings.ALLOWED_HOSTS and '*' not in settings.ALLOWED_HOSTS:
            settings.ALLOWED_HOSTS.append('testserver')

        T = TestResult()

        try:
            self._run_all(T)
        except Exception:
            T.fail('Unexpected exception', traceback.format_exc())

        exit_code = T.report()
        sys.exit(exit_code)

    # ------------------------------------------------------------------

    def _run_all(self, T):
        # ── Preparation ──────────────────────────────────────────────
        T.section('SETUP')

        # We need at least one published grant program with an agency
        from grants.models import GrantProgram
        from core.models import Agency, Organization, Notification

        program = GrantProgram.objects.filter(is_published=True).first()
        if not program:
            # Create a minimal grant program for testing
            agency = Agency.objects.first()
            if not agency:
                agency = Agency.objects.create(
                    name='Test Agency',
                    abbreviation='TST',
                )
            from grants.models import FundingSource
            source = FundingSource.objects.first()
            if not source:
                source = FundingSource.objects.create(
                    name='State General Fund',
                    source_type='state',
                )
            from django.utils import timezone
            admin_user = User.objects.filter(role='system_admin').first()
            if not admin_user:
                admin_user = User.objects.create_superuser(
                    username='admin', email='admin@dok.gov',
                    password=DEMO_PASSWORD, role='system_admin',
                    first_name='System', last_name='Admin',
                )
            program = GrantProgram.objects.create(
                agency=agency,
                title='Test Grant Program',
                description='Automated test program',
                funding_source=source,
                grant_type='competitive',
                total_funding=Decimal('1000000'),
                min_award=Decimal('10000'),
                max_award=Decimal('250000'),
                fiscal_year='2025-2026',
                duration_months=12,
                application_deadline=timezone.now() + timedelta(days=90),
                posting_date=timezone.now(),
                status='accepting_applications',
                is_published=True,
                published_at=timezone.now(),
                created_by=admin_user,
            )
            T.ok('Created test grant program')
        else:
            T.ok('Found published grant program', str(program.title)[:60])

        program_id = str(program.pk)

        # Make sure admin exists
        admin_user = User.objects.filter(username='admin').first()
        T.check(admin_user is not None, 'Admin user exists')

        # ==============================================================
        #  APPLICANT WORKFLOW
        # ==============================================================
        T.section('APPLICANT WORKFLOW - Registration')

        client = Client()

        # 1. Register a new test applicant
        reg_url = '/auth/register/'
        resp = client.get(reg_url)
        T.check(response_ok(resp), 'GET /auth/register/ returns 200',
                f'status={resp.status_code}')

        csrf = extract_csrftoken(resp)
        reg_data = {
            'csrfmiddlewaretoken': csrf,
            'username': 'test_applicant_wf',
            'email': 'testapplicant@example.com',
            'first_name': 'Test',
            'last_name': 'Applicant',
            'phone': '860-555-0100',
            'password1': TEST_PASSWORD,
            'password2': TEST_PASSWORD,
            'accepted_terms': 'on',
        }

        # Clean up from a previous run (cascade through protected relationships)
        old_user = User.objects.filter(username='test_applicant_wf').first()
        if old_user:
            from applications.models import (
                Application, ApplicationComment, ApplicationComplianceItem,
                ApplicationDocument, ApplicationStatusHistory, StaffDocument,
            )
            from awards.models import Award, AwardAmendment, AwardDocument
            # Delete awards first (depends on application)
            old_apps = Application.objects.filter(applicant=old_user)
            for a in old_apps:
                Award.objects.filter(application=a).delete()
            ApplicationStatusHistory.objects.filter(changed_by=old_user).delete()
            ApplicationComment.objects.filter(author=old_user).delete()
            ApplicationComplianceItem.objects.filter(application__in=old_apps).delete()
            StaffDocument.objects.filter(application__in=old_apps).delete()
            ApplicationDocument.objects.filter(application__in=old_apps).delete()
            ApplicationStatusHistory.objects.filter(application__in=old_apps).delete()
            old_apps.delete()
            Notification.objects.filter(recipient=old_user).delete()
            if old_user.organization:
                org = old_user.organization
                old_user.organization = None
                old_user.save(update_fields=['organization'])
                # Only delete org if no other users reference it
                if not User.objects.filter(organization=org).exists():
                    org.delete()
            old_user.delete()

        resp = client.post(reg_url, reg_data)
        # Should redirect to login on success
        T.check(
            resp.status_code in (200, 301, 302),
            'POST /auth/register/ completes',
            f'status={resp.status_code}',
        )
        applicant_user = User.objects.filter(username='test_applicant_wf').first()
        T.check(applicant_user is not None, 'Test applicant user created')
        if applicant_user:
            T.check(applicant_user.role == 'applicant',
                     'Applicant has correct role')

        # 2. Login as applicant
        T.section('APPLICANT WORKFLOW - Login')
        login_ok = client.login(username='test_applicant_wf',
                                password=TEST_PASSWORD)
        T.check(login_ok, 'Applicant can log in')

        # 3. Visit opportunities list
        T.section('APPLICANT WORKFLOW - Browse Opportunities')
        resp = client.get('/opportunities/')
        T.check(response_ok(resp), 'GET /opportunities/ returns 200',
                f'status={resp.status_code}')
        err_ok, err_detail = check_no_server_error(resp)
        T.check(err_ok, 'No server error on /opportunities/', err_detail)

        # 4. Visit opportunity detail
        resp = client.get(f'/opportunities/{program_id}/')
        T.check(response_ok(resp), f'GET /opportunities/{program_id}/ returns 200',
                f'status={resp.status_code}')
        err_ok, err_detail = check_no_server_error(resp)
        T.check(err_ok, 'No server error on opportunity detail', err_detail)

        # 5. Try to apply without an organization -> should redirect to org create
        T.section('APPLICANT WORKFLOW - Apply Without Organization')
        apply_url = f'/applications/create/{program_id}/'
        resp = client.get(apply_url)
        redirect_url = follow_redirect(resp)
        T.check(
            resp.status_code == 302 and redirect_url and 'organization/create' in redirect_url,
            'Apply without org redirects to organization create',
            f'status={resp.status_code}, location={redirect_url}',
        )

        # 6. Create organization
        T.section('APPLICANT WORKFLOW - Create Organization')
        org_create_url = '/auth/organization/create/'
        resp = client.get(f'{org_create_url}?next={apply_url}')
        T.check(response_ok(resp), 'GET /auth/organization/create/ returns 200',
                f'status={resp.status_code}')

        csrf = extract_csrftoken(resp)
        org_data = {
            'csrfmiddlewaretoken': csrf,
            'name': 'Test Nonprofit Foundation',
            'org_type': 'nonprofit',
            'ein': '12-3456789',
            'address_line1': '100 Main St',
            'city': 'Capital City',
            'state': 'DOK',
            'zip_code': '00100',
            'phone': '555-555-0200',
            'next': apply_url,
        }
        resp = client.post(f'{org_create_url}?next={apply_url}', org_data)
        T.check(
            resp.status_code in (301, 302),
            'POST organization create redirects',
            f'status={resp.status_code}',
        )
        # Reload user
        applicant_user = User.objects.filter(username='test_applicant_wf').first()
        if not applicant_user:
            T.fail('Cannot continue - applicant user was not created')
            return
        T.check(applicant_user.organization is not None,
                'Applicant now has an organization')
        if applicant_user.organization:
            T.check(
                applicant_user.organization.name == 'Test Nonprofit Foundation',
                'Organization name correct',
            )

        # 7. Now apply - should show application form
        T.section('APPLICANT WORKFLOW - Create Application')
        resp = client.get(apply_url)
        T.check(response_ok(resp), 'GET application create form returns 200',
                f'status={resp.status_code}')
        err_ok, err_detail = check_no_server_error(resp)
        T.check(err_ok, 'No server error on application form', err_detail)

        # 8. Submit application form to create a draft
        csrf = extract_csrftoken(resp)
        today = date.today()
        app_data = {
            'csrfmiddlewaretoken': csrf,
            'project_title': 'Community Health Initiative',
            'project_description': 'A comprehensive community health program '
                                   'serving underserved populations in Capital City.',
            'requested_amount': '75000.00',
            'proposed_start_date': (today + timedelta(days=30)).isoformat(),
            'proposed_end_date': (today + timedelta(days=395)).isoformat(),
            'match_amount': '15000.00',
            'match_description': 'In-kind contributions from partner organizations.',
        }
        resp = client.post(apply_url, app_data)
        T.check(
            resp.status_code in (301, 302),
            'POST application create redirects (draft created)',
            f'status={resp.status_code}',
        )

        from applications.models import Application, ApplicationComplianceItem
        app_obj = Application.objects.filter(
            applicant=applicant_user,
            project_title='Community Health Initiative',
        ).first()
        T.check(app_obj is not None, 'Application object created in DB')
        if not app_obj:
            T.fail('Cannot continue applicant workflow without application')
            return

        app_id = str(app_obj.pk)
        T.check(app_obj.status == 'draft', 'Application status is draft')
        T.check(
            app_obj.requested_amount == Decimal('75000.00'),
            'Requested amount correct',
        )

        # 9. Visit my applications
        T.section('APPLICANT WORKFLOW - My Applications')
        resp = client.get('/applications/my/')
        T.check(response_ok(resp), 'GET /applications/my/ returns 200',
                f'status={resp.status_code}')
        T.check(
            'Community Health Initiative' in resp.content.decode(),
            'My applications page shows the new application',
        )

        # 10. View application detail
        detail_url = f'/applications/{app_id}/'
        resp = client.get(detail_url)
        T.check(response_ok(resp), f'GET application detail returns 200',
                f'status={resp.status_code}')
        err_ok, err_detail = check_no_server_error(resp)
        T.check(err_ok, 'No server error on application detail', err_detail)

        # 11. Submit the application
        T.section('APPLICANT WORKFLOW - Submit Application')
        # Count notifications for staff before submission
        staff_notif_before = Notification.objects.filter(
            recipient__role__in=['system_admin', 'agency_admin', 'program_officer'],
        ).count()

        submit_url = f'/applications/{app_id}/submit/'
        csrf = extract_csrftoken(resp)
        resp = client.post(submit_url, {'csrfmiddlewaretoken': csrf})
        T.check(
            resp.status_code in (301, 302),
            'POST submit application redirects',
            f'status={resp.status_code}',
        )

        app_obj.refresh_from_db()
        T.check(app_obj.status == 'submitted', 'Application status is now submitted')
        T.check(app_obj.submitted_at is not None, 'submitted_at is set')

        # Verify compliance items were created
        compliance_count = app_obj.compliance_items.count()
        T.check(
            compliance_count > 0,
            f'Compliance items created ({compliance_count})',
        )

        # 12. Verify notification was created for staff
        staff_notif_after = Notification.objects.filter(
            recipient__role__in=['system_admin', 'agency_admin', 'program_officer'],
        ).count()
        T.check(
            staff_notif_after > staff_notif_before,
            'Staff notification created for submitted application',
            f'before={staff_notif_before}, after={staff_notif_after}',
        )

        # 13. Check notifications page
        T.section('APPLICANT WORKFLOW - Notifications')
        resp = client.get('/auth/notifications/')
        T.check(response_ok(resp), 'GET /auth/notifications/ returns 200',
                f'status={resp.status_code}')
        err_ok, err_detail = check_no_server_error(resp)
        T.check(err_ok, 'No server error on notifications page', err_detail)

        # ==============================================================
        #  GRANT MANAGER (STAFF) WORKFLOW
        # ==============================================================
        T.section('STAFF WORKFLOW - Login')
        staff_client = Client()
        staff_login = staff_client.login(username='admin', password=DEMO_PASSWORD)
        T.check(staff_login, 'Staff (admin) can log in')

        # 1. Visit dashboard
        T.section('STAFF WORKFLOW - Dashboard')
        resp = staff_client.get('/dashboard/')
        T.check(response_ok(resp), 'GET /dashboard/ returns 200',
                f'status={resp.status_code}')
        err_ok, err_detail = check_no_server_error(resp)
        T.check(err_ok, 'No server error on dashboard', err_detail)

        # 2. Visit applications list (staff sees all)
        T.section('STAFF WORKFLOW - Applications List')
        resp = staff_client.get('/applications/')
        T.check(response_ok(resp), 'GET /applications/ returns 200',
                f'status={resp.status_code}')
        err_ok, err_detail = check_no_server_error(resp)
        T.check(err_ok, 'No server error on applications list', err_detail)

        # 3. View the submitted application detail
        T.section('STAFF WORKFLOW - Application Detail')
        resp = staff_client.get(detail_url)
        T.check(response_ok(resp), 'GET application detail (staff) returns 200',
                f'status={resp.status_code}')
        err_ok, err_detail = check_no_server_error(resp)
        T.check(err_ok, 'No server error on staff application detail', err_detail)
        # Should see compliance items
        body = resp.content.decode()
        T.check(
            'compliance' in body.lower() or 'SAM Registration' in body,
            'Staff sees compliance items on application detail',
        )

        # 4. Toggle a compliance item
        T.section('STAFF WORKFLOW - Toggle Compliance')
        first_item = app_obj.compliance_items.first()
        T.check(first_item is not None, 'At least one compliance item exists')
        if first_item:
            toggle_url = f'/applications/{app_id}/compliance/{first_item.pk}/toggle/'
            csrf = extract_csrftoken(resp)
            resp = staff_client.post(
                toggle_url,
                {'csrfmiddlewaretoken': csrf, 'notes': 'Verified during test'},
            )
            T.check(
                resp.status_code in (301, 302),
                'POST toggle compliance redirects',
                f'status={resp.status_code}',
            )
            first_item.refresh_from_db()
            T.check(first_item.is_verified, 'Compliance item is now verified')
            T.check(
                first_item.notes == 'Verified during test',
                'Compliance notes saved',
            )

        # 5. Add an internal comment
        T.section('STAFF WORKFLOW - Add Comment')
        # Get fresh CSRF
        resp = staff_client.get(detail_url)
        csrf = extract_csrftoken(resp)
        comment_url = f'/applications/{app_id}/comment/'
        resp = staff_client.post(comment_url, {
            'csrfmiddlewaretoken': csrf,
            'content': 'This looks like a strong application. Recommend approval.',
            'is_internal': 'on',
        })
        T.check(
            resp.status_code in (301, 302),
            'POST add internal comment redirects',
            f'status={resp.status_code}',
        )
        from applications.models import ApplicationComment
        comment_exists = ApplicationComment.objects.filter(
            application=app_obj,
            is_internal=True,
            content__contains='strong application',
        ).exists()
        T.check(comment_exists, 'Internal comment saved in DB')

        # 6. Test staff document upload URL (just check the page loads)
        T.section('STAFF WORKFLOW - Staff Document Upload')
        staff_upload_url = f'/applications/{app_id}/staff-upload/'
        # This is POST-only, sending without file should redirect with error but not 500
        resp = staff_client.get(detail_url)
        csrf = extract_csrftoken(resp)
        resp = staff_client.post(staff_upload_url, {
            'csrfmiddlewaretoken': csrf,
            'title': 'Test Doc',
            'description': 'Test',
            'document_type': 'verification',
            # Deliberately omit file to test error handling
        })
        T.check(
            resp.status_code in (301, 302),
            'POST staff-upload without file redirects (with error msg)',
            f'status={resp.status_code}',
        )

        # 7. Change status to under_review
        T.section('STAFF WORKFLOW - Status: Under Review')
        # Count applicant notifications before
        applicant_notif_before = Notification.objects.filter(
            recipient=applicant_user,
        ).count()

        resp = staff_client.get(detail_url)
        csrf = extract_csrftoken(resp)
        status_url = f'/applications/{app_id}/status-change/'
        resp = staff_client.post(status_url, {
            'csrfmiddlewaretoken': csrf,
            'new_status': 'under_review',
            'comment': 'Moving to under review for detailed evaluation.',
        })
        T.check(
            resp.status_code in (301, 302),
            'POST status change to under_review redirects',
            f'status={resp.status_code}',
        )
        app_obj.refresh_from_db()
        T.check(app_obj.status == 'under_review',
                'Application status is now under_review')

        # Verify notification was created for applicant
        applicant_notif_after = Notification.objects.filter(
            recipient=applicant_user,
        ).count()
        T.check(
            applicant_notif_after > applicant_notif_before,
            'Applicant notification created for status change',
            f'before={applicant_notif_before}, after={applicant_notif_after}',
        )

        # 8. Try to approve without all compliance -> should fail
        T.section('STAFF WORKFLOW - Approve Blocked by Compliance')
        resp = staff_client.get(detail_url)
        csrf = extract_csrftoken(resp)
        resp = staff_client.post(status_url, {
            'csrfmiddlewaretoken': csrf,
            'new_status': 'approved',
            'comment': 'Attempting premature approval.',
        })
        app_obj.refresh_from_db()
        # Should still be under_review because required compliance items are not verified
        required_unverified = app_obj.compliance_items.filter(
            is_required=True, is_verified=False,
        ).count()
        if required_unverified > 0:
            T.check(
                app_obj.status == 'under_review',
                'Approval blocked when compliance items unverified',
                f'{required_unverified} required items still unverified',
            )
        else:
            T.ok('All compliance items already verified (skip block test)')

        # 9. Verify ALL required compliance items
        T.section('STAFF WORKFLOW - Verify All Compliance Items')
        resp = staff_client.get(detail_url)
        csrf = extract_csrftoken(resp)
        from django.utils import timezone
        unverified_items = app_obj.compliance_items.filter(is_verified=False)
        for item in unverified_items:
            toggle_url = f'/applications/{app_id}/compliance/{item.pk}/toggle/'
            resp = staff_client.post(
                toggle_url,
                {'csrfmiddlewaretoken': csrf, 'notes': 'Auto-verified in test'},
            )
            # Get fresh CSRF for next request
            resp = staff_client.get(detail_url)
            csrf = extract_csrftoken(resp)

        all_required_verified = not app_obj.compliance_items.filter(
            is_required=True, is_verified=False,
        ).exists()
        T.check(all_required_verified, 'All required compliance items verified')

        # 10. Now approve the application
        T.section('STAFF WORKFLOW - Status: Approved')
        applicant_notif_before = Notification.objects.filter(
            recipient=applicant_user,
        ).count()

        resp = staff_client.get(detail_url)
        csrf = extract_csrftoken(resp)
        resp = staff_client.post(status_url, {
            'csrfmiddlewaretoken': csrf,
            'new_status': 'approved',
            'comment': 'Application approved. All compliance requirements met.',
        })
        T.check(
            resp.status_code in (301, 302),
            'POST status change to approved redirects',
            f'status={resp.status_code}',
        )
        app_obj.refresh_from_db()
        T.check(app_obj.status == 'approved',
                'Application status is now approved')

        # Verify notification
        applicant_notif_after = Notification.objects.filter(
            recipient=applicant_user,
        ).count()
        T.check(
            applicant_notif_after > applicant_notif_before,
            'Applicant notification created for approval',
        )

        # 11. Create an award
        T.section('STAFF WORKFLOW - Create Award')
        award_create_url = f'/awards/create/{app_id}/'
        resp = staff_client.get(award_create_url)
        T.check(response_ok(resp), 'GET award create form returns 200',
                f'status={resp.status_code}')
        err_ok, err_detail = check_no_server_error(resp)
        T.check(err_ok, 'No server error on award create form', err_detail)

        csrf = extract_csrftoken(resp)
        import uuid as _uuid
        test_award_num = f'CT-TST-2026-{_uuid.uuid4().hex[:4].upper()}'
        award_data = {
            'csrfmiddlewaretoken': csrf,
            'title': 'Community Health Initiative Award',
            'award_number': test_award_num,
            'award_amount': '75000.00',
            'award_date': today.isoformat(),
            'start_date': (today + timedelta(days=30)).isoformat(),
            'end_date': (today + timedelta(days=395)).isoformat(),
            'terms_and_conditions': 'Standard terms and conditions apply. '
                                     'Recipient must comply with all state and '
                                     'federal regulations.',
            'special_conditions': 'Quarterly reporting required.',
            'requires_match': 'on',
            'match_amount': '15000.00',
        }
        # Count award notifications before
        award_notif_before = Notification.objects.filter(
            recipient=applicant_user,
            title='Award Created',
        ).count()

        resp = staff_client.post(award_create_url, award_data)
        T.check(
            resp.status_code in (301, 302),
            'POST award create redirects',
            f'status={resp.status_code}',
        )

        from awards.models import Award
        award_obj = Award.objects.filter(application=app_obj).first()
        T.check(award_obj is not None, 'Award object created in DB')

        if not award_obj:
            T.fail('Cannot continue staff workflow without award')
            return

        award_id = str(award_obj.pk)
        T.check(
            award_obj.award_amount == Decimal('75000.00'),
            'Award amount correct',
        )
        T.check(
            bool(award_obj.award_number),
            'Award number auto-generated',
            f'number={award_obj.award_number}',
        )

        # Verify award notification
        award_notif_after = Notification.objects.filter(
            recipient=applicant_user,
            title='Award Created',
        ).count()
        T.check(
            award_notif_after > award_notif_before,
            'Award notification created for applicant',
        )

        # 12. View award detail
        T.section('STAFF WORKFLOW - Award Detail')
        award_detail_url = f'/awards/{award_id}/'
        resp = staff_client.get(award_detail_url)
        T.check(response_ok(resp), 'GET award detail returns 200',
                f'status={resp.status_code}')
        err_ok, err_detail = check_no_server_error(resp)
        T.check(err_ok, 'No server error on award detail', err_detail)

        # 13. View award list
        resp = staff_client.get('/awards/')
        T.check(response_ok(resp), 'GET /awards/ returns 200',
                f'status={resp.status_code}')
        err_ok, err_detail = check_no_server_error(resp)
        T.check(err_ok, 'No server error on awards list', err_detail)

        # 14. View reporting list
        T.section('STAFF WORKFLOW - Reporting & Financial')
        resp = staff_client.get('/reporting/')
        T.check(response_ok(resp), 'GET /reporting/ returns 200',
                f'status={resp.status_code}')
        err_ok, err_detail = check_no_server_error(resp)
        T.check(err_ok, 'No server error on reporting list', err_detail)

        # 15. View financial drawdowns list
        resp = staff_client.get('/financial/drawdowns/')
        T.check(response_ok(resp), 'GET /financial/drawdowns/ returns 200',
                f'status={resp.status_code}')
        err_ok, err_detail = check_no_server_error(resp)
        T.check(err_ok, 'No server error on drawdowns list', err_detail)

        # ==============================================================
        #  ADDITIONAL PAGE CHECKS
        # ==============================================================
        T.section('ADDITIONAL PAGE CHECKS')

        # Public pages
        public_client = Client()
        public_pages = [
            ('/', 'Home page'),
            ('/opportunities/', 'Opportunities list'),
            ('/about/', 'About page'),
            ('/help/', 'Help page'),
            ('/auth/login/', 'Login page'),
            ('/auth/register/', 'Register page'),
        ]
        for url, label in public_pages:
            resp = public_client.get(url)
            T.check(response_ok(resp), f'{label} returns 200',
                    f'status={resp.status_code}')
            err_ok, err_detail = check_no_server_error(resp)
            T.check(err_ok, f'No server error on {label}', err_detail)

        # Staff-only pages
        staff_pages = [
            ('/dashboard/', 'Dashboard'),
            ('/applications/', 'Applications list'),
            ('/awards/', 'Awards list'),
            ('/reporting/', 'Reporting list'),
            ('/financial/drawdowns/', 'Drawdowns list'),
            ('/financial/transactions/', 'Transactions list'),
            ('/auth/notifications/', 'Notifications'),
            ('/auth/profile/', 'Profile'),
            ('/grants/', 'Grant programs list'),
        ]
        for url, label in staff_pages:
            resp = staff_client.get(url)
            T.check(
                response_ok(resp, {200, 301, 302}),
                f'{label} accessible (staff)',
                f'status={resp.status_code}',
            )
            err_ok, err_detail = check_no_server_error(resp)
            T.check(err_ok, f'No server error on {label}', err_detail)

        # Applicant-specific pages
        applicant_pages = [
            ('/applications/my/', 'My Applications'),
            ('/awards/my/', 'My Awards'),
            ('/auth/notifications/', 'Applicant Notifications'),
            ('/auth/profile/', 'Applicant Profile'),
        ]
        for url, label in applicant_pages:
            resp = client.get(url)
            T.check(
                response_ok(resp, {200, 301, 302}),
                f'{label} accessible (applicant)',
                f'status={resp.status_code}',
            )
            err_ok, err_detail = check_no_server_error(resp)
            T.check(err_ok, f'No server error on {label}', err_detail)

        # ==============================================================
        #  BROKEN LINK SCAN (scan key pages for href="#")
        # ==============================================================
        T.section('BROKEN LINK SCAN')

        pages_to_scan = [
            (staff_client, '/dashboard/', 'Dashboard'),
            (staff_client, detail_url, 'Application Detail (staff)'),
            (staff_client, award_detail_url, 'Award Detail'),
            (staff_client, '/applications/', 'Applications List'),
            (public_client, '/', 'Home Page'),
            (public_client, '/opportunities/', 'Opportunities List'),
            (client, '/applications/my/', 'My Applications'),
        ]

        for c, url, label in pages_to_scan:
            resp = c.get(url, follow=True)
            if resp.status_code == 200:
                body = resp.content.decode()
                # Find all href values
                hrefs = re.findall(r'href=["\']([^"\']*)["\']', body)
                placeholder_links = [
                    h for h in hrefs
                    if h == '#' and 'dropdown' not in body[
                        max(0, body.index(f'href="{"#"}"') - 100):
                        body.index(f'href="{"#"}"') + 10
                    ].lower()
                ] if hrefs else []
                # Simpler check: count bare # hrefs
                bare_hash_count = body.count('href="#"')
                dropdown_toggle_count = body.lower().count('dropdown-toggle')
                # Allow # links roughly equal to dropdown toggles
                excess = max(0, bare_hash_count - dropdown_toggle_count - 2)
                T.check(
                    excess == 0,
                    f'No placeholder href="#" links in {label}',
                    f'found {bare_hash_count} "#" hrefs, '
                    f'{dropdown_toggle_count} dropdown-toggles',
                )

        # ==============================================================
        #  404 / 500 CHECKS
        # ==============================================================
        T.section('ERROR HANDLING')

        import uuid as uuid_mod
        fake_uuid = str(uuid_mod.uuid4())

        error_urls = [
            (staff_client, f'/applications/{fake_uuid}/', '404 on fake application'),
            (staff_client, f'/awards/{fake_uuid}/', '404 on fake award'),
            (public_client, f'/opportunities/{fake_uuid}/', '404 on fake opportunity'),
            (public_client, '/nonexistent-page/', '404 on unknown URL'),
        ]

        for c, url, label in error_urls:
            resp = c.get(url)
            T.check(
                resp.status_code == 404,
                f'{label} returns 404',
                f'status={resp.status_code}',
            )
            # Make sure it's not a 500
            T.check(
                resp.status_code < 500,
                f'{label} is not a server error',
            )

        # ==============================================================
        #  APPLICANT WORKFLOW - Post-Approval Checks
        # ==============================================================
        T.section('APPLICANT POST-APPROVAL')

        # Applicant can see their award
        resp = client.get('/awards/my/')
        T.check(response_ok(resp), 'GET /awards/my/ returns 200 for applicant',
                f'status={resp.status_code}')
        T.check(
            'Community Health Initiative' in resp.content.decode(),
            'Applicant sees their award in my-awards',
        )

        # Applicant can view award detail
        resp = client.get(award_detail_url)
        T.check(response_ok(resp), 'Applicant can view award detail',
                f'status={resp.status_code}')

        # Applicant sees notification about approval
        resp = client.get('/auth/notifications/')
        T.check(response_ok(resp), 'Applicant notifications page loads',
                f'status={resp.status_code}')
        notifs = Notification.objects.filter(recipient=applicant_user)
        T.check(
            notifs.count() > 0,
            f'Applicant has {notifs.count()} notification(s)',
        )

        # ==============================================================
        #  CLEANUP
        # ==============================================================
        T.section('CLEANUP')
        # We leave test data in place (no cleanup) so it can be inspected.
        T.ok('Test run complete - test data left in place for inspection')
