"""
Signature workflow orchestration services.

Business logic is separated from views for testability and reusability.
"""
import base64
import io
import logging

from django.core.files.base import ContentFile
from django.utils import timezone
from django.utils.translation import gettext as _

from .compat import (
    build_absolute_url,
    create_notification,
    get_audit_action,
    log_audit,
    send_notification_email,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Packet lifecycle
# ---------------------------------------------------------------------------

def initiate_packet(flow, title, initiated_by, signer_assignments,
                    content_type=None, object_id=''):
    """Create a SigningPacket and its SigningStep records.

    Args:
        flow: SignatureFlow instance
        title: str — descriptive title
        initiated_by: User who is starting the signing
        signer_assignments: dict mapping flow_step.pk (UUID) -> User instance
        content_type: ContentType (optional, for linking to Award etc.)
        object_id: str (optional)

    Returns:
        SigningPacket instance
    """
    from .models import SigningPacket, SigningStep

    packet = SigningPacket.objects.create(
        flow=flow,
        title=title,
        status=SigningPacket.Status.IN_PROGRESS,
        initiated_by=initiated_by,
        content_type=content_type,
        object_id=str(object_id) if object_id else '',
    )

    steps = list(flow.steps.order_by('order'))
    for flow_step in steps:
        signer = signer_assignments.get(flow_step.pk)
        if not signer and not flow_step.is_required:
            continue
        if not signer:
            raise ValueError(
                f'No signer assigned for required step "{flow_step.label}".'
            )
        SigningStep.objects.create(
            packet=packet,
            flow_step=flow_step,
            order=flow_step.order,
            signer=signer,
            status=SigningStep.Status.PENDING,
        )

    # Activate the first step
    first_step = packet.steps.order_by('order').first()
    if first_step:
        first_step.status = first_step.Status.ACTIVE
        first_step.save(update_fields=['status', 'updated_at'])
        _notify_signer_active(first_step)

    log_audit(
        user=initiated_by,
        action=get_audit_action().CREATE,
        entity_type='SigningPacket',
        entity_id=str(packet.pk),
        description=f'Initiated signing packet "{title}" with {len(steps)} steps.',
    )

    return packet


def complete_step(signing_step, signature_type, signature_data, ip_address=None):
    """Mark a step as signed and advance the packet.

    Args:
        signing_step: SigningStep instance
        signature_type: 'typed', 'uploaded', or 'drawn'
        signature_data: typed_name (str), uploaded file, or base64 PNG data
        ip_address: client IP
    """
    from .models import SigningStep

    signing_step.status = SigningStep.Status.SIGNED
    signing_step.signature_type = signature_type
    signing_step.signed_at = timezone.now()
    signing_step.signed_ip = ip_address

    if signature_type == 'typed':
        signing_step.typed_name = signature_data
    elif signature_type == 'uploaded':
        signing_step.signature_image = signature_data
    elif signature_type == 'drawn':
        # signature_data is base64 PNG string (data:image/png;base64,...)
        img_data = signature_data
        if ',' in img_data:
            img_data = img_data.split(',', 1)[1]
        decoded = base64.b64decode(img_data)
        filename = f'sig_{signing_step.pk}.png'
        signing_step.signature_image.save(filename, ContentFile(decoded), save=False)

    signing_step.save()

    log_audit(
        user=signing_step.signer,
        action=get_audit_action().APPROVE,
        entity_type='SigningStep',
        entity_id=str(signing_step.pk),
        description=(
            f'{signing_step.signer.get_full_name()} signed step {signing_step.order} '
            f'("{signing_step.flow_step.label}") via {signature_type}.'
        ),
        ip_address=ip_address,
    )

    advance_packet(signing_step.packet)


def advance_packet(packet):
    """After a step is signed, activate the next step or complete the packet."""
    from .models import SigningStep

    # Find next pending step
    next_step = (
        packet.steps
        .filter(status=SigningStep.Status.PENDING)
        .order_by('order')
        .first()
    )

    if next_step:
        next_step.status = SigningStep.Status.ACTIVE
        next_step.save(update_fields=['status', 'updated_at'])
        _notify_signer_active(next_step)
    else:
        # All steps complete — finalize packet
        _complete_packet(packet)


def _complete_packet(packet):
    """Finalize a completed packet."""
    from .models import SigningPacket

    packet.status = SigningPacket.Status.COMPLETED
    packet.completed_at = timezone.now()
    packet.save(update_fields=['status', 'completed_at', 'updated_at'])

    # Generate the signed PDF
    try:
        generate_signed_pdf(packet)
    except Exception:
        logger.exception('Failed to generate signed PDF for packet %s', packet.pk)

    _notify_packet_completed(packet)

    log_audit(
        user=None,
        action=get_audit_action().STATUS_CHANGE,
        entity_type='SigningPacket',
        entity_id=str(packet.pk),
        description=f'Signing packet "{packet.title}" completed — all signatures collected.',
    )


def decline_step(signing_step, reason, ip_address=None):
    """Mark a step as declined and the packet as declined."""
    from .models import SigningPacket, SigningStep

    signing_step.status = SigningStep.Status.DECLINED
    signing_step.declined_at = timezone.now()
    signing_step.decline_reason = reason
    signing_step.save()

    packet = signing_step.packet
    packet.status = SigningPacket.Status.DECLINED
    packet.save(update_fields=['status', 'updated_at'])

    _notify_packet_declined(packet, signing_step)

    log_audit(
        user=signing_step.signer,
        action=get_audit_action().REJECT,
        entity_type='SigningStep',
        entity_id=str(signing_step.pk),
        description=(
            f'{signing_step.signer.get_full_name()} declined step {signing_step.order} '
            f'("{signing_step.flow_step.label}"): {reason}'
        ),
        ip_address=ip_address,
    )


def cancel_packet(packet, cancelled_by, reason=''):
    """Cancel all pending/active steps and mark the packet as cancelled."""
    from .models import SigningPacket, SigningStep

    packet.steps.filter(
        status__in=[SigningStep.Status.PENDING, SigningStep.Status.ACTIVE],
    ).update(status=SigningStep.Status.SKIPPED)

    packet.status = SigningPacket.Status.CANCELLED
    packet.cancelled_at = timezone.now()
    packet.cancelled_by = cancelled_by
    packet.cancel_reason = reason
    packet.save(update_fields=[
        'status', 'cancelled_at', 'cancelled_by', 'cancel_reason', 'updated_at',
    ])

    log_audit(
        user=cancelled_by,
        action=get_audit_action().STATUS_CHANGE,
        entity_type='SigningPacket',
        entity_id=str(packet.pk),
        description=f'Signing packet "{packet.title}" cancelled by {cancelled_by.get_full_name()}.',
    )


# ---------------------------------------------------------------------------
# PDF generation
# ---------------------------------------------------------------------------

def generate_signed_pdf(packet):
    """Overlay all signature images onto the template PDF.

    Uses pypdf + Pillow to composite signature images at the placement
    coordinates defined for each document in the flow.
    """
    from pypdf import PdfReader, PdfWriter
    from PIL import Image
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas as rl_canvas

    from .models import SignaturePlacement, SigningStep

    writer = PdfWriter()

    for doc in packet.flow.documents.all():
        if not doc.file:
            continue

        reader = PdfReader(doc.file.open('rb'))

        for page_idx, page in enumerate(reader.pages):
            page_num = page_idx + 1
            page_width = float(page.mediabox.width)
            page_height = float(page.mediabox.height)

            # Find placements for this page
            placements = SignaturePlacement.objects.filter(
                document=doc,
                page_number=page_num,
            ).select_related('step')

            if placements.exists():
                # Create an overlay PDF with signatures
                overlay_buffer = io.BytesIO()
                c = rl_canvas.Canvas(overlay_buffer, pagesize=(page_width, page_height))

                for placement in placements:
                    # Find the corresponding signing step
                    signing_step = (
                        packet.steps
                        .filter(
                            flow_step=placement.step,
                            status=SigningStep.Status.SIGNED,
                        )
                        .first()
                    )
                    if not signing_step:
                        continue

                    # Calculate absolute coordinates from percentages
                    abs_x = (placement.x / 100.0) * page_width
                    abs_y = page_height - ((placement.y / 100.0) * page_height)  # PDF origin is bottom-left
                    abs_w = (placement.width / 100.0) * page_width
                    abs_h = (placement.height / 100.0) * page_height
                    abs_y -= abs_h  # Adjust for height

                    if placement.field_type == SignaturePlacement.FieldType.DATE:
                        # Render date text
                        date_str = signing_step.signed_at.strftime('%m/%d/%Y') if signing_step.signed_at else ''
                        c.setFont('Helvetica', 10)
                        c.drawString(abs_x + 2, abs_y + abs_h * 0.3, date_str)
                    elif placement.field_type == SignaturePlacement.FieldType.NAME:
                        # Render printed name
                        name = signing_step.signer.get_full_name()
                        c.setFont('Helvetica', 10)
                        c.drawString(abs_x + 2, abs_y + abs_h * 0.3, name)
                    else:
                        # Signature or initials — render image or typed name
                        if signing_step.signature_type == 'typed':
                            c.setFont('Helvetica-Oblique', 14)
                            c.drawString(abs_x + 2, abs_y + abs_h * 0.3, signing_step.typed_name)
                        elif signing_step.signature_image:
                            try:
                                img = Image.open(signing_step.signature_image.open('rb'))
                                img_buffer = io.BytesIO()
                                img.save(img_buffer, format='PNG')
                                img_buffer.seek(0)
                                from reportlab.lib.utils import ImageReader
                                c.drawImage(
                                    ImageReader(img_buffer),
                                    abs_x, abs_y, abs_w, abs_h,
                                    preserveAspectRatio=True,
                                    mask='auto',
                                )
                            except Exception:
                                logger.exception(
                                    'Failed to overlay signature image for step %s',
                                    signing_step.pk,
                                )

                c.save()
                overlay_buffer.seek(0)
                overlay_reader = PdfReader(overlay_buffer)
                page.merge_page(overlay_reader.pages[0])

            writer.add_page(page)

    # Save the combined document
    output = io.BytesIO()
    writer.write(output)
    output.seek(0)
    filename = f'signed_{packet.pk}.pdf'
    packet.signed_document.save(filename, ContentFile(output.read()), save=True)


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

def _notify_signer_active(signing_step):
    """Notify a signer that it's their turn to sign."""
    from django.urls import reverse

    sign_url = reverse('signatures:sign', kwargs={'step_id': signing_step.pk})
    absolute_url = build_absolute_url(sign_url)

    create_notification(
        recipient=signing_step.signer,
        title=_('Signature Required'),
        message=_(
            'You have been asked to sign "%(packet)s" (Step %(order)s: %(label)s). '
            'Please review and sign the document.'
        ) % {
            'packet': signing_step.packet.title,
            'order': signing_step.order,
            'label': signing_step.flow_step.label,
        },
        link=sign_url,
        priority='high',
    )

    send_notification_email(
        recipient_email=signing_step.signer.email,
        subject=_('Action Required: Signature Needed — %(packet)s') % {
            'packet': signing_step.packet.title,
        },
        template_name='emails/signer_active.html',
        context={
            'signer': signing_step.signer,
            'packet': signing_step.packet,
            'step': signing_step,
            'sign_url': absolute_url,
        },
    )


def _notify_packet_completed(packet):
    """Notify the initiator and all signers that signing is complete."""
    from django.urls import reverse

    detail_url = reverse('signatures:packet-detail', kwargs={'pk': packet.pk})
    absolute_url = build_absolute_url(detail_url)

    notified = set()

    # Notify initiator
    if packet.initiated_by:
        create_notification(
            recipient=packet.initiated_by,
            title=_('Signing Complete'),
            message=_('All signatures have been collected for "%(packet)s".') % {
                'packet': packet.title,
            },
            link=detail_url,
            priority='high',
        )
        send_notification_email(
            recipient_email=packet.initiated_by.email,
            subject=_('Signing Complete — %(packet)s') % {'packet': packet.title},
            template_name='emails/packet_completed.html',
            context={
                'recipient': packet.initiated_by,
                'packet': packet,
                'detail_url': absolute_url,
            },
        )
        notified.add(packet.initiated_by.pk)

    # Notify each signer
    for step in packet.steps.select_related('signer'):
        if step.signer.pk not in notified:
            create_notification(
                recipient=step.signer,
                title=_('Signing Complete'),
                message=_('All signatures have been collected for "%(packet)s".') % {
                    'packet': packet.title,
                },
                link=detail_url,
                priority='medium',
            )
            notified.add(step.signer.pk)


def _notify_packet_declined(packet, declined_step):
    """Notify the initiator that a signer declined."""
    from django.urls import reverse

    if not packet.initiated_by:
        return

    detail_url = reverse('signatures:packet-detail', kwargs={'pk': packet.pk})
    absolute_url = build_absolute_url(detail_url)

    create_notification(
        recipient=packet.initiated_by,
        title=_('Signature Declined'),
        message=_(
            '%(signer)s declined to sign "%(packet)s" (Step %(order)s: %(label)s). '
            'Reason: %(reason)s'
        ) % {
            'signer': declined_step.signer.get_full_name(),
            'packet': packet.title,
            'order': declined_step.order,
            'label': declined_step.flow_step.label,
            'reason': declined_step.decline_reason,
        },
        link=detail_url,
        priority='high',
    )

    send_notification_email(
        recipient_email=packet.initiated_by.email,
        subject=_('Signature Declined — %(packet)s') % {'packet': packet.title},
        template_name='emails/packet_declined.html',
        context={
            'recipient': packet.initiated_by,
            'packet': packet,
            'declined_step': declined_step,
            'detail_url': absolute_url,
        },
    )


def send_reminder(signing_step):
    """Send a reminder email to the active signer."""
    from django.urls import reverse

    sign_url = reverse('signatures:sign', kwargs={'step_id': signing_step.pk})
    absolute_url = build_absolute_url(sign_url)

    send_notification_email(
        recipient_email=signing_step.signer.email,
        subject=_('Reminder: Signature Needed — %(packet)s') % {
            'packet': signing_step.packet.title,
        },
        template_name='emails/signer_reminder.html',
        context={
            'signer': signing_step.signer,
            'packet': signing_step.packet,
            'step': signing_step,
            'sign_url': absolute_url,
        },
    )

    signing_step.reminded_at = timezone.now()
    signing_step.save(update_fields=['reminded_at', 'updated_at'])
