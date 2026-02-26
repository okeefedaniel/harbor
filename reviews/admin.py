from django.contrib import admin

from .models import (
    ReviewAssignment,
    ReviewRubric,
    ReviewScore,
    ReviewSummary,
    RubricCriterion,
)


class RubricCriterionInline(admin.TabularInline):
    model = RubricCriterion
    extra = 1
    ordering = ['order']


@admin.register(ReviewRubric)
class ReviewRubricAdmin(admin.ModelAdmin):
    list_display = ['name', 'grant_program', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    inlines = [RubricCriterionInline]


@admin.register(RubricCriterion)
class RubricCriterionAdmin(admin.ModelAdmin):
    list_display = ['name', 'rubric', 'max_score', 'weight', 'order']
    list_filter = ['rubric']
    search_fields = ['name']


class ReviewScoreInline(admin.TabularInline):
    model = ReviewScore
    extra = 0
    readonly_fields = ['criterion', 'score', 'comment']


@admin.register(ReviewAssignment)
class ReviewAssignmentAdmin(admin.ModelAdmin):
    list_display = [
        'application', 'reviewer', 'rubric', 'status',
        'assigned_at', 'completed_at', 'conflict_of_interest',
    ]
    list_filter = ['status', 'conflict_of_interest', 'assigned_at']
    search_fields = [
        'reviewer__username', 'reviewer__first_name', 'reviewer__last_name',
    ]
    inlines = [ReviewScoreInline]


@admin.register(ReviewScore)
class ReviewScoreAdmin(admin.ModelAdmin):
    list_display = ['assignment', 'criterion', 'score']
    list_filter = ['criterion__rubric']


@admin.register(ReviewSummary)
class ReviewSummaryAdmin(admin.ModelAdmin):
    list_display = [
        'application', 'average_score', 'total_reviews',
        'recommendation', 'risk_level', 'updated_at',
    ]
    list_filter = ['recommendation', 'risk_level']
    readonly_fields = ['created_at', 'updated_at']
