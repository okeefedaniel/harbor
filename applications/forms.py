from django import forms
from django.utils.translation import gettext_lazy as _lazy

from .models import (
    Application,
    ApplicationAssignment,
    ApplicationComment,
    ApplicationDocument,
    StaffDocument,
)


class ApplicationForm(forms.ModelForm):
    """Form for creating and editing a grant application."""

    class Meta:
        model = Application
        fields = [
            'project_title',
            'project_description',
            'requested_amount',
            'proposed_start_date',
            'proposed_end_date',
            'match_amount',
            'match_description',
        ]
        widgets = {
            'project_description': forms.Textarea(attrs={'rows': 6}),
            'proposed_start_date': forms.DateInput(attrs={'type': 'date'}),
            'proposed_end_date': forms.DateInput(attrs={'type': 'date'}),
            'match_description': forms.Textarea(attrs={'rows': 6}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('proposed_start_date')
        end = cleaned_data.get('proposed_end_date')
        if start and end and end <= start:
            raise forms.ValidationError(
                _lazy('Proposed end date must be after the start date.')
            )
        return cleaned_data


class ApplicationDocumentForm(forms.ModelForm):
    """Form for uploading a supporting document to an application."""

    class Meta:
        model = ApplicationDocument
        fields = ['title', 'description', 'file', 'document_type']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class ApplicationCommentForm(forms.ModelForm):
    """Form for adding a comment to an application.

    The ``is_internal`` field is only rendered for staff users; templates
    should conditionally show it based on the user's role.
    """

    class Meta:
        model = ApplicationComment
        fields = ['content', 'is_internal']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 4}),
        }


class StaffDocumentForm(forms.ModelForm):
    """Form for uploading an internal staff document to an application."""

    class Meta:
        model = StaffDocument
        fields = ['title', 'description', 'file', 'document_type']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2}),
        }


class StatusChangeForm(forms.Form):
    """Form for staff to change an application's status.

    Requires a comment explaining the decision (especially for
    denial or revision requests).
    """

    VALID_TRANSITIONS = {
        'submitted': ['under_review'],
        'under_review': ['approved', 'denied', 'revision_requested'],
    }

    new_status = forms.ChoiceField(
        choices=Application.Status.choices,
        widget=forms.HiddenInput(),
    )
    comment = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': _lazy('Provide a reason for this status change...'),
        }),
        required=True,
        help_text=_lazy('A comment is required for all status changes.'),
    )

    def __init__(self, *args, current_status=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_status = current_status

    def clean_new_status(self):
        new_status = self.cleaned_data['new_status']
        if self.current_status:
            allowed = self.VALID_TRANSITIONS.get(self.current_status, [])
            if new_status not in allowed:
                raise forms.ValidationError(
                    _lazy('Cannot transition from "%(current)s" to '
                          '"%(new)s". Allowed: %(allowed)s.') % {
                        'current': self.current_status,
                        'new': new_status,
                        'allowed': ", ".join(allowed) or _lazy("none"),
                    }
                )
        return new_status


class ApplicationAssignmentForm(forms.ModelForm):
    """Form for managers to assign staff to process an application."""

    class Meta:
        model = ApplicationAssignment
        fields = ['assigned_to', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Optional notes about this assignment…'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from core.models import User
        self.fields['assigned_to'].queryset = User.objects.filter(
            role__in=[
                User.Role.PROGRAM_OFFICER,
                User.Role.AGENCY_ADMIN,
                User.Role.FISCAL_OFFICER,
                User.Role.SYSTEM_ADMIN,
            ],
            is_active=True,
        ).order_by('last_name', 'first_name')
        self.fields['assigned_to'].label = _lazy('Assign To')
