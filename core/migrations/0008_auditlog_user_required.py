"""Approach D for harbor: make ``harbor_core.AuditLog.user`` NOT NULL
+ add the ``harbor_core_auditlog_user_required`` CheckConstraint.

Wave 5 follow-up. Canary's ``audit_constraint_missing`` flag surfaced this.
Modeled on bounty's 0008 migration. Unhitch step matters because
``applications.Activity.audit_ref`` is on_delete=PROTECT.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def _drop_null_user_auditlogs(apps, schema_editor):
    AuditLog = apps.get_model('harbor_core', 'AuditLog')
    Activity = apps.get_model('applications', 'Activity')
    null_user_ids = list(
        AuditLog.objects.filter(user__isnull=True).values_list('id', flat=True)
    )
    if not null_user_ids:
        return
    Activity.objects.filter(audit_ref_id__in=null_user_ids).update(audit_ref=None)
    AuditLog.objects.filter(user__isnull=True).delete()


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('harbor_core', '0007_auditlog_deep_link_snapshot_auditlog_metadata_and_more'),
        ('applications', '0007_applicationcollaborator'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(
            _drop_null_user_auditlogs,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="auditlog",
            name="action",
            field=models.CharField(
                choices=[
                    ("create", "Create"), ("update", "Update"),
                    ("delete", "Delete"), ("status_change", "Status Change"),
                    ("submit", "Submit"), ("approve", "Approve"),
                    ("reject", "Reject"), ("login", "Login"),
                    ("export", "Export"), ("view", "View"),
                    ("archive", "Archive"), ("unarchive", "Unarchive"),
                    ("role_grant_denied", "Role Grant Denied"),
                    ("username_change", "Username Change"),
                    ("email_change", "Email Change"),
                    ("avatar_change", "Avatar Change"),
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
                name='harbor_core_auditlog_user_required',
            ),
        ),
    ]
