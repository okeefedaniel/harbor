from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.utils.translation import gettext_lazy as _lazy

from .models import Agency, Organization

User = get_user_model()


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
class RegistrationForm(UserCreationForm):
    """Public registration form for new applicant users."""

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': _lazy('Email address'),
        }),
    )
    first_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _lazy('First name'),
        }),
    )
    last_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _lazy('Last name'),
        }),
    )
    phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _lazy('Phone number (optional)'),
        }),
    )
    organization = forms.ModelChoiceField(
        queryset=Organization.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text=_lazy('Select your organization, if applicable.'),
    )
    accepted_terms = forms.BooleanField(
        required=True,
        label=_lazy('I accept the Terms of Service and Privacy Policy'),
    )

    class Meta:
        model = User
        fields = (
            'username', 'email', 'first_name', 'last_name',
            'phone', 'organization',
            'password1', 'password2', 'accepted_terms',
        )
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': _lazy('Username'),
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': _lazy('Password'),
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': _lazy('Confirm password'),
        })

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.phone = self.cleaned_data.get('phone', '')
        user.organization = self.cleaned_data.get('organization')
        user.role = User.Role.APPLICANT
        user.is_state_user = False
        if self.cleaned_data.get('accepted_terms'):
            user.accepted_terms = True
            from django.utils import timezone
            user.accepted_terms_at = timezone.now()
        if commit:
            user.save()
        return user


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
class LoginForm(AuthenticationForm):
    """Styled login form."""

    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': _lazy('Username'),
            'autofocus': True,
        }),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': _lazy('Password'),
        }),
    )


# ---------------------------------------------------------------------------
# Organization
# ---------------------------------------------------------------------------
class OrganizationForm(forms.ModelForm):
    """Form for creating or updating an Organization."""

    class Meta:
        model = Organization
        fields = (
            'name', 'org_type',
            'duns_number', 'uei_number', 'ein',
            'sam_registered', 'sam_expiration',
            'address_line1', 'address_line2', 'city', 'state', 'zip_code',
            'phone', 'website',
            'notes',
        )
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'org_type': forms.Select(attrs={'class': 'form-select'}),
            'duns_number': forms.TextInput(attrs={'class': 'form-control'}),
            'uei_number': forms.TextInput(attrs={'class': 'form-control'}),
            'ein': forms.TextInput(attrs={'class': 'form-control'}),
            'sam_expiration': forms.DateInput(attrs={
                'class': 'form-control', 'type': 'date',
            }),
            'address_line1': forms.TextInput(attrs={'class': 'form-control'}),
            'address_line2': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'state': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '2'}),
            'zip_code': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'website': forms.URLInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------
class ProfileForm(forms.ModelForm):
    """Form for editing the authenticated user's profile."""

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'title', 'phone')
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
        }


# ---------------------------------------------------------------------------
# User Role Management (System Admin only)
# ---------------------------------------------------------------------------
class UserRoleForm(forms.ModelForm):
    """Form for system admins to update a user's role, agency, and flags."""

    class Meta:
        model = User
        fields = ('role', 'agency', 'is_state_user', 'is_active')
        widgets = {
            'role': forms.Select(attrs={'class': 'form-select'}),
            'agency': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'role': _lazy('Role'),
            'agency': _lazy('Agency'),
            'is_state_user': _lazy('State Employee'),
            'is_active': _lazy('Account Active'),
        }
        help_texts = {
            'role': _lazy('Select the user\'s role in the system.'),
            'agency': _lazy('Assign to an agency (required for agency staff roles).'),
            'is_state_user': _lazy('Designates whether this user is a CT state employee.'),
            'is_active': _lazy('Uncheck to deactivate the user\'s account.'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['agency'].queryset = Agency.objects.filter(
            is_active=True
        ).order_by('name')
        self.fields['agency'].required = False
