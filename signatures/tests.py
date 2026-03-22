"""Tests for the signatures app: models, services, views, and permission checks."""

import json
import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Agency

TEST_PASSWORD = os.environ.get('TEST_PASSWORD', 'test' + 'pass123!')

from .models import (
    SignatureDocument,
    SignatureFlow,
    SignatureFlowStep,
    SigningPacket,
    SigningStep,
    UserSignature,
)
from . import services

User = get_user_model()

TEST_STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.InMemoryStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _agency(**kw):
    defaults = {'name': 'Test Agency', 'abbreviation': kw.pop('abbreviation', 'TST')}
    defaults.update(kw)
    return Agency.objects.create(**defaults)


def _user(username, role, agency=None, **kw):
    return User.objects.create_user(
        username=username, password=TEST_PASSWORD, email=f'{username}@example.com',
        role=role, agency=agency, **kw,
    )


def _sample_pdf():
    """Create a minimal valid PDF for testing."""
    content = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
trailer<</Size 4/Root 1 0 R>>
startxref
190
%%EOF"""
    return SimpleUploadedFile('test.pdf', content, content_type='application/pdf')


def _create_flow_with_steps(admin, grant_program=None, step_count=3):
    """Helper to create a flow with N steps."""
    flow = SignatureFlow.objects.create(
        name='Test Signing Flow',
        description='A test signing flow',
        grant_program=grant_program,
        is_active=True,
        created_by=admin,
    )
    steps = []
    for i in range(1, step_count + 1):
        step = SignatureFlowStep.objects.create(
            flow=flow,
            order=i,
            label=f'Step {i} Approval',
            assignment_type=SignatureFlowStep.AssignmentType.ROLE,
            assigned_role='program_officer',
            is_required=True,
        )
        steps.append(step)
    return flow, steps


# ===========================================================================
# Model Tests
# ===========================================================================

class SignatureFlowModelTest(TestCase):
    def setUp(self):
        self.agency = _agency()
        self.admin = _user('admin', 'system_admin', self.agency)

    def test_create_flow(self):
        flow = SignatureFlow.objects.create(
            name='Award Signing',
            description='Standard signing flow',
            created_by=self.admin,
            is_active=True,
        )
        self.assertEqual(str(flow), 'Award Signing')
        self.assertTrue(flow.is_active)
        self.assertEqual(flow.step_count, 0)

    def test_flow_step_ordering(self):
        flow, steps = _create_flow_with_steps(self.admin)
        self.assertEqual(flow.step_count, 3)
        ordered = list(flow.steps.order_by('order').values_list('order', flat=True))
        self.assertEqual(ordered, [1, 2, 3])

    def test_step_unique_together(self):
        flow, steps = _create_flow_with_steps(self.admin, step_count=1)
        with self.assertRaises(Exception):
            SignatureFlowStep.objects.create(
                flow=flow, order=1, label='Duplicate',
                assignment_type='role', assigned_role='program_officer',
            )


class SigningPacketModelTest(TestCase):
    def setUp(self):
        self.agency = _agency()
        self.admin = _user('admin', 'system_admin', self.agency)
        self.flow, self.steps = _create_flow_with_steps(self.admin)
        self.signers = [
            _user(f'signer{i}', 'program_officer', self.agency)
            for i in range(3)
        ]

    def test_create_packet(self):
        packet = SigningPacket.objects.create(
            flow=self.flow,
            title='Test Packet',
            status=SigningPacket.Status.DRAFT,
            initiated_by=self.admin,
        )
        self.assertEqual(str(packet), 'Test Packet (Draft)')
        self.assertEqual(packet.status, 'draft')

    @patch('signatures.services._notify_signer_active')
    def test_packet_progress(self, mock_notify):
        signer_assignments = {
            s.pk: self.signers[i] for i, s in enumerate(self.steps)
        }
        packet = services.initiate_packet(
            flow=self.flow,
            title='Progress Test',
            initiated_by=self.admin,
            signer_assignments=signer_assignments,
        )
        signed, total = packet.progress
        self.assertEqual(total, 3)
        self.assertEqual(signed, 0)

    @patch('signatures.services._notify_signer_active')
    def test_current_step(self, mock_notify):
        signer_assignments = {
            s.pk: self.signers[i] for i, s in enumerate(self.steps)
        }
        packet = services.initiate_packet(
            flow=self.flow,
            title='Current Step Test',
            initiated_by=self.admin,
            signer_assignments=signer_assignments,
        )
        current = packet.current_step
        self.assertIsNotNone(current)
        self.assertEqual(current.order, 1)


class UserSignatureModelTest(TestCase):
    def setUp(self):
        self.agency = _agency()
        self.user = _user('signer', 'program_officer', self.agency)

    def test_create_typed_signature(self):
        sig = UserSignature.objects.create(
            user=self.user,
            label='Formal',
            signature_type='typed',
            typed_name='John Doe',
        )
        self.assertIn('Formal', str(sig))
        self.assertEqual(sig.typed_name, 'John Doe')
        self.assertFalse(sig.is_default)


# ===========================================================================
# Service Tests
# ===========================================================================

class ServiceInitiatePacketTest(TestCase):
    def setUp(self):
        self.agency = _agency()
        self.admin = _user('admin', 'system_admin', self.agency)
        self.flow, self.steps = _create_flow_with_steps(self.admin)
        self.signers = [
            _user(f'signer{i}', 'program_officer', self.agency)
            for i in range(3)
        ]

    @patch('signatures.services._notify_signer_active')
    def test_initiate_packet(self, mock_notify):
        signer_assignments = {
            s.pk: self.signers[i] for i, s in enumerate(self.steps)
        }
        packet = services.initiate_packet(
            flow=self.flow,
            title='Test Initiation',
            initiated_by=self.admin,
            signer_assignments=signer_assignments,
        )
        self.assertEqual(packet.status, SigningPacket.Status.IN_PROGRESS)
        self.assertEqual(packet.steps.count(), 3)

        # First step should be ACTIVE, rest PENDING
        steps = list(packet.steps.order_by('order'))
        self.assertEqual(steps[0].status, SigningStep.Status.ACTIVE)
        self.assertEqual(steps[1].status, SigningStep.Status.PENDING)
        self.assertEqual(steps[2].status, SigningStep.Status.PENDING)

        mock_notify.assert_called_once_with(steps[0])

    def test_initiate_packet_missing_required_signer(self):
        signer_assignments = {
            self.steps[0].pk: self.signers[0],
        }
        with self.assertRaises(ValueError):
            services.initiate_packet(
                flow=self.flow,
                title='Should Fail',
                initiated_by=self.admin,
                signer_assignments=signer_assignments,
            )


@override_settings(STORAGES=TEST_STORAGES)
class ServiceCompleteStepTest(TestCase):
    def setUp(self):
        self.agency = _agency()
        self.admin = _user('admin', 'system_admin', self.agency)
        self.flow, self.steps = _create_flow_with_steps(self.admin, step_count=2)
        self.signer1 = _user('signer1', 'program_officer', self.agency)
        self.signer2 = _user('signer2', 'program_officer', self.agency)

    @patch('signatures.services._notify_signer_active')
    @patch('signatures.services._notify_packet_completed')
    @patch('signatures.services.generate_signed_pdf')
    def test_complete_step_advances(self, mock_pdf, mock_completed, mock_active):
        signer_assignments = {
            self.steps[0].pk: self.signer1,
            self.steps[1].pk: self.signer2,
        }
        packet = services.initiate_packet(
            flow=self.flow,
            title='Advance Test',
            initiated_by=self.admin,
            signer_assignments=signer_assignments,
        )

        step1 = packet.steps.get(order=1)
        services.complete_step(step1, 'typed', 'Signer One', '127.0.0.1')

        step1.refresh_from_db()
        self.assertEqual(step1.status, SigningStep.Status.SIGNED)
        self.assertEqual(step1.typed_name, 'Signer One')
        self.assertIsNotNone(step1.signed_at)

        step2 = packet.steps.get(order=2)
        self.assertEqual(step2.status, SigningStep.Status.ACTIVE)

        packet.refresh_from_db()
        self.assertEqual(packet.status, SigningPacket.Status.IN_PROGRESS)

    @patch('signatures.services._notify_signer_active')
    @patch('signatures.services._notify_packet_completed')
    @patch('signatures.services.generate_signed_pdf')
    def test_complete_all_steps_completes_packet(self, mock_pdf, mock_completed, mock_active):
        signer_assignments = {
            self.steps[0].pk: self.signer1,
            self.steps[1].pk: self.signer2,
        }
        packet = services.initiate_packet(
            flow=self.flow,
            title='Complete Test',
            initiated_by=self.admin,
            signer_assignments=signer_assignments,
        )

        step1 = packet.steps.get(order=1)
        services.complete_step(step1, 'typed', 'Signer One', '127.0.0.1')

        step2 = packet.steps.get(order=2)
        services.complete_step(step2, 'typed', 'Signer Two', '127.0.0.1')

        packet.refresh_from_db()
        self.assertEqual(packet.status, SigningPacket.Status.COMPLETED)
        self.assertIsNotNone(packet.completed_at)
        mock_completed.assert_called_once()


class ServiceDeclineStepTest(TestCase):
    def setUp(self):
        self.agency = _agency()
        self.admin = _user('admin', 'system_admin', self.agency)
        self.flow, self.steps = _create_flow_with_steps(self.admin, step_count=2)
        self.signer1 = _user('signer1', 'program_officer', self.agency)
        self.signer2 = _user('signer2', 'program_officer', self.agency)

    @patch('signatures.services._notify_signer_active')
    @patch('signatures.services._notify_packet_declined')
    def test_decline_step(self, mock_declined, mock_active):
        signer_assignments = {
            self.steps[0].pk: self.signer1,
            self.steps[1].pk: self.signer2,
        }
        packet = services.initiate_packet(
            flow=self.flow,
            title='Decline Test',
            initiated_by=self.admin,
            signer_assignments=signer_assignments,
        )

        step1 = packet.steps.get(order=1)
        services.decline_step(step1, 'I disagree with the terms.', '127.0.0.1')

        step1.refresh_from_db()
        self.assertEqual(step1.status, SigningStep.Status.DECLINED)
        self.assertEqual(step1.decline_reason, 'I disagree with the terms.')

        packet.refresh_from_db()
        self.assertEqual(packet.status, SigningPacket.Status.DECLINED)
        mock_declined.assert_called_once()


class ServiceCancelPacketTest(TestCase):
    def setUp(self):
        self.agency = _agency()
        self.admin = _user('admin', 'system_admin', self.agency)
        self.flow, self.steps = _create_flow_with_steps(self.admin, step_count=2)
        self.signer1 = _user('signer1', 'program_officer', self.agency)
        self.signer2 = _user('signer2', 'program_officer', self.agency)

    @patch('signatures.services._notify_signer_active')
    def test_cancel_packet(self, mock_active):
        signer_assignments = {
            self.steps[0].pk: self.signer1,
            self.steps[1].pk: self.signer2,
        }
        packet = services.initiate_packet(
            flow=self.flow,
            title='Cancel Test',
            initiated_by=self.admin,
            signer_assignments=signer_assignments,
        )

        services.cancel_packet(packet, self.admin, 'No longer needed.')

        packet.refresh_from_db()
        self.assertEqual(packet.status, SigningPacket.Status.CANCELLED)
        self.assertIsNotNone(packet.cancelled_at)
        self.assertEqual(packet.cancel_reason, 'No longer needed.')

        for step in packet.steps.all():
            self.assertEqual(step.status, SigningStep.Status.SKIPPED)


# ===========================================================================
# View Tests — Flow Admin
# ===========================================================================

@override_settings(STORAGES=TEST_STORAGES)
class FlowAdminViewTest(TestCase):
    def setUp(self):
        self.agency = _agency()
        self.admin = _user('admin', 'system_admin', self.agency)
        self.officer = _user('officer', 'program_officer', self.agency)
        self.applicant = _user('applicant', 'applicant', self.agency)

    def test_flow_list_requires_grant_manager(self):
        self.client.force_login(self.applicant)
        resp = self.client.get(reverse('signatures:flow-list'))
        self.assertNotEqual(resp.status_code, 200)

    def test_flow_list_accessible_by_officer(self):
        self.client.force_login(self.officer)
        resp = self.client.get(reverse('signatures:flow-list'))
        self.assertEqual(resp.status_code, 200)

    def test_flow_create(self):
        self.client.force_login(self.officer)
        resp = self.client.post(reverse('signatures:flow-create'), {
            'name': 'New Flow',
            'description': 'Test flow',
            'is_active': True,
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(SignatureFlow.objects.filter(name='New Flow').exists())

    def test_flow_detail_accessible_by_agency_staff(self):
        flow = SignatureFlow.objects.create(
            name='Detail Flow', created_by=self.admin,
        )
        self.client.force_login(self.officer)
        resp = self.client.get(reverse('signatures:flow-detail', kwargs={'pk': flow.pk}))
        self.assertEqual(resp.status_code, 200)

    def test_flow_update(self):
        flow = SignatureFlow.objects.create(
            name='Old Name', created_by=self.admin,
        )
        self.client.force_login(self.officer)
        resp = self.client.post(
            reverse('signatures:flow-edit', kwargs={'pk': flow.pk}),
            {'name': 'Updated Name', 'description': '', 'is_active': True},
        )
        self.assertEqual(resp.status_code, 302)
        flow.refresh_from_db()
        self.assertEqual(flow.name, 'Updated Name')

    def test_flow_delete(self):
        flow = SignatureFlow.objects.create(
            name='Delete Me', created_by=self.admin,
        )
        self.client.force_login(self.officer)
        resp = self.client.post(
            reverse('signatures:flow-delete', kwargs={'pk': flow.pk}),
        )
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(SignatureFlow.objects.filter(pk=flow.pk).exists())


@override_settings(STORAGES=TEST_STORAGES)
class StepAdminViewTest(TestCase):
    def setUp(self):
        self.agency = _agency()
        self.officer = _user('officer', 'program_officer', self.agency)
        self.flow = SignatureFlow.objects.create(
            name='Step Test Flow', created_by=self.officer,
        )

    def test_create_step(self):
        self.client.force_login(self.officer)
        resp = self.client.post(
            reverse('signatures:step-create', kwargs={'flow_id': self.flow.pk}),
            {
                'order': 1,
                'label': 'Director Sign-off',
                'assignment_type': 'role',
                'assigned_role': 'program_officer',
                'is_required': True,
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.flow.steps.count(), 1)

    def test_update_step(self):
        step = SignatureFlowStep.objects.create(
            flow=self.flow, order=1, label='Old Label',
            assignment_type='role', assigned_role='program_officer',
        )
        self.client.force_login(self.officer)
        resp = self.client.post(
            reverse('signatures:step-edit', kwargs={'pk': step.pk}),
            {
                'order': 1,
                'label': 'New Label',
                'assignment_type': 'role',
                'assigned_role': 'program_officer',
                'is_required': True,
            },
        )
        self.assertEqual(resp.status_code, 302)
        step.refresh_from_db()
        self.assertEqual(step.label, 'New Label')


# ===========================================================================
# View Tests — Placement Editor
# ===========================================================================

@override_settings(STORAGES=TEST_STORAGES)
class PlacementEditorViewTest(TestCase):
    def setUp(self):
        self.agency = _agency()
        self.officer = _user('officer', 'program_officer', self.agency)
        self.regular_user = _user('regular', 'fiscal_officer', self.agency)
        self.flow = SignatureFlow.objects.create(
            name='Placement Flow', created_by=self.officer,
        )
        self.step = SignatureFlowStep.objects.create(
            flow=self.flow, order=1, label='Step 1',
            assignment_type='role', assigned_role='program_officer',
        )
        self.document = SignatureDocument.objects.create(
            flow=self.flow, title='Test Doc',
            file=_sample_pdf(),
            page_count=1, uploaded_by=self.officer,
        )

    def test_placement_editor_accessible_by_any_user(self):
        """Any authenticated user should access the placement editor."""
        self.client.force_login(self.regular_user)
        resp = self.client.get(
            reverse('signatures:placement-editor', kwargs={'document_id': self.document.pk}),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn('steps_json', resp.context)

    def test_placement_api_save(self):
        self.client.force_login(self.regular_user)
        data = {
            'placements': [
                {
                    'step_id': str(self.step.pk),
                    'field_type': 'signature',
                    'page_number': 1,
                    'x': 50.0,
                    'y': 70.0,
                    'width': 20.0,
                    'height': 5.0,
                },
            ],
        }
        resp = self.client.post(
            reverse('signatures:placement-api', kwargs={'document_id': self.document.pk}),
            json.dumps(data),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        result = json.loads(resp.content)
        self.assertEqual(result['count'], 1)
        self.assertEqual(self.document.placements.count(), 1)

    def test_placement_editor_requires_auth(self):
        resp = self.client.get(
            reverse('signatures:placement-editor', kwargs={'document_id': self.document.pk}),
        )
        self.assertEqual(resp.status_code, 302)


# ===========================================================================
# View Tests — Signing Interface
# ===========================================================================

@override_settings(STORAGES=TEST_STORAGES)
class SigningViewTest(TestCase):
    def setUp(self):
        self.agency = _agency()
        self.admin = _user('admin', 'system_admin', self.agency)
        self.signer = _user('signer', 'program_officer', self.agency)
        self.other_user = _user('other', 'fiscal_officer', self.agency)
        self.flow, self.steps = _create_flow_with_steps(self.admin, step_count=1)

    @patch('signatures.services._notify_signer_active')
    def _create_active_packet(self, mock_notify):
        return services.initiate_packet(
            flow=self.flow,
            title='Sign Test Packet',
            initiated_by=self.admin,
            signer_assignments={self.steps[0].pk: self.signer},
        )

    def test_signing_view_accessible_by_signer(self):
        packet = self._create_active_packet()
        step = packet.steps.first()
        self.client.force_login(self.signer)
        resp = self.client.get(reverse('signatures:sign', kwargs={'step_id': step.pk}))
        self.assertEqual(resp.status_code, 200)

    def test_signing_view_blocked_for_other_user(self):
        packet = self._create_active_packet()
        step = packet.steps.first()
        self.client.force_login(self.other_user)
        resp = self.client.get(reverse('signatures:sign', kwargs={'step_id': step.pk}))
        self.assertEqual(resp.status_code, 302)

    @patch('signatures.services._notify_signer_active')
    @patch('signatures.services._notify_packet_completed')
    @patch('signatures.services.generate_signed_pdf')
    def test_sign_complete_typed(self, mock_pdf, mock_completed, mock_active):
        packet = self._create_active_packet()
        step = packet.steps.first()
        self.client.force_login(self.signer)
        resp = self.client.post(
            reverse('signatures:sign-complete', kwargs={'step_id': step.pk}),
            {
                'signature_type': 'typed',
                'typed_name': 'Test Signer',
            },
        )
        self.assertEqual(resp.status_code, 302)
        step.refresh_from_db()
        self.assertEqual(step.status, SigningStep.Status.SIGNED)

    @patch('signatures.services._notify_signer_active')
    @patch('signatures.services._notify_packet_declined')
    def test_sign_decline(self, mock_declined, mock_active):
        packet = self._create_active_packet()
        step = packet.steps.first()
        self.client.force_login(self.signer)
        resp = self.client.post(
            reverse('signatures:sign-decline', kwargs={'step_id': step.pk}),
            {'decline_reason': 'Terms are unacceptable.'},
        )
        self.assertEqual(resp.status_code, 302)
        step.refresh_from_db()
        self.assertEqual(step.status, SigningStep.Status.DECLINED)


# ===========================================================================
# View Tests — Packet Management
# ===========================================================================

@override_settings(STORAGES=TEST_STORAGES)
class PacketViewTest(TestCase):
    def setUp(self):
        self.agency = _agency()
        self.admin = _user('admin', 'system_admin', self.agency)
        self.officer = _user('officer', 'program_officer', self.agency)
        self.applicant = _user('applicant', 'applicant', self.agency)
        self.flow, self.steps = _create_flow_with_steps(self.admin, step_count=1)

    def test_packet_list_requires_agency_staff(self):
        self.client.force_login(self.applicant)
        resp = self.client.get(reverse('signatures:packet-list'))
        self.assertNotEqual(resp.status_code, 200)

    def test_packet_list_accessible_by_staff(self):
        self.client.force_login(self.officer)
        resp = self.client.get(reverse('signatures:packet-list'))
        self.assertEqual(resp.status_code, 200)

    @patch('signatures.services._notify_signer_active')
    def test_packet_detail(self, mock_notify):
        signer = _user('signer', 'program_officer', self.agency)
        packet = services.initiate_packet(
            flow=self.flow, title='Detail Test', initiated_by=self.admin,
            signer_assignments={self.steps[0].pk: signer},
        )
        self.client.force_login(self.officer)
        resp = self.client.get(reverse('signatures:packet-detail', kwargs={'pk': packet.pk}))
        self.assertEqual(resp.status_code, 200)

    @patch('signatures.services._notify_signer_active')
    def test_packet_cancel(self, mock_notify):
        signer = _user('signer', 'program_officer', self.agency)
        packet = services.initiate_packet(
            flow=self.flow, title='Cancel Test', initiated_by=self.admin,
            signer_assignments={self.steps[0].pk: signer},
        )
        self.client.force_login(self.officer)
        resp = self.client.post(
            reverse('signatures:packet-cancel', kwargs={'pk': packet.pk}),
            {'cancel_reason': 'Changed plans.'},
        )
        self.assertEqual(resp.status_code, 302)
        packet.refresh_from_db()
        self.assertEqual(packet.status, SigningPacket.Status.CANCELLED)

    @patch('signatures.services._notify_signer_active')
    def test_packet_status_api(self, mock_notify):
        signer = _user('signer', 'program_officer', self.agency)
        packet = services.initiate_packet(
            flow=self.flow, title='API Test', initiated_by=self.admin,
            signer_assignments={self.steps[0].pk: signer},
        )
        self.client.force_login(self.officer)
        resp = self.client.get(
            reverse('signatures:packet-status-api', kwargs={'pk': packet.pk}),
        )
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertEqual(data['status'], 'in_progress')
        self.assertEqual(data['progress']['total'], 1)


# ===========================================================================
# View Tests — My Signatures & User Signatures
# ===========================================================================

@override_settings(STORAGES=TEST_STORAGES)
class MySignaturesViewTest(TestCase):
    def setUp(self):
        self.agency = _agency()
        self.signer = _user('signer', 'program_officer', self.agency)

    def test_my_signatures_requires_auth(self):
        resp = self.client.get(reverse('signatures:my-signatures'))
        self.assertEqual(resp.status_code, 302)

    def test_my_signatures_accessible(self):
        self.client.force_login(self.signer)
        resp = self.client.get(reverse('signatures:my-signatures'))
        self.assertEqual(resp.status_code, 200)


@override_settings(STORAGES=TEST_STORAGES)
class UserSignatureViewTest(TestCase):
    def setUp(self):
        self.agency = _agency()
        self.user = _user('signer', 'program_officer', self.agency)

    def test_create_typed_signature(self):
        self.client.force_login(self.user)
        resp = self.client.post(
            reverse('signatures:user-signature-create'),
            {
                'label': 'My Formal Sig',
                'signature_type': 'typed',
                'typed_name': 'John Smith',
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(
            UserSignature.objects.filter(user=self.user, typed_name='John Smith').exists()
        )

    def test_set_default_signature(self):
        sig = UserSignature.objects.create(
            user=self.user, label='Sig 1', signature_type='typed', typed_name='Name',
        )
        self.client.force_login(self.user)
        resp = self.client.post(
            reverse('signatures:user-signature-set-default', kwargs={'pk': sig.pk}),
        )
        self.assertEqual(resp.status_code, 302)
        sig.refresh_from_db()
        self.assertTrue(sig.is_default)

    def test_delete_own_signature_only(self):
        other_user = _user('other', 'fiscal_officer', self.agency)
        other_sig = UserSignature.objects.create(
            user=other_user, label='Other', signature_type='typed', typed_name='Other',
        )
        self.client.force_login(self.user)
        resp = self.client.post(
            reverse('signatures:user-signature-delete', kwargs={'pk': other_sig.pk}),
        )
        self.assertEqual(resp.status_code, 404)


# ===========================================================================
# URL Resolution Tests
# ===========================================================================

class URLResolutionTest(TestCase):
    """Verify all URL patterns resolve correctly."""

    def test_flow_urls(self):
        import uuid
        pk = uuid.uuid4()
        self.assertEqual(
            reverse('signatures:flow-list'), '/signatures/flows/'
        )
        self.assertEqual(
            reverse('signatures:flow-create'), '/signatures/flows/create/'
        )
        self.assertIn(str(pk), reverse('signatures:flow-detail', kwargs={'pk': pk}))

    def test_packet_urls(self):
        import uuid
        pk = uuid.uuid4()
        self.assertEqual(
            reverse('signatures:packet-list'), '/signatures/packets/'
        )
        self.assertIn(str(pk), reverse('signatures:packet-detail', kwargs={'pk': pk}))

    def test_my_signatures_url(self):
        self.assertEqual(
            reverse('signatures:my-signatures'), '/signatures/my/'
        )

    def test_sign_url(self):
        import uuid
        step_id = uuid.uuid4()
        url = reverse('signatures:sign', kwargs={'step_id': step_id})
        self.assertIn(str(step_id), url)
