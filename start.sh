#!/bin/bash
set -e

# Detect standalone SignStreamer mode vs Grantify mode
if [ "$DJANGO_SETTINGS_MODULE" = "signstreamer.settings" ]; then
    echo "=== SignStreamer Mode ==="
    MANAGE_CMD="python manage_signstreamer.py"
    WSGI_MODULE="signstreamer.wsgi"
else
    echo "=== Grantify Mode ==="
    MANAGE_CMD="python manage.py"
    WSGI_MODULE="grantify.wsgi"
fi

echo "=== Running migrations ==="
$MANAGE_CMD migrate --noinput

echo "=== Collecting static files ==="
$MANAGE_CMD collectstatic --noinput

echo "=== Starting gunicorn ==="
# Start gunicorn first so healthcheck passes, then run background tasks
gunicorn $WSGI_MODULE --bind 0.0.0.0:$PORT --workers 2 &
GUNICORN_PID=$!

# Grantify-only background tasks (skip in SignStreamer mode)
if [ "$DJANGO_SETTINGS_MODULE" != "signstreamer.settings" ]; then
    # Wait for gunicorn to be ready
    echo "=== Waiting for gunicorn to start ==="
    sleep 5

    echo "=== Running background startup tasks ==="
    (
        echo "--- Seeding demo data ---"
        python manage.py shell < seed_data.py || echo "WARNING: Seed data failed (non-fatal)"

        echo "--- Syncing federal grants ---"
        python manage.py sync_federal_grants --limit 10 || echo "WARNING: Federal grants sync failed (non-fatal)"

        echo "--- Running AI grant matching ---"
        python manage.py match_opportunities || echo "WARNING: Grant matching failed (non-fatal)"

        echo "=== Background tasks complete ==="
    ) &
fi

# Wait for gunicorn to exit (keeps container running)
wait $GUNICORN_PID
