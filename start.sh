#!/bin/bash
export PYTHONUNBUFFERED=1

echo "========================================"
echo "=== Container starting at $(date) ==="
echo "========================================"
echo "DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE"
echo "PORT=$PORT"
echo "DATABASE_URL is $([ -n "$DATABASE_URL" ] && echo 'SET' || echo 'NOT SET')"

# Detect standalone Manifest mode vs Harbor mode
if [ "$DJANGO_SETTINGS_MODULE" = "signstreamer.settings" ]; then
    echo "=== Manifest Mode ==="
    MANAGE_CMD="python manage_signstreamer.py"
    WSGI_MODULE="signstreamer.wsgi"
else
    echo "=== Harbor Mode ==="
    MANAGE_CMD="python manage.py"
    WSGI_MODULE="harbor.wsgi"
fi

# Collect static files FIRST (no DB needed, but required before gunicorn
# starts because WhiteNoise needs the manifest)
echo "=== Collecting static files ==="
$MANAGE_CMD collectstatic --noinput 2>&1 || echo "WARNING: collectstatic failed (non-fatal)"

# Start gunicorn EARLY so Railway healthcheck passes while migrations run
echo "=== Starting gunicorn ==="
gunicorn $WSGI_MODULE --bind 0.0.0.0:$PORT --workers 2 --access-logfile - --error-logfile - &
GUNICORN_PID=$!

# Give gunicorn a moment to bind the port
sleep 2

# Now run migrations (gunicorn is already serving /health/)
echo "=== Running migrations ==="
$MANAGE_CMD migrate --noinput 2>&1 || echo "ERROR: Migrations failed — see output above"

# Harbor-only background tasks (skip in Manifest mode)
if [ "$DJANGO_SETTINGS_MODULE" != "signstreamer.settings" ]; then
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

echo "=== Startup complete, waiting for gunicorn (PID $GUNICORN_PID) ==="

# Wait for gunicorn to exit (keeps container running)
wait $GUNICORN_PID
