from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Div, Fieldset, Layout, Row, Submit
from django import forms
from django.utils.translation import gettext_lazy as _lazy

from .models import Report


class ReportForm(forms.ModelForm):
    """Form for creating and editing reports.

    The ``award``, ``submitted_by``, ``submitted_at``, ``reviewed_by``,
    ``reviewed_at``, ``reviewer_comments``, and ``status`` fields are set
    in the view.
    """

    class Meta:
        model = Report
        fields = [
            'template',
            'report_type',
            'reporting_period_start',
            'reporting_period_end',
            'due_date',
            'data',
        ]
        widgets = {
            'reporting_period_start': forms.DateInput(attrs={'type': 'date'}),
            'reporting_period_end': forms.DateInput(attrs={'type': 'date'}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'data': forms.Textarea(attrs={'rows': 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Fieldset(
                _lazy('Report Information'),
                Row(
                    Column('report_type', css_class='col-md-6'),
                    Column('template', css_class='col-md-6'),
                ),
                Row(
                    Column('reporting_period_start', css_class='col-md-4'),
                    Column('reporting_period_end', css_class='col-md-4'),
                    Column('due_date', css_class='col-md-4'),
                ),
            ),
            Fieldset(
                _lazy('Report Data'),
                'data',
            ),
            Div(
                Submit('submit', _lazy('Save Report'), css_class='btn btn-primary me-2'),
                css_class='mt-4',
            ),
        )
