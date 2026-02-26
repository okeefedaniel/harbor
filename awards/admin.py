from django.contrib import admin

from .models import Award, AwardAmendment, AwardDocument


class AwardAmendmentInline(admin.TabularInline):
    model = AwardAmendment
    extra = 0
    readonly_fields = ['created_at']


class AwardDocumentInline(admin.TabularInline):
    model = AwardDocument
    extra = 0
    readonly_fields = ['created_at']


@admin.register(Award)
class AwardAdmin(admin.ModelAdmin):
    list_display = [
        'award_number', 'title', 'grant_program', 'agency',
        'organization', 'status', 'award_amount', 'start_date', 'end_date',
    ]
    list_filter = ['status', 'agency', 'requires_match', 'created_at']
    search_fields = ['award_number', 'title', 'organization__name']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [AwardAmendmentInline, AwardDocumentInline]
    date_hierarchy = 'created_at'


@admin.register(AwardAmendment)
class AwardAmendmentAdmin(admin.ModelAdmin):
    list_display = [
        'award', 'amendment_number', 'amendment_type',
        'status', 'requested_by', 'created_at',
    ]
    list_filter = ['amendment_type', 'status']
    search_fields = ['award__award_number', 'description']
    readonly_fields = ['created_at']


@admin.register(AwardDocument)
class AwardDocumentAdmin(admin.ModelAdmin):
    list_display = ['award', 'title', 'document_type', 'uploaded_by', 'created_at']
    list_filter = ['document_type', 'created_at']
    search_fields = ['title', 'award__award_number']
    readonly_fields = ['created_at']
