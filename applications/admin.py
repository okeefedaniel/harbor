from django.contrib import admin

from .models import (
    Application,
    ApplicationAssignment,
    ApplicationComment,
    ApplicationComplianceItem,
    ApplicationDocument,
    ApplicationSection,
    ApplicationStatusHistory,
    StaffDocument,
)


class ApplicationSectionInline(admin.TabularInline):
    model = ApplicationSection
    extra = 0


class ApplicationDocumentInline(admin.TabularInline):
    model = ApplicationDocument
    extra = 0
    readonly_fields = ('created_at',)


class ApplicationCommentInline(admin.StackedInline):
    model = ApplicationComment
    extra = 0
    readonly_fields = ('created_at',)


class ApplicationStatusHistoryInline(admin.TabularInline):
    model = ApplicationStatusHistory
    extra = 0
    readonly_fields = ('old_status', 'new_status', 'changed_by', 'comment', 'timestamp')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = (
        'project_title',
        'organization',
        'grant_program',
        'status',
        'requested_amount',
        'submitted_at',
    )
    list_filter = ('status', 'grant_program', 'submitted_at')
    search_fields = ('project_title', 'project_description', 'organization__name')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
    inlines = [
        ApplicationSectionInline,
        ApplicationDocumentInline,
        ApplicationCommentInline,
        ApplicationStatusHistoryInline,
    ]

    fieldsets = (
        (None, {
            'fields': ('grant_program', 'applicant', 'organization', 'status', 'submitted_at'),
        }),
        ('Project Details', {
            'fields': (
                'project_title', 'project_description',
                'requested_amount', 'proposed_start_date', 'proposed_end_date',
            ),
        }),
        ('Match Information', {
            'fields': ('match_amount', 'match_description'),
        }),
        ('Audit', {
            'fields': ('created_at', 'updated_at'),
        }),
    )


@admin.register(ApplicationSection)
class ApplicationSectionAdmin(admin.ModelAdmin):
    list_display = ('section_name', 'application', 'section_order', 'is_complete')
    list_filter = ('is_complete',)
    search_fields = ('section_name',)


@admin.register(ApplicationDocument)
class ApplicationDocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'application', 'document_type', 'uploaded_by', 'created_at')
    list_filter = ('document_type',)
    search_fields = ('title', 'description')
    readonly_fields = ('created_at',)


@admin.register(ApplicationComment)
class ApplicationCommentAdmin(admin.ModelAdmin):
    list_display = ('application', 'author', 'is_internal', 'created_at')
    list_filter = ('is_internal',)
    search_fields = ('content',)
    readonly_fields = ('created_at',)


@admin.register(ApplicationStatusHistory)
class ApplicationStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ('application', 'old_status', 'new_status', 'changed_by', 'timestamp')
    list_filter = ('old_status', 'new_status')
    readonly_fields = ('application', 'old_status', 'new_status', 'changed_by', 'comment', 'timestamp')

    def has_add_permission(self, request):
        return False


@admin.register(ApplicationComplianceItem)
class ApplicationComplianceItemAdmin(admin.ModelAdmin):
    list_display = (
        'application', 'item_type', 'is_required', 'is_verified',
        'verified_by', 'verified_at',
    )
    list_filter = ('is_required', 'is_verified', 'item_type')
    search_fields = ('application__project_title', 'notes')
    readonly_fields = ('verified_at',)


@admin.register(StaffDocument)
class StaffDocumentAdmin(admin.ModelAdmin):
    list_display = (
        'application', 'document_type', 'uploaded_by', 'created_at',
    )
    list_filter = ('document_type',)
    search_fields = ('notes', 'application__project_title')
    readonly_fields = ('created_at',)


@admin.register(ApplicationAssignment)
class ApplicationAssignmentAdmin(admin.ModelAdmin):
    list_display = (
        'application', 'assigned_to', 'assigned_by', 'assignment_type',
        'status', 'assigned_at',
    )
    list_filter = ('status', 'assignment_type')
    search_fields = (
        'application__project_title',
        'assigned_to__username', 'assigned_to__first_name', 'assigned_to__last_name',
        'notes',
    )
    readonly_fields = ('assigned_at', 'updated_at')
