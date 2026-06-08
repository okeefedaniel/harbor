"""Approach D for harbor's secondary ``signatures.AuditLog``.

Harbor's ``signatures`` app ships an ``AuditLog`` model alongside
``harbor_core.AuditLog`` so the same codebase can be deployed as
Manifest standalone (where ``KEEL_AUDIT_LOG_MODEL = 'signatures.AuditLog'``).
In Harbor mode the canonical AuditLog is ``harbor_core.AuditLog`` and this
table sits idle — but the model declaration still exists, so makemigrations
notices the AbstractAuditLog field changes here too.

Side-by-side companion to ``harbor_core.0008_auditlog_user_required`` so
``makemigrations --check`` stays green. Same atomic=False / unhitch
pattern; the unhitch is a no-op in Harbor mode because no Activity rows
reference this signatures.AuditLog.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def _drop_null_user_auditlogs(apps, schema_editor):
    """Idempotent — early-returns if no null-user rows exist (Harbor mode)."""
    AuditLog = apps.get_model('signatures', 'AuditLog')
    null_user_ids = list(
        AuditLog.objects.filter(user__isnull=True).values_list('id', flat=True)
    )
    if not null_user_ids:
        return
    AuditLog.objects.filter(user__isnull=True).delete()


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('signatures', '0004_auditlog_deep_link_snapshot_auditlog_metadata_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(
            _drop_null_user_auditlogs,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name='auditlog',
            name='action',
            field=models.CharField(
                choices=[
                    ('create', 'Create'), ('update', 'Update'),
                    ('delete', 'Delete'), ('status_change', 'Status Change'),
                    ('submit', 'Submit'), ('approve', 'Approve'),
                    ('reject', 'Reject'), ('login', 'Login'),
                    ('export', 'Export'), ('view', 'View'),
                    ('archive', 'Archive'), ('unarchive', 'Unarchive'),
                    ('role_grant_denied', 'Role Grant Denied'),
                    ('username_change', 'Username Change'),
                    ('email_change', 'Email Change'),
                    ('avatar_change', 'Avatar Change'),
                ],
                max_length=25,
            ),
        ),
        migrations.AlterField(
            model_name='auditlog',
            name='user',
            field=models.ForeignKey(
                help_text=(
                    'The user who performed the action. AuditLog is '
                    'user-only under Approach D — system events go '
                    'through Activity.'
                ),
                on_delete=django.db.models.deletion.PROTECT,
                related_name='%(app_label)s_audit_logs',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddConstraint(
            model_name='auditlog',
            constraint=models.CheckConstraint(
                condition=models.Q(('user__isnull', False)),
                name='signatures_auditlog_user_required',
            ),
        ),
    ]
