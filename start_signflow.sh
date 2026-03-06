#!/bin/bash
set -e

echo "=== Running SignFlow migrations ==="
python manage_signflow.py migrate --noinput

echo "=== Collecting static files ==="
python manage_signflow.py collectstatic --noinput

echo "=== Starting gunicorn (SignFlow) ==="
gunicorn signflow.wsgi --bind 0.0.0.0:$PORT --workers 2
