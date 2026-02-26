from django.utils import timezone


def site_context(request):
    """Inject site-wide template variables into every template context."""
    context = {
        'SITE_NAME': 'Grantify',
        'CURRENT_YEAR': timezone.now().year,
    }

    if hasattr(request, 'user') and request.user.is_authenticated:
        context['unread_notification_count'] = (
            request.user.notifications.filter(is_read=False).count()
        )

    return context
