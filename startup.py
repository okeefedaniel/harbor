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
        result = subprocess.run(
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

def main():
    log("=" * 50)
    log("Container starting")
    log("=" * 50)

    # Diagnostics
    settings_module = os.environ.get('DJANGO_SETTINGS_MODULE', 'NOT SET')
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
    log(f"DJANGO_SECRET_KEY = {secret}")
    log(f"Python: {sys.executable} {sys.version}")
    log(f"CWD: {os.getcwd()}")
    log(f"PATH: {os.environ.get('PATH', 'NOT SET')}")

    # Detect mode
    if settings_module == 'signstreamer.settings':
        log("=== SignStreamer Mode ===")
        manage_cmd = f"{sys.executable} manage_signstreamer.py"
        wsgi_module = "signstreamer.wsgi"
    else:
        log("=== Grantify Mode ===")
        manage_cmd = f"{sys.executable} manage.py"
        wsgi_module = "grantify.wsgi"

    # Test that Django settings can be imported
    log("Testing Django settings import...")
    try:
        import django
        django.setup()
        log("Django settings loaded successfully")
    except Exception as e:
        log(f"ERROR: Django settings failed to load: {e}")
        import traceback
        traceback.print_exc(file=sys.stdout)
        sys.stdout.flush()

    # Collect static files (no DB needed, but required for WhiteNoise)
    log("=== Collecting static files ===")
    run(f"{manage_cmd} collectstatic --noinput")

    # Start gunicorn EARLY so healthcheck passes
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
    gunicorn_proc = subprocess.Popen(
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
                }).encode())

        server = HTTPServer(('0.0.0.0', int(port)), HealthHandler)
        log(f"Fallback health server listening on port {port}")
        server.serve_forever()
        return

    # Run migrations (gunicorn is already serving /health/)
    log("=== Running migrations ===")
    run(f"{manage_cmd} migrate --noinput")

    # Grantify-only background tasks
    if settings_module != 'signstreamer.settings':
        log("=== Running background startup tasks ===")
        run(f"{manage_cmd} shell < seed_data.py")
        run(f"{manage_cmd} sync_federal_grants --limit 10")
        run(f"{manage_cmd} match_opportunities")
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
