# =============================================================================
# SolarGuard -- Automated Local Team Environment Setup Script (PowerShell)
# Safe, idempotent setup for new collaborators and clean local environments.
# Compatible with Windows PowerShell 5.1 and PowerShell 7+.
# =============================================================================

[CmdletBinding()]
param(
    [string]$PythonPath = "",
    [switch]$SeedDemoData = $true,
    [switch]$NoDemoData,
    [switch]$SkipInstall,
    [switch]$RunServer
)

$ErrorActionPreference = "Stop"

Write-Host "========================================================================" -ForegroundColor DarkCyan
Write-Host " SolarGuard -- Automated Team Environment Setup" -ForegroundColor Cyan
Write-Host "========================================================================" -ForegroundColor DarkCyan

# -----------------------------------------------------------------------------
# Function: Find-CompatiblePython
# Locates a supported Python interpreter (Python 3.10 - 3.13), prioritizing 3.11
# even if a newer incompatible version (such as Python 3.14 or 3.15) is default.
# -----------------------------------------------------------------------------
function Find-CompatiblePython {
    param([string]$ExplicitPath)

    # 1. Check user-provided explicit path if supplied
    if ($ExplicitPath -and (Test-Path $ExplicitPath)) {
        $ver = & $ExplicitPath -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2>$null
        if ($ver) {
            $major, $minor = $ver.Split('.')[0..1]
            if ([int]$major -eq 3 -and [int]$minor -ge 10 -and [int]$minor -le 13) {
                return @{ Path = $ExplicitPath; Version = $ver }
            }
        }
    }

    # 2. Try Windows Python Launcher (py) prioritizing Python 3.11, then 3.12, 3.10, 3.13
    $PyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if ($PyLauncher) {
        foreach ($targetVer in @("-3.11", "-3.12", "-3.10", "-3.13")) {
            try {
                $verOut = & py.exe $targetVer -c "import sys; print(sys.executable + '|' + f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2>$null
                if ($LASTEXITCODE -eq 0 -and $verOut -and $verOut.Contains("|")) {
                    $parts = $verOut.Split('|')
                    if ($parts.Length -ge 2 -and (Test-Path $parts[0])) {
                        return @{ Path = $parts[0]; Version = $parts[1] }
                    }
                }
            } catch {
                # Continue searching next candidate version
            }
        }
    }

    # 3. Check well-known default installation directories
    $candidatePaths = @(
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "C:\Python311\python.exe",
        "C:\Program Files\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "C:\Python312\python.exe",
        "C:\Program Files\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
        "C:\Python310\python.exe",
        "C:\Program Files\Python310\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
        "C:\Python313\python.exe",
        "C:\Program Files\Python313\python.exe"
    )

    foreach ($cand in $candidatePaths) {
        if (Test-Path $cand) {
            $ver = & $cand -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2>$null
            if ($ver) {
                $major, $minor = $ver.Split('.')[0..1]
                if ([int]$major -eq 3 -and [int]$minor -ge 10 -and [int]$minor -le 13) {
                    return @{ Path = $cand; Version = $ver }
                }
            }
        }
    }

    # 4. Check system default 'python' on PATH
    $SysPython = Get-Command python -ErrorAction SilentlyContinue
    if ($SysPython) {
        $ver = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2>$null
        if ($ver) {
            $major, $minor = $ver.Split('.')[0..1]
            if ([int]$major -eq 3 -and [int]$minor -ge 10 -and [int]$minor -le 13) {
                return @{ Path = $SysPython.Source; Version = $ver }
            }
        }
    }

    return $null
}

# -----------------------------------------------------------------------------
# 1. Python Version Check & Selection
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "[Step 1/8] Locating Compatible Python Installation..." -ForegroundColor Yellow

$SelectedPythonInfo = Find-CompatiblePython -ExplicitPath $PythonPath

if (-not $SelectedPythonInfo) {
    Write-Error "No compatible Python version (3.10 - 3.13) was found. SolarGuard requires Python 3.10 - 3.13 (Python 3.11 recommended). Please install Python 3.11."
    exit 1
}

$SelectedPython = $SelectedPythonInfo.Path
$SelectedVer = $SelectedPythonInfo.Version

Write-Host "  Selected Python Interpreter: $SelectedPython" -ForegroundColor Green
Write-Host "  Python Version:              $SelectedVer" -ForegroundColor Green

# -----------------------------------------------------------------------------
# 2. Virtual Environment Setup (.venv)
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "[Step 2/8] Setting Up Virtual Environment (.venv)..." -ForegroundColor Yellow
$VenvDir = Join-Path $PSScriptRoot ".venv"
$VenvPy = Join-Path $VenvDir "Scripts\python.exe"

$recreateVenv = $false
if (Test-Path $VenvDir) {
    if (Test-Path $VenvPy) {
        $existingVer = & $VenvPy -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if ($existingVer) {
            $maj, $min = $existingVer.Split('.')[0..1]
            if ([int]$maj -eq 3 -and [int]$min -ge 10 -and [int]$min -le 13) {
                Write-Host "  [OK] Compatible virtual environment .venv found (Python $existingVer)." -ForegroundColor Green
            } else {
                Write-Warning "  Existing .venv uses incompatible Python $existingVer. Recreating with $SelectedVer..."
                $recreateVenv = $true
            }
        } else {
            $recreateVenv = $true
        }
    } else {
        $recreateVenv = $true
    }
} else {
    $recreateVenv = $true
}

if ($recreateVenv) {
    Write-Host "  Creating isolated virtual environment using $SelectedPython..." -ForegroundColor Gray
    & $SelectedPython -m venv $VenvDir
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $VenvPy)) {
        Write-Error "Failed to create virtual environment."
        exit 1
    }
    Write-Host "  [OK] Virtual environment created successfully." -ForegroundColor Green
}

# -----------------------------------------------------------------------------
# 3. Dependency Installation
# -----------------------------------------------------------------------------
if (-not $SkipInstall) {
    Write-Host ""
    Write-Host "[Step 3/8] Installing Dependencies from requirements.txt..." -ForegroundColor Yellow
    Write-Host "  Upgrading pip in virtual environment..." -ForegroundColor Gray
    & $VenvPy -m pip install --upgrade pip --quiet
    
    $reqFile = Join-Path $PSScriptRoot "requirements.txt"
    Write-Host "  Installing requirements (this may take a few moments)..." -ForegroundColor Gray
    & $VenvPy -m pip install -r $reqFile --quiet
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to install required Python packages."
        exit 1
    }
    Write-Host "  [OK] All dependencies verified and installed." -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "[Step 3/8] Skipping dependency installation (-SkipInstall specified)." -ForegroundColor Gray
}

# -----------------------------------------------------------------------------
# 4. Environment File (.env) Setup
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "[Step 4/8] Verifying Local Configuration (.env)..." -ForegroundColor Yellow
$EnvFile = Join-Path $PSScriptRoot ".env"
$EnvExample = Join-Path $PSScriptRoot ".env.example"

if (-not (Test-Path $EnvFile)) {
    if (Test-Path $EnvExample) {
        Write-Host "  Copying .env.example to .env..." -ForegroundColor Gray
        Copy-Item $EnvExample $EnvFile
        Write-Host "  [OK] Created local .env configuration file." -ForegroundColor Green
    } else {
        Write-Warning "  Neither .env nor .env.example was found. Relying on settings.py defaults."
    }
} else {
    Write-Host "  [OK] Local .env already exists." -ForegroundColor Green
}

# -----------------------------------------------------------------------------
# 5. Model Artifact & Integrity Verification
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "[Step 5/8] Verifying MobileNetV2 v3.0 Model Integrity..." -ForegroundColor Yellow
$ModelFile = Join-Path $PSScriptRoot "ml_models\solarguard_model_v3.keras"

if (-not (Test-Path $ModelFile)) {
    Write-Host "  [WARNING] Model file not found at: $ModelFile" -ForegroundColor Red
    Write-Host "  To enable real CNN inference:" -ForegroundColor Yellow
    Write-Host "  1. Pull the latest commits from GitHub main branch." -ForegroundColor Yellow
    Write-Host "  2. Confirm 'solarguard_model_v3.keras' is located in the ml_models/ folder." -ForegroundColor Yellow
    Write-Host "  3. Re-run: python manage.py verify_model" -ForegroundColor Yellow
} else {
    & $VenvPy manage.py verify_model
    if ($LASTEXITCODE -ne 0) {
        Write-Error "AI model verification failed."
        exit 1
    }
}

# -----------------------------------------------------------------------------
# 6. Database Migrations
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "[Step 6/8] Applying Database Migrations..." -ForegroundColor Yellow
& $VenvPy manage.py migrate
if ($LASTEXITCODE -ne 0) {
    Write-Error "Database migration failed."
    exit 1
}
Write-Host "  [OK] Database schema up to date." -ForegroundColor Green

# -----------------------------------------------------------------------------
# 7. Optional Demo Data Seeding
# -----------------------------------------------------------------------------
$shouldSeed = $SeedDemoData -and (-not $NoDemoData)
if ($shouldSeed) {
    Write-Host ""
    Write-Host "[Step 7/8] Seeding Local Idempotent Demo Data..." -ForegroundColor Yellow
    & $VenvPy manage.py seed_demo_data
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Demo data seeding encountered a warning."
    } else {
        Write-Host "  [OK] Demo accounts and sample array ready." -ForegroundColor Green
    }
} else {
    Write-Host ""
    Write-Host "  [Step 7/8] Skipping demo data seeding (-NoDemoData or -SeedDemoData:`$false specified)." -ForegroundColor Gray
}

# -----------------------------------------------------------------------------
# 8. Django System Check & Final Readiness
# -----------------------------------------------------------------------------
Write-Host ""
Write-Host "[Step 8/8] Performing Final Django System Check..." -ForegroundColor Yellow
& $VenvPy manage.py check
if ($LASTEXITCODE -ne 0) {
    Write-Error "Django system check failed."
    exit 1
}

Write-Host ""
Write-Host "========================================================================" -ForegroundColor DarkGreen
Write-Host " SolarGuard Setup Complete! Environment is Ready." -ForegroundColor Green
Write-Host "========================================================================" -ForegroundColor DarkGreen
Write-Host ""
Write-Host "Demo Credentials:" -ForegroundColor Cyan
Write-Host "  - Customer:   username 'demo_customer', password 'SolarGuard2026!'" -ForegroundColor Gray
Write-Host "  - Technician: username 'demo_tech',     password 'SolarGuard2026!'" -ForegroundColor Gray
Write-Host "  - Admin:      username 'demo_admin',    password 'SolarGuard2026!'" -ForegroundColor Gray
Write-Host ""
Write-Host "To start the development server:" -ForegroundColor Yellow
Write-Host "  .venv\Scripts\activate" -ForegroundColor White
Write-Host "  python manage.py runserver" -ForegroundColor White
Write-Host "  Open browser at: http://127.0.0.1:8000" -ForegroundColor White

if ($RunServer) {
    Write-Host ""
    Write-Host "Starting Django Development Server..." -ForegroundColor Cyan
    & $VenvPy manage.py runserver
}
