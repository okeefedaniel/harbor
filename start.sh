#!/bin/bash
set -e

echo "=== Running migrations ==="
python manage.py migrate --noinput

echo "=== Collecting static files ==="
python manage.py collectstatic --noinput

echo "=== Starting gunicorn ==="
# Start gunicorn first so healthcheck passes, then run background tasks
gunicorn grantify.wsgi --bind 0.0.0.0:$PORT --workers 2 &
GUNICORN_PID=$!

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

# Wait for gunicorn to exit (keeps container running)
wait $GUNICORN_PID
