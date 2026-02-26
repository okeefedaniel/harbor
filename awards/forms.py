from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Div, Field, Fieldset, Layout, Row, Submit
from django import forms
from django.utils.translation import gettext_lazy as _lazy

from .models import Award, AwardAmendment, AwardDocument, SignatureRequest


class AwardForm(forms.ModelForm):
    """Form for creating and editing grant awards.

    The ``application``, ``grant_program``, ``agency``, ``recipient``,
    ``organization``, and ``approved_by/approved_at/executed_at`` fields
    are excluded because they are set automatically in the view.
    """

    class Meta:
        model = Award
        fields = [
            'title',
            'award_number',
            'award_amount',
            'award_date',
            'start_date',
            'end_date',
            'terms_and_conditions',
            'special_conditions',
            'requires_match',
            'match_amount',
        ]
        widgets = {
            'award_date': forms.DateInput(attrs={'type': 'date'}),
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'terms_and_conditions': forms.Textarea(attrs={'rows': 5}),
            'special_conditions': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Fieldset(
                _lazy('Award Information'),
                'title',
                Row(
                    Column('award_number', css_class='col-md-6'),
                    Column('award_amount', css_class='col-md-6'),
                ),
                Row(
                    Column('award_date', css_class='col-md-4'),
                    Column('start_date', css_class='col-md-4'),
                    Column('end_date', css_class='col-md-4'),
                ),
            ),
            Fieldset(
                _lazy('Terms & Conditions'),
                'terms_and_conditions',
                'special_conditions',
            ),
            Fieldset(
                _lazy('Match Requirements'),
                Row(
                    Column('requires_match', css_class='col-md-6'),
                    Column('match_amount', css_class='col-md-6'),
                ),
            ),
            Div(
                Submit('submit', _lazy('Save Award'), css_class='btn btn-primary me-2'),
                css_class='mt-4',
            ),
        )


class AwardDocumentForm(forms.ModelForm):
    """Form for uploading award documents.

    The ``award`` and ``uploaded_by`` fields are set in the view.
    """

    class Meta:
        model = AwardDocument
        fields = [
            'title',
            'description',
            'document_type',
            'file',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Fieldset(
                _lazy('Document Details'),
                'title',
                'document_type',
                'description',
                'file',
            ),
            Div(
                Submit('submit', _lazy('Upload Document'), css_class='btn btn-primary me-2'),
                css_class='mt-4',
            ),
        )


class AwardAmendmentForm(forms.ModelForm):
    """Form for creating award amendments.

    The ``award``, ``amendment_number``, ``requested_by``, ``approved_by``,
    ``status``, ``submitted_at``, and ``approved_at`` fields are set in the view.
    """

    class Meta:
        model = AwardAmendment
        fields = [
            'amendment_type',
            'description',
            'old_value',
            'new_value',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'old_value': forms.Textarea(attrs={'rows': 3}),
            'new_value': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Fieldset(
                _lazy('Amendment Details'),
                'amendment_type',
                'description',
                Row(
                    Column('old_value', css_class='col-md-6'),
                    Column('new_value', css_class='col-md-6'),
                ),
            ),
            Div(
                Submit('submit', _lazy('Submit Amendment'), css_class='btn btn-primary me-2'),
                css_class='mt-4',
            ),
        )


class SignatureRequestForm(forms.Form):
    """Form for requesting an e-signature on an award agreement via DocuSign."""

    signer_name = forms.CharField(max_length=255, label=_lazy('Signer Name'))
    signer_email = forms.EmailField(label=_lazy('Signer Email'))
    cc_email = forms.EmailField(required=False, label=_lazy('CC Email (optional)'))
    notes = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False,
        label=_lazy('Notes'),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Fieldset(
                _lazy('Signature Details'),
                'signer_name',
                'signer_email',
                'cc_email',
                'notes',
            ),
            Div(
                Submit('submit', _lazy('Send for Signature'), css_class='btn btn-primary me-2'),
                css_class='mt-4',
            ),
        )
