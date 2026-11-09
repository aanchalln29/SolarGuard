# SolarGuard — Cloudflare Quick Tunnel Demo Guide

This guide details how to securely host a temporary live demonstration of **SolarGuard** over the internet using **Cloudflare Quick Tunnel** on Windows, with `DEBUG=False` and **Waitress WSGI**.

---

## 1. Security Architecture & Threat Mitigation

| Security Aspect | Local Development | Cloudflare Public Demo Mode | Benefit / Protection |
| :--- | :--- | :--- | :--- |
| **DEBUG Mode** | `DEBUG = True` | **`DEBUG = False`** | Prevents technical stack traces, environment variables, or SQL queries from being exposed on error. |
| **WSGI Server** | `runserver` (single-threaded dev server) | **Waitress WSGI (`threads=4`)** | Multi-threaded, production-grade WSGI server for Windows; avoids request hanging during CNN inference. |
| **ALLOWED_HOSTS** | `['127.0.0.1', 'localhost', '*']` | **`['127.0.0.1', 'localhost', '.trycloudflare.com']`** | **Strict subdomain pattern matching**. Blocks arbitrary Host headers; **wildcard `*` is forbidden**. |
| **CSRF Origins** | Localhost only | **`https://*.trycloudflare.com`** | Enables forms, logins, inspections, and file uploads across the ephemeral HTTPS tunnel without CSRF 403 blocks. |
| **Cookies** | Standard HTTP | **`SESSION_COOKIE_SECURE = True`, `CSRF_COOKIE_SECURE = True`** | Ensures browser session and CSRF tokens are only transmitted over the encrypted HTTPS tunnel. |
| **Proxy SSL** | None | **`('HTTP_X_FORWARDED_PROTO', 'https')`** | Django recognizes that Cloudflare has terminated SSL at the edge, properly handling `request.is_secure()`. |
| **Media Privacy** | Unrestricted local static serve | **Direct `/media/` browsing returns 404** | All inspection and maintenance photos are served exclusively through object-level authorized streaming views (`/inspect/result/<id>/image/`). |
| **Django Admin** | Available at `/admin/` | **`/admin/` returns 404 (Disabled)** | Prevents external visitors from accessing or brute-forcing the Django administration portal. |
| **Static Assets** | Django static view | **WhiteNoise Storage** | High-performance cached serving of compressed CSS, JS, fonts, and SVGs from `staticfiles/`. |

> [!IMPORTANT]
> **Cloudflare Quick Tunnel Access Model:**
> Cloudflare Quick Tunnel creates an ephemeral public HTTPS link (`https://<random-name>.trycloudflare.com`) that routes to your local machine. It does **not** provide built-in email or identity access lists (the `--allowed-mail` flag only applies to persistent Cloudflare Zero Trust Access tunnels, not Quick Tunnels). Protection is achieved through SolarGuard's internal Django role-based access control (RBAC), disabled admin routes, private media streaming, and unique demo passwords.

---

## 2. Public Credential Audit & Safety Options

Our pre-flight audit detected 4 accounts with publicly known or default credentials:
1. `admin` (Default superuser)
2. `demo_admin` (Password: `SolarGuard2026!`)
3. `demo_tech` (Password: `SolarGuard2026!`)
4. `demo_customer` (Password: `SolarGuard2026!`)

### Safe Credential Rotation (Recommended)
Before opening the public tunnel, you can rotate the demo accounts to unique 16-character passwords and deactivate the root `admin` account:
```powershell
.\start_cloudflare_demo.ps1 -RotatePasswords
```
- Automatically creates a timestamped backup: `scratch/demo_backups/db_pre_demo_<timestamp>.sqlite3`.
- Deactivates root `admin` so brute-force attempts fail immediately.
- Sets temporary passwords for `demo_customer`, `demo_tech`, and `demo_admin`.
- Displays a clean credentials card to present to evaluators.

### 1-Click Rollback After Presentation
To instantly restore your original database and passwords:
```powershell
.\start_cloudflare_demo.ps1 -RestorePasswords
```

---

## 3. Step-by-Step Live Demo Launch

### Step 1: Pre-Flight Audit
Run the automated pre-flight security check in PowerShell:
```powershell
.\start_cloudflare_demo.ps1
```
Verify that all 5 audit stages show `[PASS]`.

---

### Step 2: Start Waitress Production WSGI Server (Terminal 1)
In your first PowerShell terminal, run:
```powershell
& ".\.venv\Scripts\python.exe" run_waitress.py
```
Expected output:
```text
========================================================================
 SolarGuard — Waitress Production WSGI Server
========================================================================
 Binding:          http://127.0.0.1:8000/
 Concurrency:      4 worker threads
 Channel Timeout:  120s
 Cloudflare Mode:  True
 Admin (/admin/):  Disabled by default for security
 Press Ctrl+C to terminate server.
========================================================================
```

---

### Step 3: Start Cloudflare Quick Tunnel (Terminal 2)
In a **second PowerShell terminal**, launch Cloudflare Quick Tunnel:
```powershell
& "C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url http://127.0.0.1:8000
```
Within a few seconds, Cloudflare will display your live public HTTPS URL:
```text
+--------------------------------------------------------------------------------------------+
|  Your quick Tunnel has been created! Visit it at (it may take some time to be reachable):  |
|  https://your-temporary-name.trycloudflare.com                                             |
+--------------------------------------------------------------------------------------------+
```

---

## 4. Evaluator Presentation Flow

Share `https://your-temporary-name.trycloudflare.com` with your evaluators or open it on a mobile device:

1. **Customer View:** Log in as `demo_customer`. Showcase the interactive 11-panel solar array (4-3-4 grid) with real-time module health status.
2. **Technician Inspection & Live Inference:**
   - Log in as `demo_tech` -> Navigate to **Inspect Panel**.
   - Upload sample photo: `media/sample_test_images/sample_bird_drop.jpg`.
   - Submit inspection: MobileNetV2 v3.0 performs CNN inference in ~150 ms and predicts `Surface-Damage` (59.6% confidence).
   - Show automatic generation of maintenance ticket #10.
3. **Security & Privacy Proof:**
   - Attempt to access `https://<tunnel>.trycloudflare.com/admin/` -> Returns **HTTP 404** (Admin route completely unmounted).
   - Attempt to open raw image URL `https://<tunnel>.trycloudflare.com/media/...` -> Returns **HTTP 404** (Direct media browsing inactive).
   - View photo inside authorized inspection view: loaded securely via authorized streaming.
4. **Reports Hub:** Log in as `demo_admin` -> Go to **Reports** -> Download the PDF inspection report generated on the fly.

---

## 5. Teardown & Return to Local Development Mode

When your college presentation is complete:

1. **Stop the Tunnel:** In Terminal 2, press `Ctrl + C`. The public URL is immediately deactivated.
2. **Stop Waitress:** In Terminal 1, press `Ctrl + C`.
3. **Restore Original Accounts & Passwords (if rotated):**
   ```powershell
   .\start_cloudflare_demo.ps1 -RestorePasswords
   ```
4. **Return to Local Development:**
   Simply run your regular development server:
   ```powershell
   python manage.py runserver
   ```
   SolarGuard will automatically start in local development mode (`DEBUG=True`, `/admin/` enabled).
