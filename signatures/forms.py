from django import forms
from django.utils.translation import gettext_lazy as _

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Fieldset, Layout, Row, Column, Submit

from .models import SignatureDocument, SignatureFlow, SignatureFlowStep, SignatureRole, UserSignature


class SignatureFlowForm(forms.ModelForm):
    class Meta:
        model = SignatureFlow
        fields = ['name', 'description', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .compat import is_harbor
        # Include grant_program field only when the grants app is installed
        show_program = is_harbor() and hasattr(SignatureFlow, 'grant_program')
        layout_fields = ['name', 'description']
        if show_program:
            self.fields['grant_program'] = forms.ModelChoiceField(
                queryset=SignatureFlow.grant_program.field.related_model.objects.all(),
                required=False,
                label=_('Grant Program'),
                help_text=_('Link to a grant program (leave blank for standalone use).'),
            )
            if self.instance.pk and hasattr(self.instance, 'grant_program'):
                self.fields['grant_program'].initial = self.instance.grant_program
            layout_fields.append('grant_program')
        layout_fields.append('is_active')
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Fieldset(_('Signature Flow'), *layout_fields),
            Submit('submit', _('Save Flow'), css_class='btn-primary'),
        )


class FlowStepForm(forms.ModelForm):
    class Meta:
        model = SignatureFlowStep
        fields = ['order', 'label', 'assignment_type', 'assigned_user', 'assigned_role', 'is_required']
        widgets = {
            'order': forms.NumberInput(attrs={'min': 1}),
        }

    def __init__(self, *args, **kwargs):
        self.flow = kwargs.pop('flow', None)
        super().__init__(*args, **kwargs)
        # Filter assigned_user to staff / agency roles
        from .compat import get_assignable_users, get_role_choices
        self.fields['assigned_user'].queryset = get_assignable_users()
        self.fields['assigned_role'].widget = forms.Select(
            choices=get_role_choices(),
        )
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Fieldset(
                _('Signing Step'),
                Row(
                    Column('order', css_class='col-md-2'),
                    Column('label', css_class='col-md-10'),
                ),
                Row(
                    Column('assignment_type', css_class='col-md-4'),
                    Column('assigned_user', css_class='col-md-4'),
                    Column('assigned_role', css_class='col-md-4'),
                ),
                'is_required',
            ),
            Submit('submit', _('Save Step'), css_class='btn-primary'),
        )

    def clean(self):
        cleaned_data = super().clean()
        assignment_type = cleaned_data.get('assignment_type')
        if assignment_type == SignatureFlowStep.AssignmentType.USER:
            if not cleaned_data.get('assigned_user'):
                self.add_error('assigned_user', _('A user is required when assignment type is "Specific User".'))
        elif assignment_type == SignatureFlowStep.AssignmentType.ROLE:
            if not cleaned_data.get('assigned_role'):
                self.add_error('assigned_role', _('A role is required when assignment type is "Role".'))
        return cleaned_data


class SignatureDocumentForm(forms.ModelForm):
    class Meta:
        model = SignatureDocument
        fields = ['title', 'description', 'file']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.attrs = {'enctype': 'multipart/form-data'}
        self.helper.layout = Layout(
            Fieldset(
                _('Upload Document'),
                'title',
                'description',
                'file',
            ),
            Submit('submit', _('Upload'), css_class='btn-primary'),
        )

    def clean_file(self):
        f = self.cleaned_data.get('file')
        if f:
            if not f.name.lower().endswith('.pdf'):
                raise forms.ValidationError(_('Only PDF files are accepted.'))
            if f.content_type != 'application/pdf':
                raise forms.ValidationError(_('Only PDF files are accepted.'))
        return f


class PacketInitiateForm(forms.Form):
    """Dynamic form — renders one user selector per flow step."""

    title = forms.CharField(
        max_length=255,
        label=_('Packet Title'),
        help_text=_('Descriptive title for this signing session.'),
    )

    def __init__(self, *args, flow=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.flow = flow
        if flow:
            from django.contrib.auth import get_user_model
            from .compat import get_assignable_users

            User = get_user_model()
            staff_qs = get_assignable_users()

            for step in flow.steps.all():
                field_name = f'signer_{step.pk}'
                if step.assignment_type == SignatureFlowStep.AssignmentType.USER and step.assigned_user:
                    # Pre-assigned user — show as read-only
                    self.fields[field_name] = forms.ModelChoiceField(
                        queryset=User.objects.filter(pk=step.assigned_user_id),
                        initial=step.assigned_user,
                        label=f"Step {step.order}: {step.label}",
                        required=step.is_required,
                    )
                else:
                    # Role-based or unassigned — show dropdown
                    qs = staff_qs
                    if step.assigned_role and hasattr(qs.model, 'role'):
                        qs = qs.filter(role=step.assigned_role)
                    self.fields[field_name] = forms.ModelChoiceField(
                        queryset=qs,
                        label=f"Step {step.order}: {step.label}",
                        required=step.is_required,
                        help_text=_(
                            'Select the signer for this step (role: %(role)s).'
                        ) % {'role': step.get_role_display() if step.assigned_role else _('any staff')},
                    )

        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.add_input(Submit('submit', _('Start Signing'), css_class='btn-primary'))


class SigningForm(forms.Form):
    """Form for capturing a signature."""

    SIGNATURE_CHOICES = [
        ('typed', _('Type my name')),
        ('uploaded', _('Upload an image')),
        ('drawn', _('Draw my signature')),
    ]

    signature_type = forms.ChoiceField(
        choices=SIGNATURE_CHOICES,
        widget=forms.RadioSelect,
        label=_('Signature Method'),
    )
    typed_name = forms.CharField(
        max_length=255,
        required=False,
        label=_('Type your full name'),
    )
    signature_image = forms.FileField(
        required=False,
        label=_('Upload signature image'),
        help_text=_('PNG or JPG file of your signature.'),
    )
    drawn_data = forms.CharField(
        widget=forms.HiddenInput,
        required=False,
    )

    def clean(self):
        cleaned_data = super().clean()
        sig_type = cleaned_data.get('signature_type')
        if sig_type == 'typed' and not cleaned_data.get('typed_name'):
            self.add_error('typed_name', _('Please type your name.'))
        elif sig_type == 'uploaded' and not cleaned_data.get('signature_image'):
            self.add_error('signature_image', _('Please upload a signature image.'))
        elif sig_type == 'drawn' and not cleaned_data.get('drawn_data'):
            self.add_error('drawn_data', _('Please draw your signature.'))
        return cleaned_data


class UserSignatureForm(forms.ModelForm):
    class Meta:
        model = UserSignature
        fields = ['label', 'signature_type', 'typed_name', 'signature_image']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Default to "typed" so the form is immediately valid for submission
        if self.instance._state.adding:
            self.fields['signature_type'].initial = 'typed'
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            'label',
            'signature_type',
            'typed_name',
            'signature_image',
        )


class DeclineForm(forms.Form):
    """Form for declining to sign."""
    decline_reason = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        label=_('Reason for declining'),
        help_text=_('Please explain why you are declining to sign.'),
    )


class SignatureRoleForm(forms.ModelForm):
    class Meta:
        model = SignatureRole
        fields = ['key', 'label', 'description', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Fieldset(
                _('Signature Role'),
                Row(
                    Column('key', css_class='col-md-4'),
                    Column('label', css_class='col-md-8'),
                ),
                'description',
                'is_active',
            ),
            Submit('submit', _('Save Role'), css_class='btn-primary'),
        )
