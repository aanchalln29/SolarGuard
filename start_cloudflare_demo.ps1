# =============================================================================
# SolarGuard -- Cloudflare Quick Tunnel Demo Launcher
# Safe, repeatable setup for temporary public demonstration
# =============================================================================

[CmdletBinding()]
param (
    [switch]$RotatePasswords,
    [switch]$RestorePasswords
)

$ErrorActionPreference = "Stop"

# 1. Ensure Machine / User PATH are loaded for cloudflared
$machinePath = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
$userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
$env:Path = "$machinePath;$userPath"

# 2. Locate Virtual Environment Python
$ProjectRoot = $PSScriptRoot
$VenvPy = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPy)) {
    Write-Host "[ERROR] Virtual environment Python not found at: $VenvPy" -ForegroundColor Red
    Write-Host "Please create the virtual environment first."
    exit 1
}

# 3. Locate cloudflared binary
$CloudflaredBin = "cloudflared"
$standardPath = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
if (Test-Path $standardPath) {
    $CloudflaredBin = $standardPath
}

Write-Host "========================================================================" -ForegroundColor Cyan
Write-Host " SolarGuard -- Cloudflare Quick Tunnel Public Demo Setup" -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor Cyan

# 4. Handle Rollback if requested
if ($RestorePasswords) {
    Write-Host "Restoring database from pre-demo backup..." -ForegroundColor Yellow
    & $VenvPy manage.py check_demo_security --restore-passwords
    exit 0
}

# 5. Handle Credential Rotation if requested
if ($RotatePasswords) {
    Write-Host "Generating temporary unique demo passwords..." -ForegroundColor Yellow
    & $VenvPy manage.py check_demo_security --rotate-demo-passwords
} else {
    # Run pre-flight security audit
    $env:CLOUDFLARE_DEMO_MODE = "True"
    $env:DJANGO_SECRET_KEY = "sg-preflight-" + [Guid]::NewGuid().ToString("N") + [Guid]::NewGuid().ToString("N")
    & $VenvPy manage.py check_demo_security
    Remove-Item Env:CLOUDFLARE_DEMO_MODE -ErrorAction SilentlyContinue
    Remove-Item Env:DJANGO_SECRET_KEY -ErrorAction SilentlyContinue
}

Write-Host "`n------------------------------------------------------------------------" -ForegroundColor Cyan
Write-Host " TWO-STEP DEMO LAUNCH INSTRUCTIONS:" -ForegroundColor Cyan
Write-Host "------------------------------------------------------------------------"
Write-Host "STEP 1 (Terminal 1) -- Start Waitress Production WSGI Server:" -ForegroundColor Yellow
Write-Host "  & '$VenvPy' run_waitress.py`n" -ForegroundColor White

Write-Host "STEP 2 (Terminal 2) -- Start Cloudflare Quick Tunnel:" -ForegroundColor Yellow
Write-Host "  & '$CloudflaredBin' tunnel --url http://127.0.0.1:8000`n" -ForegroundColor White

Write-Host "STEP 3 -- Share the generated *.trycloudflare.com URL with evaluators." -ForegroundColor Green
Write-Host "Important: Direct /media/ and /admin/ are blocked for security."
Write-Host "When finished, press Ctrl+C in both terminals to stop." -ForegroundColor Gray
Write-Host "========================================================================`n" -ForegroundColor Cyan
