from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import (
    SignatureDocument,
    SignatureFlow,
    SignatureFlowStep,
    SignaturePlacement,
    SignatureRole,
    SigningPacket,
    SigningStep,
    UserSignature,
)


class SignatureFlowStepInline(admin.TabularInline):
    model = SignatureFlowStep
    extra = 0
    ordering = ['order']


class SignatureDocumentInline(admin.TabularInline):
    model = SignatureDocument
    extra = 0
    readonly_fields = ['page_count', 'created_at']


@admin.register(SignatureFlow)
class SignatureFlowAdmin(admin.ModelAdmin):
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [SignatureFlowStepInline, SignatureDocumentInline]

    def get_list_display(self, request):
        base = ['name']
        if hasattr(SignatureFlow, 'grant_program'):
            base.append('grant_program')
        base.extend(['is_active', 'created_by', 'created_at'])
        return base


class SignaturePlacementInline(admin.TabularInline):
    model = SignaturePlacement
    extra = 0
    ordering = ['page_number', 'y']


@admin.register(SignatureDocument)
class SignatureDocumentAdmin(admin.ModelAdmin):
    list_display = ['title', 'flow', 'page_count', 'uploaded_by', 'created_at']
    list_filter = ['created_at']
    search_fields = ['title', 'description']
    readonly_fields = ['page_count', 'created_at', 'updated_at']
    inlines = [SignaturePlacementInline]


class SigningStepInline(admin.TabularInline):
    model = SigningStep
    extra = 0
    ordering = ['order']
    readonly_fields = ['signed_at', 'signed_ip', 'created_at']


@admin.register(SigningPacket)
class SigningPacketAdmin(admin.ModelAdmin):
    list_display = ['title', 'flow', 'status', 'initiated_by', 'created_at', 'completed_at']
    list_filter = ['status', 'created_at']
    search_fields = ['title']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [SigningStepInline]


@admin.register(UserSignature)
class UserSignatureAdmin(admin.ModelAdmin):
    list_display = ['user', 'label', 'signature_type', 'is_default', 'created_at']
    list_filter = ['signature_type', 'is_default']
    search_fields = ['user__first_name', 'user__last_name', 'label']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(SignatureRole)
class SignatureRoleAdmin(admin.ModelAdmin):
    list_display = ['key', 'label', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['key', 'label']
    readonly_fields = ['created_at', 'updated_at']
    prepopulated_fields = {'key': ('label',)}
