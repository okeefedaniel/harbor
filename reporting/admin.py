from django.contrib import admin

from .models import Report, ReportDocument, ReportTemplate, SF425Report


# ---------------------------------------------------------------------------
# ReportTemplate
# ---------------------------------------------------------------------------
@admin.register(ReportTemplate)
class ReportTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'report_type', 'agency', 'frequency', 'is_active', 'created_at')
    list_filter = ('report_type', 'frequency', 'is_active', 'agency')
    search_fields = ('name',)
    readonly_fields = ('id', 'created_at', 'updated_at')


# ---------------------------------------------------------------------------
# ReportDocument (inline)
# ---------------------------------------------------------------------------
class ReportDocumentInline(admin.TabularInline):
    model = ReportDocument
    extra = 0
    readonly_fields = ('id', 'created_at')


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------
@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = (
        'report_type', 'award', 'status', 'due_date',
        'reporting_period_start', 'reporting_period_end',
        'submitted_at', 'reviewed_at',
    )
    list_filter = ('report_type', 'status')
    search_fields = ('award__id',)
    readonly_fields = ('id', 'created_at', 'updated_at')
    date_hierarchy = 'due_date'
    inlines = [ReportDocumentInline]


# ---------------------------------------------------------------------------
# ReportDocument (standalone)
# ---------------------------------------------------------------------------
@admin.register(ReportDocument)
class ReportDocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'report', 'uploaded_by', 'created_at')
    search_fields = ('title',)
    readonly_fields = ('id', 'created_at')


# ---------------------------------------------------------------------------
# SF425Report
# ---------------------------------------------------------------------------
@admin.register(SF425Report)
class SF425ReportAdmin(admin.ModelAdmin):
    list_display = (
        'award', 'status', 'reporting_period_start', 'reporting_period_end',
        'federal_expenditures', 'remaining_federal_funds', 'generated_at',
    )
    list_filter = ('status',)
    search_fields = ('award__id',)
    readonly_fields = ('id', 'generated_at')
