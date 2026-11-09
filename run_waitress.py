"""
SolarGuard — Windows Production WSGI Server Runner (Waitress)
Serves SolarGuard on 127.0.0.1:8000 using Waitress multi-threaded WSGI server.
Optimized for safe reverse-proxying behind Cloudflare Quick Tunnel.
"""

import os
import sys
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Enforce Cloudflare demo production hardening
os.environ.setdefault('CLOUDFLARE_DEMO_MODE', 'True')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'solarguard_project.settings')

# Auto-generate cryptographically secure 50-character SECRET_KEY if not provided
if not os.environ.get('DJANGO_SECRET_KEY'):
    ephemeral_key = "sg-demo-" + secrets.token_urlsafe(40)
    os.environ['DJANGO_SECRET_KEY'] = ephemeral_key

# Verify static files exist
static_root = BASE_DIR / 'staticfiles'
if not static_root.exists() or not any(static_root.iterdir()):
    print("[WARNING] STATIC_ROOT (staticfiles/) is empty. Running collectstatic...")
    import django
    from django.core.management import call_command
    django.setup()
    call_command('collectstatic', interactive=False)

try:
    import waitress
except ImportError:
    print("[ERROR] Waitress is not installed. Run: pip install waitress")
    sys.exit(1)

import django
django.setup()
from solarguard_project.wsgi import application

HOST = os.environ.get('WAITRESS_HOST', '127.0.0.1')
PORT = int(os.environ.get('WAITRESS_PORT', '8000'))
THREADS = int(os.environ.get('WAITRESS_THREADS', '4'))
TIMEOUT = int(os.environ.get('WAITRESS_TIMEOUT', '120'))

print("=" * 72)
print(" SolarGuard — Waitress Production WSGI Server")
print("=" * 72)
print(f" Binding:          http://{HOST}:{PORT}/")
print(f" Concurrency:      {THREADS} worker threads")
print(f" Channel Timeout:  {TIMEOUT}s")
print(f" Cloudflare Mode:  {os.environ.get('CLOUDFLARE_DEMO_MODE')}")
print(f" Admin (/admin/):  Disabled by default for security")
print(" Press Ctrl+C to terminate server.")
print("=" * 72)

waitress.serve(
    application,
    host=HOST,
    port=PORT,
    threads=THREADS,
    channel_timeout=TIMEOUT,
    ident='SolarGuard-Waitress'
)
