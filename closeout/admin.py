from django.contrib import admin

from .models import Closeout, CloseoutChecklist, CloseoutDocument, FundReturn


# ---------------------------------------------------------------------------
# CloseoutChecklist (inline)
# ---------------------------------------------------------------------------
class CloseoutChecklistInline(admin.TabularInline):
    model = CloseoutChecklist
    extra = 0
    readonly_fields = ('id', 'completed_at')


# ---------------------------------------------------------------------------
# CloseoutDocument (inline)
# ---------------------------------------------------------------------------
class CloseoutDocumentInline(admin.TabularInline):
    model = CloseoutDocument
    extra = 0
    readonly_fields = ('id', 'created_at')


# ---------------------------------------------------------------------------
# FundReturn (inline)
# ---------------------------------------------------------------------------
class FundReturnInline(admin.TabularInline):
    model = FundReturn
    extra = 0
    readonly_fields = ('id', 'created_at')


# ---------------------------------------------------------------------------
# Closeout
# ---------------------------------------------------------------------------
@admin.register(Closeout)
class CloseoutAdmin(admin.ModelAdmin):
    list_display = ('award', 'status', 'initiated_by', 'initiated_at', 'completed_at')
    list_filter = ('status',)
    search_fields = ('award__id',)
    readonly_fields = ('id', 'initiated_at')
    inlines = [CloseoutChecklistInline, CloseoutDocumentInline, FundReturnInline]


# ---------------------------------------------------------------------------
# CloseoutChecklist (standalone)
# ---------------------------------------------------------------------------
@admin.register(CloseoutChecklist)
class CloseoutChecklistAdmin(admin.ModelAdmin):
    list_display = ('item_name', 'closeout', 'is_required', 'is_completed', 'completed_at')
    list_filter = ('is_required', 'is_completed')
    search_fields = ('item_name', 'item_description')
    readonly_fields = ('id',)


# ---------------------------------------------------------------------------
# CloseoutDocument (standalone)
# ---------------------------------------------------------------------------
@admin.register(CloseoutDocument)
class CloseoutDocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'document_type', 'closeout', 'uploaded_by', 'created_at')
    list_filter = ('document_type',)
    search_fields = ('title',)
    readonly_fields = ('id', 'created_at')


# ---------------------------------------------------------------------------
# FundReturn (standalone)
# ---------------------------------------------------------------------------
@admin.register(FundReturn)
class FundReturnAdmin(admin.ModelAdmin):
    list_display = ('closeout', 'amount', 'status', 'payment_reference', 'processed_at', 'created_at')
    list_filter = ('status',)
    search_fields = ('payment_reference', 'reason')
    readonly_fields = ('id', 'created_at')
