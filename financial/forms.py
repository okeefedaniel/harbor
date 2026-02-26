from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Div, Fieldset, Layout, Row, Submit
from django import forms
from django.utils.translation import gettext_lazy as _lazy

from .models import Budget, BudgetLineItem, DrawdownRequest, Transaction


class BudgetForm(forms.ModelForm):
    """Form for creating and editing budgets.

    The ``award``, ``approved_by``, ``approved_at``, and ``submitted_at``
    fields are set in the view.
    """

    class Meta:
        model = Budget
        fields = [
            'fiscal_year',
            'total_amount',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Fieldset(
                _lazy('Budget Information'),
                Row(
                    Column('fiscal_year', css_class='col-md-6'),
                    Column('total_amount', css_class='col-md-6'),
                ),
            ),
            Div(
                Submit('submit', _lazy('Save Budget'), css_class='btn btn-primary me-2'),
                css_class='mt-4',
            ),
        )


class BudgetLineItemForm(forms.ModelForm):
    """Form for creating and editing budget line items.

    The ``budget`` field is set in the view.
    """

    class Meta:
        model = BudgetLineItem
        fields = [
            'category',
            'description',
            'amount',
            'federal_share',
            'state_share',
            'match_share',
            'notes',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Fieldset(
                _lazy('Line Item Details'),
                Row(
                    Column('category', css_class='col-md-6'),
                    Column('amount', css_class='col-md-6'),
                ),
                'description',
                Row(
                    Column('federal_share', css_class='col-md-4'),
                    Column('state_share', css_class='col-md-4'),
                    Column('match_share', css_class='col-md-4'),
                ),
                'notes',
            ),
            Div(
                Submit('submit', _lazy('Save Line Item'), css_class='btn btn-primary me-2'),
                css_class='mt-4',
            ),
        )


class DrawdownRequestForm(forms.ModelForm):
    """Form for creating drawdown requests.

    The ``award``, ``submitted_by``, ``submitted_at``, ``reviewed_by``,
    ``reviewed_at``, ``paid_at``, ``payment_reference``, and ``request_number``
    fields are set in the view.
    """

    class Meta:
        model = DrawdownRequest
        fields = [
            'amount',
            'period_start',
            'period_end',
            'description',
        ]
        widgets = {
            'period_start': forms.DateInput(attrs={'type': 'date'}),
            'period_end': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Fieldset(
                _lazy('Drawdown Request'),
                'amount',
                Row(
                    Column('period_start', css_class='col-md-6'),
                    Column('period_end', css_class='col-md-6'),
                ),
                'description',
            ),
            Div(
                Submit('submit', _lazy('Submit Request'), css_class='btn btn-primary me-2'),
                css_class='mt-4',
            ),
        )


class TransactionForm(forms.ModelForm):
    """Form for creating financial transactions.

    The ``award`` and ``created_by`` fields are set in the view.
    """

    class Meta:
        model = Transaction
        fields = [
            'transaction_type',
            'amount',
            'transaction_date',
            'description',
            'reference_number',
            'core_ct_reference',
        ]
        widgets = {
            'transaction_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Fieldset(
                _lazy('Transaction Details'),
                Row(
                    Column('transaction_type', css_class='col-md-6'),
                    Column('amount', css_class='col-md-6'),
                ),
                'transaction_date',
                'description',
                Row(
                    Column('reference_number', css_class='col-md-6'),
                    Column('core_ct_reference', css_class='col-md-6'),
                ),
            ),
            Div(
                Submit('submit', _lazy('Record Transaction'), css_class='btn btn-primary me-2'),
                css_class='mt-4',
            ),
        )
