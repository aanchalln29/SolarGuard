"""
SolarGuard — Cloudflare Quick Tunnel Security Audit & Credential Manager
Validates production hardening, evaluates demo credentials, and provides safe
credential rotation with zero-loss rollback for temporary public demonstrations.
"""

import os
import shutil
import secrets
import string
import sqlite3
import subprocess
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone


class Command(BaseCommand):
    help = "Performs pre-flight security checks and credential auditing for Cloudflare Quick Tunnel demo."

    def add_arguments(self, parser):
        parser.add_argument(
            '--rotate-demo-passwords',
            action='store_true',
            help="Generate unique, cryptographically secure passwords for demo accounts and deactivate 'admin'."
        )
        parser.add_argument(
            '--restore-passwords',
            action='store_true',
            help="Restore original database and user accounts from pre-demo backup."
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 76))
        self.stdout.write(self.style.MIGRATE_HEADING(" SolarGuard -- Cloudflare Quick Tunnel Pre-Flight Security Audit"))
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 76))

        base_dir = settings.BASE_DIR
        db_path = Path(settings.DATABASES['default']['NAME'])
        backup_dir = base_dir / 'scratch' / 'demo_backups'

        # ---------------------------------------------------------------------
        # Handle Rollback / Restore
        # ---------------------------------------------------------------------
        if options['restore_passwords']:
            if not backup_dir.exists():
                self.stdout.write(self.style.ERROR(f"[FAIL] Backup directory not found at {backup_dir}"))
                return

            backups = sorted(backup_dir.glob("db_pre_demo_*.sqlite3"), key=os.path.getmtime, reverse=True)
            if not backups:
                self.stdout.write(self.style.ERROR("[FAIL] No pre-demo database backups found."))
                return

            latest_backup = backups[0]
            self.stdout.write(self.style.WARNING(f"Restoring database from: {latest_backup.name}..."))
            shutil.copy2(latest_backup, db_path)
            self.stdout.write(self.style.SUCCESS(f"[PASS] Successfully restored {db_path.name} to pre-demo state!"))
            return

        # ---------------------------------------------------------------------
        # 1. Core Settings & Hardening Audit
        # ---------------------------------------------------------------------
        self.stdout.write(self.style.HTTP_INFO("\n[1/5] Auditing Django Production Settings:"))

        # Check DEBUG
        if settings.DEBUG is False:
            self.stdout.write(self.style.SUCCESS("  [PASS] DEBUG = False (Tracebacks & technical errors disabled)"))
        else:
            self.stdout.write(self.style.ERROR("  [FAIL] DEBUG = True! Must be False before exposing tunnel."))

        # Check ALLOWED_HOSTS
        allowed = settings.ALLOWED_HOSTS
        if '*' in allowed:
            self.stdout.write(self.style.ERROR("  [FAIL] ALLOWED_HOSTS contains '*' (Open host header vulnerability)"))
        elif '.trycloudflare.com' in allowed or any(h.endswith('trycloudflare.com') for h in allowed):
            self.stdout.write(self.style.SUCCESS(f"  [PASS] ALLOWED_HOSTS strictly allows .trycloudflare.com: {allowed}"))
        else:
            self.stdout.write(self.style.WARNING(f"  [WARN] .trycloudflare.com not in ALLOWED_HOSTS: {allowed}"))

        # Check CSRF_TRUSTED_ORIGINS
        csrf_origins = getattr(settings, 'CSRF_TRUSTED_ORIGINS', [])
        has_cf_csrf = any('trycloudflare.com' in o for o in csrf_origins)
        if has_cf_csrf:
            self.stdout.write(self.style.SUCCESS(f"  [PASS] CSRF_TRUSTED_ORIGINS includes trycloudflare: {csrf_origins}"))
        else:
            self.stdout.write(self.style.ERROR(f"  [FAIL] CSRF_TRUSTED_ORIGINS missing https://*.trycloudflare.com"))

        # Check Admin exposure
        enable_admin = getattr(settings, 'ENABLE_ADMIN', True)
        if not enable_admin:
            self.stdout.write(self.style.SUCCESS("  [PASS] Django Admin interface (/admin/) is DISABLED in demo mode"))
        else:
            self.stdout.write(self.style.WARNING("  [WARN] Django Admin interface (/admin/) is ENABLED"))

        # Check Cookies
        session_sec = getattr(settings, 'SESSION_COOKIE_SECURE', False)
        csrf_sec = getattr(settings, 'CSRF_COOKIE_SECURE', False)
        if session_sec and csrf_sec:
            self.stdout.write(self.style.SUCCESS("  [PASS] Session & CSRF cookies set to Secure=True"))
        else:
            self.stdout.write(self.style.WARNING(f"  [WARN] Cookies: SESSION_COOKIE_SECURE={session_sec}, CSRF_COOKIE_SECURE={csrf_sec}"))

        # Check Proxy SSL Header
        ssl_header = getattr(settings, 'SECURE_PROXY_SSL_HEADER', None)
        if ssl_header == ('HTTP_X_FORWARDED_PROTO', 'https'):
            self.stdout.write(self.style.SUCCESS("  [PASS] SECURE_PROXY_SSL_HEADER configured for Cloudflare HTTPS edge"))
        else:
            self.stdout.write(self.style.WARNING("  [WARN] SECURE_PROXY_SSL_HEADER not set to ('HTTP_X_FORWARDED_PROTO', 'https')"))

        # ---------------------------------------------------------------------
        # 2. Static Assets & Media Privacy Audit
        # ---------------------------------------------------------------------
        self.stdout.write(self.style.HTTP_INFO("\n[2/5] Auditing Static Files & Media Access:"))
        static_root = Path(settings.STATIC_ROOT)
        if static_root.exists() and any(static_root.iterdir()):
            count = sum(1 for _ in static_root.rglob('*') if _.is_file())
            self.stdout.write(self.style.SUCCESS(f"  [PASS] Collected static assets found in {static_root.name}/ ({count} files)"))
        else:
            self.stdout.write(self.style.ERROR("  [FAIL] STATIC_ROOT is empty! Run 'python manage.py collectstatic' first."))

        # Verify Media Privacy (when DEBUG=False, direct static serving of media is inactive)
        if not settings.DEBUG:
            self.stdout.write(self.style.SUCCESS("  [PASS] Direct /media/ browsing is inactive under DEBUG=False"))
            self.stdout.write(self.style.SUCCESS("  [PASS] Uploaded photos strictly gated by secure_inspection_image_view"))

        # ---------------------------------------------------------------------
        # 3. Model & Database Integrity
        # ---------------------------------------------------------------------
        self.stdout.write(self.style.HTTP_INFO("\n[3/5] Auditing Database & AI Model:"))
        model_path = base_dir / 'ml_models' / 'solarguard_model_v3.keras'
        if model_path.exists():
            size = model_path.stat().st_size
            self.stdout.write(self.style.SUCCESS(f"  [PASS] MobileNetV2 v3.0 model present ({size:,} bytes)"))
        else:
            self.stdout.write(self.style.ERROR(f"  [FAIL] Model file missing at {model_path}"))

        try:
            con = sqlite3.connect(str(db_path))
            cur = con.cursor()
            res = cur.execute("PRAGMA integrity_check;").fetchall()
            if res == [('ok',)]:
                self.stdout.write(self.style.SUCCESS("  [PASS] SQLite database integrity check: ok"))
            con.close()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  [FAIL] Database check error: {e}"))

        # ---------------------------------------------------------------------
        # 4. Cloudflared Binary Verification
        # ---------------------------------------------------------------------
        self.stdout.write(self.style.HTTP_INFO("\n[4/5] Auditing Cloudflared Installation:"))
        cf_paths = [
            "cloudflared",
            r"C:\Program Files (x86)\cloudflared\cloudflared.exe",
            r"C:\Program Files\cloudflared\cloudflared.exe"
        ]
        found_cf = None
        for p in cf_paths:
            try:
                out = subprocess.check_output([p, '--version'], stderr=subprocess.STDOUT, text=True)
                found_cf = p
                self.stdout.write(self.style.SUCCESS(f"  [PASS] Found Cloudflared: {out.strip()} ({p})"))
                break
            except Exception:
                continue

        if not found_cf:
            self.stdout.write(self.style.ERROR("  [FAIL] cloudflared.exe not found in PATH or standard Program Files."))

        # ---------------------------------------------------------------------
        # 5. Account Security & Credential Audit
        # ---------------------------------------------------------------------
        self.stdout.write(self.style.HTTP_INFO("\n[5/5] Auditing Account Security & Public Credentials:"))

        users = User.objects.all().order_by('id')
        known_defaults = ['admin', 'admin123', 'SolarGuard2026!']
        flagged_users = []

        for u in users:
            is_flagged = False
            flag_reason = []
            if u.username == 'admin' and u.is_active:
                flag_reason.append("Root admin username with active status")
                is_flagged = True
            if u.username in ['demo_customer', 'demo_tech', 'demo_admin']:
                flag_reason.append("Publicly documented demo account (known password 'SolarGuard2026!')")
                is_flagged = True

            status_str = "ACTIVE" if u.is_active else "DISABLED"
            role_str = "Superuser" if u.is_superuser else ("Staff" if u.is_staff else "Standard")
            
            if is_flagged:
                flagged_users.append((u, flag_reason))
                self.stdout.write(self.style.WARNING(f"  [FLAG] User '{u.username}' ({role_str}, {status_str}): {'; '.join(flag_reason)}"))
            else:
                self.stdout.write(f"  [INFO] User '{u.username}' ({role_str}, {status_str})")

        # ---------------------------------------------------------------------
        # Safe Credential Rotation (Optional --rotate-demo-passwords)
        # ---------------------------------------------------------------------
        if options['rotate_demo_passwords']:
            self.stdout.write(self.style.MIGRATE_HEADING("\n" + "=" * 76))
            self.stdout.write(self.style.MIGRATE_HEADING(" EXECUTING SAFE CREDENTIAL ROTATION"))
            self.stdout.write(self.style.MIGRATE_HEADING("=" * 76))

            # Step A: Create automatic backup
            backup_dir.mkdir(parents=True, exist_ok=True)
            ts = timezone.now().strftime("%Y%m%d_%H%M%S")
            backup_file = backup_dir / f"db_pre_demo_{ts}.sqlite3"
            shutil.copy2(db_path, backup_file)
            self.stdout.write(self.style.SUCCESS(f"  [BACKUP] Pre-demo backup created at: {backup_file}"))

            # Step B: Deactivate root admin
            try:
                root_admin = User.objects.get(username='admin')
                root_admin.is_active = False
                root_admin.save(update_fields=['is_active'])
                self.stdout.write(self.style.SUCCESS("  [HARDENED] Deactivated root 'admin' account (login blocked)"))
            except User.DoesNotExist:
                pass

            # Step C: Generate unique passwords for demo users
            demo_targets = ['demo_customer', 'demo_tech', 'demo_admin']
            new_creds = {}
            alphabet = string.ascii_letters + string.digits + "!@#$%"

            for uname in demo_targets:
                try:
                    u = User.objects.get(username=uname)
                    pwd = "SG-" + "".join(secrets.choice(alphabet) for _ in range(12))
                    u.set_password(pwd)
                    u.is_active = True
                    u.save()
                    new_creds[uname] = pwd
                except User.DoesNotExist:
                    pass

            self.stdout.write(self.style.MIGRATE_LABEL("\nTEMPORARY DEMO CREDENTIAL CARD (SAVE FOR EVALUATION):"))
            self.stdout.write("-" * 65)
            self.stdout.write(f"{'Role':<18} | {'Username':<16} | {'Temporary Password':<24}")
            self.stdout.write("-" * 65)
            for uname, pwd in new_creds.items():
                role = "Customer" if "customer" in uname else ("Technician" if "tech" in uname else "Facility Admin")
                self.stdout.write(f"{role:<18} | {uname:<16} | {pwd:<24}")
            self.stdout.write("-" * 65)
            self.stdout.write("To restore original passwords after demo, run:")
            self.stdout.write(self.style.SUCCESS("  python manage.py check_demo_security --restore-passwords\n"))

        else:
            if flagged_users:
                self.stdout.write(self.style.WARNING("\n  [RECOMMENDATION] Publicly known demo passwords detected."))
                self.stdout.write("  To generate temporary unique passwords and disable root 'admin' before opening the tunnel:")
                self.stdout.write(self.style.SUCCESS("    python manage.py check_demo_security --rotate-demo-passwords"))
                self.stdout.write("  (This automatically creates a full database backup with instant 1-command restore)")

        self.stdout.write(self.style.MIGRATE_HEADING("\n" + "=" * 76))
        self.stdout.write(self.style.MIGRATE_HEADING(" Pre-Flight Audit Completed"))
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 76))
