"""ASGI config for SignFlow standalone deployment."""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'signflow.settings')
application = get_asgi_application()
