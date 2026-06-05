#!/usr/bin/env python
"""
Startup script for Railway deployment.
Replaces start.sh to ensure output is always visible.
"""
import os
import sys
import subprocess
import time

# Force unbuffered output
os.environ['PYTHONUNBUFFERED'] = '1'

def log(msg):
    print(f"[startup] {msg}", flush=True)

def run(cmd, fatal=False):
    """Run a command, streaming output. Returns True on success."""
    log(f"Running: {cmd}")
    try:
        result = subprocess.run(  # nosec B602 — internal boot script with hardcoded commands, no user input
            cmd, shell=True,
            stdout=sys.stdout, stderr=sys.stderr,
        )
        if result.returncode != 0:
            log(f"Command exited with code {result.returncode}: {cmd}")
            if fatal:
                sys.exit(result.returncode)
            return False
        return True
    except Exception as e:
        log(f"Command failed with exception: {e}")
        if fatal:
            sys.exit(1)
        return False

DEPLOY_VERSION = 'ae38328+'  # bumped each deploy to verify build cache

def main():
    log("=" * 50)
    log(f"Container starting  (version {DEPLOY_VERSION})")
    log("=" * 50)

    # Diagnostics
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'harbor.settings')
    settings_module = os.environ['DJANGO_SETTINGS_MODULE']
    port = os.environ.get('PORT', 'NOT SET')
    raw_db_url = os.environ.get('DATABASE_URL', '')
    if raw_db_url:
        # Show scheme + masked URL for debugging
        if '://' in raw_db_url:
            scheme = raw_db_url.split('://')[0]
            db_url = f"SET ({scheme}://******, len={len(raw_db_url)})"
        else:
            db_url = f"SET but NO SCHEME (first 30 chars: {repr(raw_db_url[:30])})"
    else:
        db_url = 'NOT SET (empty)'
    secret = 'SET' if os.environ.get('DJANGO_SECRET_KEY') else 'NOT SET'
    log(f"DJANGO_SETTINGS_MODULE = {settings_module}")
    log(f"PORT = {port}")
    log(f"DATABASE_URL = {db_url}")
    log(f"Secret key configured: {secret}")
    log(f"Python: {sys.executable} {sys.version}")
    log(f"CWD: {os.getcwd()}")
    log(f"PATH: {os.environ.get('PATH', 'NOT SET')}")

    log("=== Harbor Mode ===")
    manage_cmd = f"{sys.executable} manage.py"
    wsgi_module = "harbor.wsgi"

    # Test that Django settings can be imported
    log("Testing Django settings import...")
    setup_error = None
    try:
        import django
        django.setup()
        log("Django settings loaded successfully")
    except Exception as e:
        setup_error = str(e)
        log(f"ERROR: Django settings failed to load: {e}")
        import traceback
        traceback.print_exc(file=sys.stdout)
        sys.stdout.flush()

    # Run migrations BEFORE gunicorn — workers access the DB during
    # AppConfig.ready(), so tables (especially keel_accounts) must exist.
    # MUST be fatal: a failed migration silently followed by gunicorn
    # startup manifests as "deploy SUCCESS + every page 500s with
    # UndefinedTable" — exactly the harbor incident on 2026-04-22.
    # See keel/CLAUDE.md "Startup failures MUST be fatal."
    log("=== Running migrations ===")
    run(f"{manage_cmd} migrate --noinput", fatal=True)

    # Seed the canonical bootstrap superuser so SSO can link incoming
    # Keel OIDC claims to a local user. Without this, fresh deploys
    # 403/render the "signup closed" page on the first SSO callback
    # because the OIDC adapter has nothing to connect the social
    # account to. Idempotent — re-running is a no-op.
    log("=== Ensuring dokadmin user ===")
    run(f"{manage_cmd} ensure_dokadmin")

    # Sync keel.scheduling registry with declared @scheduled_job decorations.
    # Idempotent; preserves admin-edited enabled + notes fields.
    log("=== Syncing scheduled-job registry ===")
    run(f"{manage_cmd} sync_scheduled_jobs")

    # Ensure django.contrib.sites has the correct Site record (required by allauth)
    log("=== Configuring Site object ===")
    try:
        from django.contrib.sites.models import Site
        domain = os.environ.get('SITE_DOMAIN', 'harbor.docklabs.ai')
        name = 'Harbor'
        site, created = Site.objects.update_or_create(
            id=1,
            defaults={'domain': domain, 'name': name},
        )
        log(f"  Site {'created' if created else 'updated'}: {site.domain}")
    except Exception as e:
        log(f"  WARNING: Could not configure Site: {e}")

    # Collect static files (no DB needed, but required for WhiteNoise)
    log("=== Collecting static files ===")
    run(f"{manage_cmd} collectstatic --noinput", fatal=True)

    # Start gunicorn
    if port == 'NOT SET':
        port = '8080'
        log(f"WARNING: PORT not set, defaulting to {port}")

    gunicorn_cmd = (
        f"gunicorn {wsgi_module} "
        f"--bind 0.0.0.0:{port} "
        f"--workers 2 "
        f"--access-logfile - "
        f"--error-logfile - "
        f"--timeout 120"
    )
    log(f"=== Starting gunicorn on port {port} ===")
    gunicorn_proc = subprocess.Popen(  # nosec B602 — internal boot script with hardcoded commands, no user input
        gunicorn_cmd, shell=True,
        stdout=sys.stdout, stderr=sys.stderr,
    )
    log(f"Gunicorn started (PID {gunicorn_proc.pid})")

    # Wait a moment for gunicorn to bind
    time.sleep(3)

    # Check if gunicorn is still running
    if gunicorn_proc.poll() is not None:
        log(f"ERROR: Gunicorn exited with code {gunicorn_proc.returncode}")
        log("Trying to start a minimal health server instead...")
        # Start a minimal HTTP server so we can at least see logs
        from http.server import HTTPServer, BaseHTTPRequestHandler
        import json

        class HealthHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'status': 'error',
                    'message': 'Gunicorn failed to start. Check logs.',
                    'version': DEPLOY_VERSION,
                    'settings': settings_module,
                    'setup_error': setup_error,
                }).encode())

        server = HTTPServer(('0.0.0.0', int(port)), HealthHandler)
        log(f"Fallback health server listening on port {port}")
        server.serve_forever()
        return

    log("=== Running background startup tasks ===")
    if os.environ.get('SEED_ON_DEPLOY', '').lower() in ('true', '1', 'yes'):
        run(f"{manage_cmd} shell < seed_data.py")
    run(f"{manage_cmd} match_opportunities")

    # On demo deploys, personalize the seeded review / assignment / notification
    # rows for the cross-suite walkthrough persona (`agency_admin`) so Helm's
    # "Awaiting Me" column lights up with Harbor content. Idempotent — re-runs
    # are no-ops once everything is already assigned to the persona.
    if os.environ.get('DEMO_MODE', '').lower() in ('true', '1', 'yes'):
        log("=== Seeding demo inbox for agency_admin ===")
        run(f"{manage_cmd} seed_demo_inbox")

    log("=== Background tasks complete ===")

    log("=== Startup complete, waiting for gunicorn ===")
    gunicorn_proc.wait()
    log(f"Gunicorn exited with code {gunicorn_proc.returncode}")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        log(f"FATAL ERROR: {e}")
        import traceback
        traceback.print_exc(file=sys.stdout)
        sys.stdout.flush()
        # Keep container alive briefly so logs can be captured
        time.sleep(30)
        sys.exit(1)
