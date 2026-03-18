"""
Custom allauth adapters for Microsoft Entra ID (Azure AD) SSO integration.

Handles:
- Auto-creating users from Microsoft SSO with correct roles
- Mapping Azure AD group claims to Harbor roles
- Marking SSO users as state employees
- Linking SSO users to their agency based on email domain
"""
import logging

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)

User = get_user_model()

# Map Microsoft group names or email domains to Harbor roles.
# Extend this as your Azure AD configuration grows.
ROLE_DOMAIN_MAP = {
    # State agency email domains → default role for new SSO users
    'dok.gov': User.Role.PROGRAM_OFFICER,
    'state.dok.us': User.Role.PROGRAM_OFFICER,
}


class HarborAccountAdapter(DefaultAccountAdapter):
    """Custom account adapter.

    - Ensures the login redirect goes to /dashboard/
    - Keeps standard (non-SSO) registration working for applicants
    """

    def get_login_redirect_url(self, request):
        return '/dashboard/'

    def get_signup_redirect_url(self, request):
        return '/dashboard/'


class HarborSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Custom social account adapter for Microsoft SSO.

    When a user signs in via Microsoft for the first time, this adapter
    populates their Harbor profile from the Microsoft token data.
    """

    def pre_social_login(self, request, sociallogin):
        """If an existing user has the same email, auto-link the social account."""
        if sociallogin.is_existing:
            return

        email = (sociallogin.account.extra_data.get('mail')
                 or sociallogin.account.extra_data.get('userPrincipalName', ''))

        if not email:
            return

        try:
            user = User.objects.get(email__iexact=email)
            sociallogin.connect(request, user)
            logger.info('SSO: Linked Microsoft account to existing user %s', user.username)
        except User.DoesNotExist:
            pass

    def populate_user(self, request, sociallogin, data):
        """Fill in user fields from Microsoft profile data."""
        user = super().populate_user(request, sociallogin, data)

        extra = sociallogin.account.extra_data
        email = data.get('email') or extra.get('mail') or extra.get('userPrincipalName', '')

        user.email = email
        user.first_name = data.get('first_name') or extra.get('givenName', '')
        user.last_name = data.get('last_name') or extra.get('surname', '')

        if not user.username and email:
            # Use email prefix as username, ensuring uniqueness
            base = email.split('@')[0].lower().replace('.', '_')
            username = base
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f'{base}_{counter}'
                counter += 1
            user.username = username

        # Determine role based on email domain
        domain = email.split('@')[-1].lower() if '@' in email else ''
        if domain in ROLE_DOMAIN_MAP:
            user.role = ROLE_DOMAIN_MAP[domain]
            user.is_state_user = True
        else:
            user.role = User.Role.APPLICANT
            user.is_state_user = False

        # Mark terms as accepted for SSO users (implied by org SSO policy)
        user.accepted_terms = True

        # Try to link to agency based on email domain
        if user.is_state_user:
            from core.models import Agency
            # Attempt to match the user's domain prefix to an agency abbreviation
            domain_prefix = domain.split('.')[0].upper()
            agency = Agency.objects.filter(
                abbreviation__iexact=domain_prefix,
                is_active=True,
            ).first()
            if agency:
                user.agency = agency
                logger.info(
                    'SSO: Auto-linked user %s to agency %s',
                    email, agency.abbreviation,
                )

        logger.info(
            'SSO: Populated new user from Microsoft — email=%s, role=%s, state=%s',
            email, user.role, user.is_state_user,
        )

        return user

    def save_user(self, request, sociallogin, form=None):
        """Save the user and set the accepted_terms timestamp."""
        user = super().save_user(request, sociallogin, form)

        if user.accepted_terms and not user.accepted_terms_at:
            from django.utils import timezone
            user.accepted_terms_at = timezone.now()
            user.save(update_fields=['accepted_terms_at'])

        return user
