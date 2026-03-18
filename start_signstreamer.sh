#!/bin/bash
set -e

echo "=== Running Manifest migrations ==="
python manage_signstreamer.py migrate --noinput

echo "=== Collecting static files ==="
python manage_signstreamer.py collectstatic --noinput

echo "=== Starting gunicorn (Manifest) ==="
gunicorn signstreamer.wsgi --bind 0.0.0.0:$PORT --workers 2
