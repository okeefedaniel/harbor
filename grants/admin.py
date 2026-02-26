from django.contrib import admin

from .models import (
    FederalOpportunity,
    FundingSource,
    GrantPreference,
    GrantProgram,
    GrantProgramDocument,
    OpportunityCollaborator,
    OpportunityMatch,
    SavedProgram,
    TrackedOpportunity,
)


class GrantProgramDocumentInline(admin.TabularInline):
    model = GrantProgramDocument
    extra = 0
    readonly_fields = ('created_at',)


@admin.register(FundingSource)
class FundingSourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'source_type', 'cfda_number', 'is_active')
    list_filter = ('source_type', 'is_active')
    search_fields = ('name', 'cfda_number', 'federal_agency')


@admin.register(GrantProgram)
class GrantProgramAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'agency',
        'grant_type',
        'status',
        'total_funding',
        'application_deadline',
        'is_published',
    )
    list_filter = ('status', 'grant_type', 'is_published', 'fiscal_year', 'agency')
    search_fields = ('title', 'description')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'posting_date'
    inlines = [GrantProgramDocumentInline]

    fieldsets = (
        (None, {
            'fields': ('agency', 'title', 'description', 'funding_source', 'grant_type'),
        }),
        ('Eligibility', {
            'fields': ('eligibility_criteria',),
        }),
        ('Funding', {
            'fields': (
                'total_funding', 'min_award', 'max_award',
                'match_required', 'match_percentage',
            ),
        }),
        ('Timeline', {
            'fields': (
                'fiscal_year', 'multi_year', 'duration_months',
                'posting_date', 'application_deadline',
            ),
        }),
        ('Publishing', {
            'fields': ('status', 'is_published', 'published_at'),
        }),
        ('Contact', {
            'fields': ('contact_name', 'contact_email', 'contact_phone'),
        }),
        ('Audit', {
            'fields': ('created_by', 'created_at', 'updated_at'),
        }),
    )


@admin.register(GrantProgramDocument)
class GrantProgramDocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'grant_program', 'document_type', 'uploaded_by', 'created_at')
    list_filter = ('document_type',)
    search_fields = ('title', 'description')
    readonly_fields = ('created_at',)


# ---------------------------------------------------------------------------
# Federal Opportunity (read-only admin, synced from Grants.gov)
# ---------------------------------------------------------------------------
@admin.register(FederalOpportunity)
class FederalOpportunityAdmin(admin.ModelAdmin):
    list_display = (
        'opportunity_number', 'title_short', 'agency_name',
        'opportunity_status', 'close_date', 'total_funding', 'synced_at',
    )
    list_filter = ('opportunity_status', 'funding_instrument')
    search_fields = ('title', 'agency_name', 'opportunity_number', 'agency_code')
    readonly_fields = (
        'opportunity_id', 'opportunity_number', 'title', 'description',
        'agency_name', 'agency_code', 'category', 'funding_instrument',
        'cfda_numbers', 'award_floor', 'award_ceiling', 'expected_awards',
        'total_funding', 'post_date', 'close_date', 'archive_date',
        'opportunity_status', 'applicant_types', 'eligible_applicants',
        'grants_gov_url', 'synced_at', 'raw_data',
    )
    date_hierarchy = 'post_date'

    def title_short(self, obj):
        return obj.title[:80] + '...' if len(obj.title) > 80 else obj.title
    title_short.short_description = 'Title'

    def has_add_permission(self, request):
        return False  # Read-only: data comes from API sync

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


class OpportunityCollaboratorInline(admin.TabularInline):
    model = OpportunityCollaborator
    extra = 0
    readonly_fields = ('invited_at',)


@admin.register(TrackedOpportunity)
class TrackedOpportunityAdmin(admin.ModelAdmin):
    list_display = ('federal_opportunity', 'tracked_by', 'status', 'priority', 'grant_program', 'updated_at')
    list_filter = ('status', 'priority')
    search_fields = ('federal_opportunity__title', 'notes')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [OpportunityCollaboratorInline]


@admin.register(SavedProgram)
class SavedProgramAdmin(admin.ModelAdmin):
    list_display = ('grant_program', 'user', 'interest_level', 'created_at')
    list_filter = ('interest_level',)
    search_fields = ('grant_program__title', 'user__username', 'notes')
    readonly_fields = ('created_at', 'updated_at')


# ---------------------------------------------------------------------------
# AI Grant Matching
# ---------------------------------------------------------------------------
@admin.register(GrantPreference)
class GrantPreferenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'focus_areas_display', 'is_active', 'updated_at')
    list_filter = ('is_active',)
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'description')
    readonly_fields = ('created_at', 'updated_at')

    def focus_areas_display(self, obj):
        if obj.focus_areas:
            labels = dict(GrantPreference.FocusArea.choices)
            return ', '.join(str(labels.get(a, a)) for a in obj.focus_areas[:3])
        return '—'
    focus_areas_display.short_description = 'Focus Areas'


@admin.register(OpportunityMatch)
class OpportunityMatchAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'source', 'opportunity_title_short', 'relevance_score',
        'status', 'feedback', 'notified', 'created_at',
    )
    list_filter = ('source', 'status', 'feedback', 'notified')
    search_fields = (
        'user__username', 'federal_opportunity__title', 'grant_program__title',
        'explanation',
    )
    readonly_fields = ('created_at', 'updated_at', 'notified_at', 'feedback', 'feedback_reason')

    def opportunity_title_short(self, obj):
        title = obj.opportunity_title
        return title[:60] + '...' if len(title) > 60 else title
    opportunity_title_short.short_description = 'Opportunity'
