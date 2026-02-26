"""
Clean up demo users to one per role with descriptive names.

Creates exactly 7 users — one for each RBAC role — with clear,
demo-friendly names and a shared easy-to-remember password.

Run with:  python manage.py cleanup_demo_users
"""
from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Agency, Organization, User

PASSWORD = "demo2026"

# Map: old_username -> (new_username, first_name, last_name)
RENAME_MAP = {
    "sarah.chen": ("agency.admin", "Agency", "Administrator"),
    "mike.russo": ("program.officer", "Program", "Officer"),
    "lisa.patel": ("fiscal.officer", "Fiscal", "Officer"),
    "dr.martinez": ("reviewer", "Grant", "Reviewer"),
    "john.doe": ("applicant", "Grant", "Applicant"),
}

# Users to delete after reassigning their data to the primary user of the same role
DELETE_MAP = {
    # old_username -> primary username (after rename) to inherit FK data
    "karen.wright": "agency.admin",
    "james.oconnor": "program.officer",
    "prof.chang": "reviewer",
    "ms.williams": "reviewer",
    "maria.garcia": "applicant",
    "robert.kim": "applicant",
    "emily.johnson": "applicant",
    "thomas.brown": "applicant",
}


def _get_user_fk_fields():
    """Find every ForeignKey / OneToOneField that points to the User model."""
    fk_fields = []
    for model in apps.get_models():
        for field in model._meta.get_fields():
            if hasattr(field, "related_model") and field.related_model is User:
                if hasattr(field, "field"):  # reverse relation
                    continue
                fk_fields.append((model, field))
    return fk_fields


def _reassign_user_data(from_user, to_user, fk_fields, stdout):
    """Point all FK references from `from_user` to `to_user`."""
    for model, field in fk_fields:
        qs = model.objects.filter(**{field.name: from_user})
        count = qs.count()
        if count:
            qs.update(**{field.name: to_user})
            stdout.write(
                f"    Reassigned {count} {model.__name__}.{field.name} "
                f"rows from {from_user.username} -> {to_user.username}"
            )


class Command(BaseCommand):
    help = "Clean up demo users to one per role with descriptive names."

    @transaction.atomic
    def handle(self, *args, **options):
        fk_fields = _get_user_fk_fields()
        self.stdout.write(f"Found {len(fk_fields)} FK fields pointing to User.\n")

        # ── 1. Rename primary users ──────────────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING("\n  Renaming primary users..."))
        for old_username, (new_username, first, last) in RENAME_MAP.items():
            try:
                user = User.objects.get(username=old_username)
            except User.DoesNotExist:
                # Maybe already renamed from a previous run
                if User.objects.filter(username=new_username).exists():
                    self.stdout.write(f"  {new_username} already exists, skipping.")
                    continue
                self.stdout.write(
                    self.style.WARNING(f"  {old_username} not found, skipping.")
                )
                continue

            user.username = new_username
            user.first_name = first
            user.last_name = last
            user.set_password(PASSWORD)
            user.save()
            self.stdout.write(
                self.style.SUCCESS(f"  {old_username} -> {new_username} ({first} {last})")
            )

        # ── 2. Reassign data & delete duplicates ─────────────────
        self.stdout.write(self.style.MIGRATE_HEADING("\n  Reassigning data & deleting duplicates..."))
        for old_username, primary_username in DELETE_MAP.items():
            try:
                from_user = User.objects.get(username=old_username)
            except User.DoesNotExist:
                self.stdout.write(f"  {old_username} not found (already deleted?), skipping.")
                continue

            try:
                to_user = User.objects.get(username=primary_username)
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.WARNING(
                        f"  Primary {primary_username} not found, cannot reassign {old_username}."
                    )
                )
                continue

            _reassign_user_data(from_user, to_user, fk_fields, self.stdout)
            from_user.delete()
            self.stdout.write(
                self.style.SUCCESS(f"  Deleted {old_username} (data -> {primary_username})")
            )

        # ── 3. Normalize admin user ──────────────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING("\n  Normalizing admin user..."))
        try:
            admin = User.objects.get(username="admin")
            admin.first_name = "System"
            admin.last_name = "Administrator"
            admin.role = "system_admin"
            admin.is_staff = True
            admin.is_superuser = True
            admin.set_password(PASSWORD)
            admin.save()
            self.stdout.write(self.style.SUCCESS("  admin -> password set to demo2026"))
        except User.DoesNotExist:
            self.stdout.write(self.style.WARNING("  admin user not found."))

        # ── 4. Create auditor if missing ─────────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING("\n  Creating auditor user..."))
        auditor, created = User.objects.get_or_create(
            username="auditor",
            defaults=dict(
                first_name="System",
                last_name="Auditor",
                role="auditor",
                email="auditor@dok.gov",
                is_state_user=True,
                accepted_terms=True,
                accepted_terms_at=User.objects.first().accepted_terms_at,
            ),
        )
        if created:
            agency = Agency.objects.filter(abbreviation="OBM").first()
            if agency:
                auditor.agency = agency
            auditor.set_password(PASSWORD)
            auditor.save()
            self.stdout.write(self.style.SUCCESS("  Created auditor (System Auditor)"))
        else:
            auditor.first_name = "System"
            auditor.last_name = "Auditor"
            auditor.set_password(PASSWORD)
            auditor.save()
            self.stdout.write("  auditor already exists, updated password.")

        # ── Summary ──────────────────────────────────────────────
        self.stdout.write(self.style.MIGRATE_HEADING("\n  Final user list:"))
        for u in User.objects.all().order_by("role", "username"):
            self.stdout.write(
                f"  {u.username:<20} {u.first_name} {u.last_name:<20} "
                f"role={u.role:<16} staff={u.is_staff}"
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"\n  Done! {User.objects.count()} users remain. "
                f"All passwords set to '{PASSWORD}'."
            )
        )
