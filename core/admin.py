from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Agency, AuditLog, Notification, Organization, User


# ---------------------------------------------------------------------------
# Organization
# ---------------------------------------------------------------------------
@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'org_type', 'city', 'state', 'is_active', 'created_at')
    list_filter = ('org_type', 'is_active', 'sam_registered', 'state')
    search_fields = ('name', 'ein', 'uei_number', 'duns_number')
    readonly_fields = ('id', 'created_at', 'updated_at')


# ---------------------------------------------------------------------------
# Agency
# ---------------------------------------------------------------------------
@admin.register(Agency)
class AgencyAdmin(admin.ModelAdmin):
    list_display = (
        'abbreviation', 'name', 'department_code', 'can_be_grantor',
        'is_active', 'onboarded_at',
    )
    list_filter = ('is_active', 'can_be_grantor', 'can_be_grantee')
    search_fields = ('name', 'abbreviation', 'department_code')
    readonly_fields = ('id', 'created_at', 'updated_at')


# ---------------------------------------------------------------------------
# User (extends Django UserAdmin)
# ---------------------------------------------------------------------------
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        'username', 'email', 'first_name', 'last_name', 'role',
        'agency', 'is_state_user', 'is_active',
    )
    list_filter = BaseUserAdmin.list_filter + ('role', 'is_state_user', 'agency')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    readonly_fields = ('id', 'created_at', 'updated_at')

    fieldsets = BaseUserAdmin.fieldsets + (
        ('Grantify Profile', {
            'fields': (
                'role', 'title', 'phone', 'agency', 'organization',
                'is_state_user', 'accepted_terms', 'accepted_terms_at',
                'anthropic_api_key',
            ),
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
        }),
    )

    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Grantify Profile', {
            'fields': ('role', 'agency', 'organization', 'is_state_user'),
        }),
    )


# ---------------------------------------------------------------------------
# AuditLog
# ---------------------------------------------------------------------------
@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'action', 'entity_type', 'entity_id')
    list_filter = ('action', 'entity_type')
    search_fields = ('description', 'entity_type', 'entity_id')
    readonly_fields = (
        'id', 'user', 'action', 'entity_type', 'entity_id',
        'description', 'changes', 'ip_address', 'timestamp',
    )
    date_hierarchy = 'timestamp'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


# ---------------------------------------------------------------------------
# Notification
# ---------------------------------------------------------------------------
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'recipient', 'priority', 'is_read', 'created_at')
    list_filter = ('priority', 'is_read')
    search_fields = ('title', 'message')
    readonly_fields = ('id', 'created_at')
