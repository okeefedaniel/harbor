"""ASGI config for Manifest standalone deployment."""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'signstreamer.settings')
application = get_asgi_application()
