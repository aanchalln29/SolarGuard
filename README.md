# SolarGuard ☀️🛡️
### AI-Assisted Solar Asset Health, Inspection & Prioritized Maintenance Platform

SolarGuard is a comprehensive, production-grade Django web platform engineered for photovoltaic (PV) solar panel health monitoring, optical surface defect screening using MobileNetV2 CNN, 2D spatial array layout management, panel digital passports, and end-to-end maintenance work order lifecycles.

---

## 📑 Table of Contents
1. [Core Features](#-core-features)
2. [System Architecture](#-system-architecture)
3. [Quickstart Setup](#-quickstart-setup)
4. [AI Model Specifications (MobileNetV2 v3.0)](#-ai-model-specifications)
5. [User Roles & Permissions](#-user-roles--permissions)
6. [Team Collaboration Guide](#-team-collaboration-guide)
7. [Running Tests](#-running-tests)
8. [License & Context](#-license--context)

---

## 🌟 Core Features

- **Optical Condition Screening**: Fast 2D RGB photographic classification using a fine-tuned MobileNetV2 CNN (`Normal`, `Dusty`, `Bird-Dropping`, `Surface-Damage`).
- **Automated Maintenance Triage Engine**: Combines optical defect classification with panel operating age, historical cleaning frequency, and environmental stress to assign actionable maintenance priorities.
- **Interactive 2D Array Layout Builder**: Visually constructs and manages real-world rooftop arrays (supporting regular and irregular geometries like 4-3-4 configurations) with revision history and technician verification workflows.
- **Panel Digital Passport**: Complete chronological audit trail for every physical module tracking permanent hardware IDs, OEM serials, optical inspection records, and work order histories.
- **Role-Based Collaboration**: Strict security boundaries separating **Customers** (view own arrays, request service), **Field Technicians** (verify findings, execute work orders), and **Facility Administrators** (fleet overview, layout approval, technician allocation).
- **PDF Report Generation**: Server-rendered executive PDF reports for individual module passports, installation health audits, and compliance work order trails via ReportLab.

---

## 🧠 System Architecture

```text
                        [ Client / Drone RGB Image ]
                                      |
                                      v
                      [ Django Processing Pipeline ]
                                      |
                 +--------------------+--------------------+
                 |                                         |
                 v                                         v
   [ MobileNetV2 CNN v3.0 ]               [ Panel Digital Passport ]
   • Input: 224x224x3 RGB                 • Operating Age & Clean Date
   • Output: Softmax distribution         • Historical Service Events
   • Classes: Normal, Dusty,              • Physical Grid Coordinates
     Bird-Dropping, Surface-Damage                         |
                 |                                         |
                 +--------------------+--------------------+
                                      |
                                      v
                 [ Deterministic Triage Decision Engine ]
                 • Routine / Cleaning / Manual Inspection
                                      |
                                      v
                 [ Interactive SaaS Dashboard & Work Orders ]
                 • 2D Visual Layout Array Map
                 • Technician Verification Workflow
                 • Immutable PDF Audit Reports
```

---

## ⚡ Quickstart Setup

### Prerequisites
- Python 3.10 to 3.13 (verified on Python 3.13.2)
- Git 2.30+

### Option A: Automated One-Command Setup (Windows PowerShell)
```powershell
.\setup_team_env.ps1
```

### Option B: Manual Setup
```powershell
# 1. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # macOS / Linux

# 2. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 3. Configure environment
Copy-Item .env.example .env

# 4. Verify AI Model Integrity
python manage.py verify_model

# 5. Apply migrations and seed demo data
python manage.py migrate
python manage.py seed_demo_data

# 6. Start development server
python manage.py runserver
```

Open your browser at **`http://127.0.0.1:8000/`**.

---

## 🤖 AI Model Specifications

SolarGuard is powered by **MobileNetV2 CNN v3.0**:

- **Model Artifact**: `ml_models/solarguard_model_v3.keras` (9.25 MB)
- **SHA-256 Checksum**: `C7D54BA2507E2FD1E062CD446AC124EB4C897820402BB54D251B4B1BFA683CD6`
- **Architecture**: MobileNetV2 base with custom Dense classification head
- **Input Resolution**: `224 × 224 × 3` RGB
- **Input Preprocessing**: Built-in Rescaling `[-1.0, 1.0]`
- **Classes**: `[0: 'Bird-Dropping', 1: 'Dusty', 2: 'Normal', 3: 'Surface-Damage']`
- **Offline / Corrupt Tolerance**: If the model artifact is absent or fails to load, the system gracefully marks the inspection as `Inference Offline` and flags it for field technician review without crashing.

To verify your local model artifact at any time:
```powershell
python manage.py verify_model
```

---

## 👥 User Roles & Demo Credentials

When `python manage.py seed_demo_data` is run, three demo accounts are automatically prepared:

| Role | Username | Password | Key Capabilities |
| :--- | :--- | :--- | :--- |
| **Customer** | `demo_customer` | `SolarGuard2026!` | Manage own rooftop array, submit inspections, log service tickets |
| **Technician** | `demo_tech` | `SolarGuard2026!` | Review AI predictions, verify module layout drafts, resolve work orders |
| **Administrator** | `demo_admin` | `SolarGuard2026!` | Fleet dashboard, allocate technicians, approve layouts, download reports |

---

## 🤝 Team Collaboration Guide

For detailed branching, cloning, Pull Request, and database collaboration guidelines, please consult:
👉 **[TEAM_SETUP.md](TEAM_SETUP.md)**

### Key Git Branches:
- `main` — Production-stable code. Never push directly to `main`.
- `tanushree-dev` — Tanushree's feature branch.
- `teammate-dev` — Teammate's feature branch.

### Schema & Database Rules:
- **Never commit `db.sqlite3`**. Each developer uses their own local SQLite database.
- **Track all database changes via migrations**: `python manage.py makemigrations`.
- **Apply migrations on pull**: `python manage.py migrate`.

---

## 🧪 Running Tests

SolarGuard includes comprehensive unit, integration, and smoke test suites:

```powershell
# Run Django system checks
python manage.py check

# Verify migration consistency
python manage.py makemigrations --check --dry-run

# Run full core test suite
python manage.py test core.test_runtime_repair core.test_v3_smoke core.test_phase10_journey
```

---

## 📄 Project Context

SolarGuard was developed as a Software Engineering & Project Management (SEPM) semester capstone project, demonstrating real-world software architecture, AI model integration, and collaborative software delivery.
