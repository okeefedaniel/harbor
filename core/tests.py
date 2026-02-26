"""Tests for the core app: User model, Organization, Agency, AuditLog,
Notification, and views (dashboard, login, logout, register)."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.models import Agency, AuditLog, Notification, Organization

User = get_user_model()


# ---------------------------------------------------------------------------
# Helper factories (reused across this module)
# ---------------------------------------------------------------------------
def _create_agency(**kwargs):
    defaults = {
        'name': 'Dept of Testing',
        'abbreviation': kwargs.pop('abbreviation', 'DOT'),
        'description': 'Test agency',
    }
    defaults.update(kwargs)
    return Agency.objects.create(**defaults)


def _create_organization(**kwargs):
    defaults = {
        'name': 'Test Org',
        'org_type': Organization.OrgType.NONPROFIT,
    }
    defaults.update(kwargs)
    return Organization.objects.create(**defaults)


def _create_user(username, role, agency=None, organization=None, **kwargs):
    defaults = {
        'username': username,
        'email': f'{username}@example.com',
        'role': role,
        'agency': agency,
        'organization': organization,
    }
    defaults.update(kwargs)
    return User.objects.create_user(password='testpass123!', **defaults)


# ===========================================================================
# Model tests
# ===========================================================================
class UserModelTests(TestCase):
    """Test the custom User model role properties."""

    def setUp(self):
        self.agency = _create_agency()

    def test_create_user_with_default_role(self):
        user = User.objects.create_user(username='newuser', password='testpass123!')
        self.assertEqual(user.role, User.Role.APPLICANT)

    def test_is_agency_staff_true_for_staff_roles(self):
        for role in [User.Role.SYSTEM_ADMIN, User.Role.AGENCY_ADMIN,
                     User.Role.PROGRAM_OFFICER, User.Role.FISCAL_OFFICER]:
            user = _create_user(f'user_{role}', role, agency=self.agency)
            self.assertTrue(user.is_agency_staff, f'{role} should be agency staff')

    def test_is_agency_staff_false_for_non_staff(self):
        for role in [User.Role.APPLICANT, User.Role.REVIEWER, User.Role.AUDITOR]:
            user = _create_user(f'user_{role}', role)
            self.assertFalse(user.is_agency_staff, f'{role} should NOT be agency staff')

    def test_can_manage_grants(self):
        manager = _create_user('mgr', User.Role.PROGRAM_OFFICER, agency=self.agency)
        self.assertTrue(manager.can_manage_grants)
        fiscal = _create_user('fiscal', User.Role.FISCAL_OFFICER, agency=self.agency)
        self.assertFalse(fiscal.can_manage_grants)

    def test_can_review(self):
        reviewer = _create_user('rev', User.Role.REVIEWER)
        self.assertTrue(reviewer.can_review)
        applicant = _create_user('app', User.Role.APPLICANT)
        self.assertFalse(applicant.can_review)

    def test_str_full_name(self):
        user = _create_user('jdoe', User.Role.APPLICANT, first_name='John', last_name='Doe')
        self.assertEqual(str(user), 'John Doe')

    def test_str_username_fallback(self):
        user = _create_user('jdoe2', User.Role.APPLICANT)
        self.assertEqual(str(user), 'jdoe2')


class OrganizationModelTests(TestCase):
    """Test Organization CRUD."""

    def test_create_organization(self):
        org = _create_organization(name='Acme Nonprofit')
        self.assertEqual(str(org), 'Acme Nonprofit')
        self.assertTrue(org.is_active)

    def test_update_organization(self):
        org = _create_organization()
        org.name = 'Updated Name'
        org.save()
        org.refresh_from_db()
        self.assertEqual(org.name, 'Updated Name')

    def test_organization_defaults(self):
        org = _create_organization()
        self.assertEqual(org.state, 'CT')
        self.assertFalse(org.sam_registered)


class AgencyModelTests(TestCase):
    """Test Agency model."""

    def test_create_agency(self):
        agency = _create_agency(name='Dept of Energy', abbreviation='DOE')
        self.assertEqual(str(agency), 'DOE - Dept of Energy')

    def test_agency_defaults(self):
        agency = _create_agency(abbreviation='TST')
        self.assertTrue(agency.can_be_grantor)
        self.assertFalse(agency.can_be_grantee)
        self.assertTrue(agency.is_active)


class AuditLogModelTests(TestCase):
    """Test AuditLog creation."""

    def test_create_audit_log(self):
        user = _create_user('auditor', User.Role.SYSTEM_ADMIN)
        log = AuditLog.objects.create(
            user=user,
            action=AuditLog.Action.CREATE,
            entity_type='TestEntity',
            entity_id='12345',
            description='Created a test entity.',
        )
        self.assertEqual(log.action, AuditLog.Action.CREATE)
        self.assertEqual(log.entity_type, 'TestEntity')

    def test_audit_log_without_user(self):
        log = AuditLog.objects.create(
            action=AuditLog.Action.LOGIN,
            entity_type='Session',
            entity_id='sess-1',
        )
        self.assertIsNone(log.user)
        self.assertIn('System', str(log))


class NotificationModelTests(TestCase):
    """Test Notification creation and marking as read."""

    def setUp(self):
        self.user = _create_user('nuser', User.Role.APPLICANT)

    def test_create_notification(self):
        n = Notification.objects.create(
            recipient=self.user, title='Test', message='Hello',
        )
        self.assertFalse(n.is_read)
        self.assertIsNone(n.read_at)
        self.assertEqual(n.priority, Notification.Priority.MEDIUM)

    def test_mark_notification_read(self):
        n = Notification.objects.create(
            recipient=self.user, title='Test', message='Read me',
        )
        n.is_read = True
        n.read_at = timezone.now()
        n.save()
        n.refresh_from_db()
        self.assertTrue(n.is_read)
        self.assertIsNotNone(n.read_at)


# ===========================================================================
# View tests
# ===========================================================================
class RegisterViewTests(TestCase):
    """Test the public registration view."""

    def test_register_page_loads(self):
        resp = self.client.get(reverse('core:register'))
        self.assertEqual(resp.status_code, 200)

    def test_register_creates_applicant(self):
        data = {
            'username': 'newapplicant',
            'email': 'new@example.com',
            'first_name': 'New',
            'last_name': 'Applicant',
            'password1': 'Str0ng!Pass99',
            'password2': 'Str0ng!Pass99',
            'accepted_terms': True,
        }
        resp = self.client.post(reverse('core:register'), data)
        self.assertEqual(resp.status_code, 302)
        user = User.objects.get(username='newapplicant')
        self.assertEqual(user.role, User.Role.APPLICANT)
        self.assertTrue(user.accepted_terms)


class LoginLogoutViewTests(TestCase):
    """Test login and logout."""

    def setUp(self):
        self.user = _create_user('loginuser', User.Role.APPLICANT)

    def test_login_page_loads(self):
        resp = self.client.get(reverse('core:login'))
        self.assertEqual(resp.status_code, 200)

    def test_login_success(self):
        resp = self.client.post(reverse('core:login'), {
            'username': 'loginuser', 'password': 'testpass123!',
        })
        self.assertEqual(resp.status_code, 302)

    def test_login_failure(self):
        resp = self.client.post(reverse('core:login'), {
            'username': 'loginuser', 'password': 'wrongpass',
        })
        self.assertEqual(resp.status_code, 200)

    def test_logout(self):
        self.client.login(username='loginuser', password='testpass123!')
        resp = self.client.post(reverse('core:logout'))
        self.assertIn(resp.status_code, [200, 302])


class DashboardViewTests(TestCase):
    """Test the main dashboard view for different roles."""

    def setUp(self):
        self.agency = _create_agency()
        self.org = _create_organization()
        self.admin = _create_user('admin', User.Role.SYSTEM_ADMIN, agency=self.agency)
        self.applicant = _create_user('applicant', User.Role.APPLICANT, organization=self.org)
        self.reviewer = _create_user('reviewer', User.Role.REVIEWER)

    def test_dashboard_requires_login(self):
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 302)

    def test_dashboard_agency_staff(self):
        self.client.login(username='admin', password='testpass123!')
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('pending_applications', resp.context)
        self.assertIn('total_funding', resp.context)

    def test_dashboard_applicant(self):
        self.client.login(username='applicant', password='testpass123!')
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('recent_applications', resp.context)
        self.assertIn('applications_count', resp.context)

    def test_dashboard_reviewer(self):
        self.client.login(username='reviewer', password='testpass123!')
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('pending_applications', resp.context)


class NotificationViewTests(TestCase):
    """Test notification list and mark-read views."""

    def setUp(self):
        self.user = _create_user('nuser', User.Role.APPLICANT)
        self.notification = Notification.objects.create(
            recipient=self.user, title='Test Notification', message='Content here',
        )
        self.client.login(username='nuser', password='testpass123!')

    def test_notification_list(self):
        resp = self.client.get(reverse('core:notifications'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Test Notification')

    def test_mark_notification_read(self):
        resp = self.client.post(
            reverse('core:notification-read', kwargs={'pk': self.notification.pk})
        )
        self.assertEqual(resp.status_code, 200)
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)

    def test_mark_notification_read_get_not_allowed(self):
        resp = self.client.get(
            reverse('core:notification-read', kwargs={'pk': self.notification.pk})
        )
        self.assertEqual(resp.status_code, 405)
