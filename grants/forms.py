from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Div, Field, Fieldset, HTML, Layout, Row, Submit
from django import forms
from django.utils.translation import gettext_lazy as _lazy

from core.models import Organization
from .models import GrantPreference, GrantProgram, OpportunityCollaborator, TrackedOpportunity


class GrantProgramForm(forms.ModelForm):
    """Form for creating and editing grant programs.

    The ``agency`` and ``created_by`` fields are excluded because they are
    set automatically in the view based on the authenticated user.
    """

    class Meta:
        model = GrantProgram
        exclude = ['agency', 'created_by', 'is_published', 'published_at',
                    'status']
        widgets = {
            'application_deadline': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M',
            ),
            'posting_date': forms.DateTimeInput(
                attrs={'type': 'datetime-local'},
                format='%Y-%m-%dT%H:%M',
            ),
            'description': forms.Textarea(attrs={'rows': 4}),
            'eligibility_criteria': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Ensure the datetime-local widget receives the correct input format
        self.fields['application_deadline'].input_formats = [
            '%Y-%m-%dT%H:%M',
            '%Y-%m-%dT%H:%M:%S',
        ]
        self.fields['posting_date'].input_formats = [
            '%Y-%m-%dT%H:%M',
            '%Y-%m-%dT%H:%M:%S',
        ]

        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Fieldset(
                _lazy('Program Information'),
                'title',
                'description',
                Row(
                    Column('funding_source', css_class='col-md-6'),
                    Column('grant_type', css_class='col-md-6'),
                ),
                'eligibility_criteria',
            ),
            Fieldset(
                _lazy('Funding Details'),
                Row(
                    Column('total_funding', css_class='col-md-4'),
                    Column('min_award', css_class='col-md-4'),
                    Column('max_award', css_class='col-md-4'),
                ),
                Row(
                    Column('match_required', css_class='col-md-6'),
                    Column('match_percentage', css_class='col-md-6'),
                ),
            ),
            Fieldset(
                _lazy('Timeline'),
                Row(
                    Column('fiscal_year', css_class='col-md-4'),
                    Column('multi_year', css_class='col-md-4'),
                    Column('duration_months', css_class='col-md-4'),
                ),
                Row(
                    Column('application_deadline', css_class='col-md-6'),
                    Column('posting_date', css_class='col-md-6'),
                ),
            ),
            Fieldset(
                _lazy('Contact Information'),
                Row(
                    Column('contact_name', css_class='col-md-4'),
                    Column('contact_email', css_class='col-md-4'),
                    Column('contact_phone', css_class='col-md-4'),
                ),
            ),
            Div(
                Submit('submit', _lazy('Save Program'), css_class='btn btn-primary me-2'),
                css_class='mt-4',
            ),
        )


class TrackedOpportunityForm(forms.ModelForm):
    """Form for updating a tracked federal opportunity's status, priority, notes,
    and optional linked grant program."""

    class Meta:
        model = TrackedOpportunity
        fields = ['status', 'priority', 'notes', 'grant_program']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['grant_program'].required = False
        self.fields['grant_program'].empty_label = _lazy('— No linked program —')

        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Fieldset(
                _lazy('Tracking Details'),
                Row(
                    Column('status', css_class='col-md-6'),
                    Column('priority', css_class='col-md-6'),
                ),
                'notes',
                'grant_program',
            ),
            Div(
                Submit('submit', _lazy('Update Tracking'), css_class='btn btn-primary me-2'),
                css_class='mt-3',
            ),
        )


class CollaboratorForm(forms.Form):
    """Form for adding an internal or external collaborator to a tracked opportunity."""

    COLLABORATOR_TYPE_CHOICES = [
        ('internal', _lazy('Internal User')),
        ('external', _lazy('External Collaborator')),
    ]

    collaborator_type = forms.ChoiceField(
        choices=COLLABORATOR_TYPE_CHOICES,
        label=_lazy('Collaborator Type'),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    username = forms.CharField(
        required=False,
        label=_lazy('Username'),
        help_text=_lazy('Harbor username for internal collaborators.'),
    )
    email = forms.EmailField(
        required=False,
        label=_lazy('Email'),
        help_text=_lazy('Email address for external collaborators.'),
    )
    name = forms.CharField(
        required=False,
        label=_lazy('Name'),
        help_text=_lazy('Full name for external collaborators.'),
    )
    role = forms.ChoiceField(
        choices=OpportunityCollaborator.CollaboratorRole.choices,
        label=_lazy('Role'),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            'collaborator_type',
            'username',
            'email',
            'name',
            'role',
            Div(
                Submit('submit', _lazy('Add Collaborator'), css_class='btn btn-primary btn-sm'),
                css_class='mt-3',
            ),
        )

    def clean(self):
        cleaned_data = super().clean()
        collab_type = cleaned_data.get('collaborator_type')
        username = cleaned_data.get('username', '').strip()
        email = cleaned_data.get('email', '').strip()

        if collab_type == 'internal' and not username:
            self.add_error('username', _lazy('Username is required for internal collaborators.'))
        elif collab_type == 'external' and not email:
            self.add_error('email', _lazy('Email is required for external collaborators.'))

        return cleaned_data


class GrantPreferenceForm(forms.ModelForm):
    """Form for editing AI grant-matching preferences.

    ``focus_areas`` and ``eligible_org_types`` are rendered as multi-select
    checkboxes so that the underlying JSONField stores a simple list.
    """

    focus_areas = forms.MultipleChoiceField(
        choices=GrantPreference.FocusArea.choices,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label=_lazy('Focus Areas'),
        help_text=_lazy('Select one or more areas of interest.'),
    )
    eligible_org_types = forms.MultipleChoiceField(
        choices=Organization.OrgType.choices,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label=_lazy('Eligible Organization Types'),
        help_text=_lazy('Select the organization types you want to find grants for.'),
    )

    class Meta:
        model = GrantPreference
        fields = [
            'focus_areas',
            'eligible_org_types',
            'funding_range_min',
            'funding_range_max',
            'description',
            'is_active',
        ]
        widgets = {
            'description': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Describe your priorities, mission, or what you '
                               'are looking for in your own words...',
            }),
        }
        labels = {
            'funding_range_min': _lazy('Minimum Funding Amount'),
            'funding_range_max': _lazy('Maximum Funding Amount'),
            'description': _lazy('Additional Context'),
            'is_active': _lazy('Enable AI Matching'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_method = 'post'
        select_all_link = (
            '<a href="#" class="select-all-toggle small text-primary text-decoration-none" '
            'data-select-all="Select All" data-deselect-all="Deselect All">'
            'Select All</a>'
        )

        self.helper.layout = Layout(
            Fieldset(
                _lazy('Areas of Interest'),
                HTML(select_all_link),
                'focus_areas',
            ),
            Fieldset(
                _lazy('Organization Types'),
                HTML(select_all_link),
                'eligible_org_types',
            ),
            Fieldset(
                _lazy('Funding Range'),
                Row(
                    Column('funding_range_min', css_class='col-md-6'),
                    Column('funding_range_max', css_class='col-md-6'),
                ),
            ),
            Fieldset(
                _lazy('Additional Context'),
                'description',
            ),
            Field('is_active'),
            Div(
                Submit('submit', _lazy('Save Preferences'), css_class='btn btn-primary me-2'),
                css_class='mt-4',
            ),
        )
