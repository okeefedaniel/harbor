from django.contrib import admin

from .models import (
    Budget,
    BudgetLineItem,
    CoreCTAccountString,
    DrawdownRequest,
    Transaction,
)


class BudgetLineItemInline(admin.TabularInline):
    model = BudgetLineItem
    extra = 1


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = [
        'award', 'fiscal_year', 'total_amount', 'status',
        'submitted_at', 'approved_at',
    ]
    list_filter = ['status', 'fiscal_year']
    search_fields = ['award__award_number']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [BudgetLineItemInline]


@admin.register(BudgetLineItem)
class BudgetLineItemAdmin(admin.ModelAdmin):
    list_display = [
        'budget', 'category', 'description', 'amount',
        'federal_share', 'state_share', 'match_share',
    ]
    list_filter = ['category']
    search_fields = ['description', 'budget__award__award_number']


@admin.register(DrawdownRequest)
class DrawdownRequestAdmin(admin.ModelAdmin):
    list_display = [
        'award', 'request_number', 'amount', 'period_start',
        'period_end', 'status', 'submitted_by', 'submitted_at',
    ]
    list_filter = ['status', 'submitted_at']
    search_fields = ['request_number', 'award__award_number']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'created_at'


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = [
        'award', 'transaction_type', 'amount', 'reference_number',
        'core_ct_reference', 'transaction_date', 'created_by',
    ]
    list_filter = ['transaction_type', 'transaction_date']
    search_fields = [
        'reference_number', 'core_ct_reference',
        'award__award_number', 'description',
    ]
    readonly_fields = ['created_at']
    date_hierarchy = 'transaction_date'


@admin.register(CoreCTAccountString)
class CoreCTAccountStringAdmin(admin.ModelAdmin):
    list_display = [
        'award', 'fund', 'department', 'sid',
        'program', 'account', 'project',
    ]
    search_fields = [
        'award__award_number', 'fund', 'department',
        'program', 'account', 'project',
    ]
