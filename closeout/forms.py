from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Div, Fieldset, Layout, Row, Submit
from django import forms
from django.utils.translation import gettext_lazy as _lazy

from .models import CloseoutChecklist, CloseoutDocument, FundReturn


class CloseoutChecklistForm(forms.ModelForm):
    """Form for updating a closeout checklist item.

    The ``closeout``, ``completed_by``, and ``completed_at`` fields are
    set in the view.
    """

    class Meta:
        model = CloseoutChecklist
        fields = [
            'is_completed',
            'notes',
        ]
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Fieldset(
                _lazy('Checklist Item'),
                'is_completed',
                'notes',
            ),
            Div(
                Submit('submit', _lazy('Update'), css_class='btn btn-primary me-2'),
                css_class='mt-4',
            ),
        )


class CloseoutDocumentForm(forms.ModelForm):
    """Form for uploading a closeout document.

    The ``closeout`` and ``uploaded_by`` fields are set in the view.
    """

    class Meta:
        model = CloseoutDocument
        fields = [
            'title',
            'document_type',
            'file',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Fieldset(
                _lazy('Document Details'),
                'title',
                'document_type',
                'file',
            ),
            Div(
                Submit('submit', _lazy('Upload Document'), css_class='btn btn-primary me-2'),
                css_class='mt-4',
            ),
        )


class FundReturnForm(forms.ModelForm):
    """Form for recording a fund return during closeout.

    The ``closeout``, ``processed_at``, and ``processed_by`` fields are
    set in the view.
    """

    class Meta:
        model = FundReturn
        fields = [
            'amount',
            'reason',
        ]
        widgets = {
            'reason': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Fieldset(
                _lazy('Fund Return Details'),
                'amount',
                'reason',
            ),
            Div(
                Submit('submit', _lazy('Record Fund Return'), css_class='btn btn-primary me-2'),
                css_class='mt-4',
            ),
        )
