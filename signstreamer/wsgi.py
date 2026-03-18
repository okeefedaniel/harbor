"""WSGI config for Manifest standalone deployment."""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'signstreamer.settings')
application = get_wsgi_application()
