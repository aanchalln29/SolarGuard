# SolarGuard — Team Collaboration & Onboarding Guide

Welcome to the **SolarGuard** developer team! This guide provides the complete, step-by-step instructions for cloning, setting up, verifying, and collaborating on SolarGuard in a two-developer team environment.

Both developers have **FULL access** to all components:
- Frontend (Templates, CSS, JavaScript)
- Backend (Django views, models, permissions, services)
- Database schema & migrations
- AI Model (MobileNetV2 CNN v3.0 optical inference)
- Panel Layout Builder (2D irregular grid coordinate engine)
- Inspection & Maintenance Work Order Lifecycles
- PDF Report Generation

---

## 1. Prerequisites

Before starting, ensure your system has:
- **Git** (version 2.30 or newer): `git --version`
- **Python** (version 3.10 to 3.13): `python --version` (tested on Python 3.13.2)
- **PowerShell** (Windows) or **Bash** (macOS / Linux)
- A code editor such as **VS Code**

---

## 2. Cloning the Repository

Clone the private repository from GitHub into your local workspace:

```powershell
# Clone the repository
git clone https://github.com/tanushreeburde/SolarGuard.git "SolarGuard"

# Enter the project directory
cd SolarGuard
```

Verify you are on the `main` branch:
```powershell
git branch -a
git status
```

---

## 3. Environment Setup (Choose Option A or Option B)

### Option A: Automated One-Command Setup (Recommended for Windows)

Run the included automated setup script in PowerShell:

```powershell
.\setup_team_env.ps1
```

The script automatically:
1. Validates Python version compatibility.
2. Creates an isolated virtual environment (`.venv`).
3. Installs all required packages from `requirements.txt`.
4. Copies `.env.example` to `.env`.
5. Verifies the MobileNetV2 v3.0 model hash and test inference.
6. Applies Django migrations to your local `db.sqlite3`.
7. Seeds idempotent demo accounts and a verified sample array.
8. Runs Django system integrity checks.

---

### Option B: Manual Step-by-Step Setup

If you prefer manual setup or are on macOS/Linux:

#### Step 1: Create and Activate Virtual Environment
```powershell
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

#### Step 2: Install Dependencies
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

#### Step 3: Configure Environment Variables
```powershell
# Copy the template
Copy-Item .env.example .env    # Windows PowerShell
# cp .env.example .env          # Linux / macOS
```

#### Step 4: Verify or Place the AI Model
Ensure `ml_models/solarguard_model_v3.keras` is in place (see Section 4 below). Then run:
```powershell
python manage.py verify_model
```

#### Step 5: Initialize the Database
```powershell
# Apply all Django schema migrations
python manage.py migrate

# Seed sample demo data (idempotent, safe to run multiple times)
python manage.py seed_demo_data
```

#### Step 6: Verify Django Health & Run Server
```powershell
python manage.py check
python manage.py runserver
```
Visit `http://127.0.0.1:8000` in your browser.

---

## 4. AI Model Collaboration & Verification

SolarGuard uses **MobileNetV2 CNN v3.0** for optical surface fault classification. Both developers run real local inference.

### Official Model Specifications
| Parameter | Value |
| :--- | :--- |
| **Active Version** | `v3.0` (MobileNetV2) |
| **Model File** | `ml_models/solarguard_model_v3.keras` |
| **File Size** | 9,697,439 bytes (9.25 MB) |
| **SHA-256 Checksum** | `C7D54BA2507E2FD1E062CD446AC124EB4C897820402BB54D251B4B1BFA683CD6` |
| **Input Shape** | `(1, 224, 224, 3)` RGB, normalized `[-1.0, 1.0]` |
| **Class Mapping** | `[0: 'Bird-Dropping', 1: 'Dusty', 2: 'Normal', 3: 'Surface-Damage']` |

### How to Verify Model Integrity
Run the built-in audit command anytime:
```powershell
python manage.py verify_model
```
Expected output:
```text
  [PASS] File exists. Size: 9,697,439 bytes (9.25 MB)
  [PASS] SHA-256 Checksum Verified: C7D54BA2507E2FD1E062CD446AC124EB4C897820402BB54D251B4B1BFA683CD6
  [PASS] TensorFlow imported successfully: v2.21.0 (Keras v3.15.1)
  [PASS] Keras model loaded successfully.
  [PASS] Input dimensions match 224x224x3 RGB standard.
  [PASS] Output units match 4-class classification standard.
  [PASS] Synthetic tensor inference succeeded. Sum of probabilities: 1.0000
  [PASS] Real image inference: Surface-Damage
```

*Note on Model Files:* Large raw archives and candidate models (`ml_models/candidates/`, `Trained model Colab/`) are excluded from Git. Candidate v3.1 is staged and inactive; only official v3.0 is active.

---

## 5. Local Demo Accounts

After running `python manage.py seed_demo_data`, you can log in with any of the following pre-configured test roles:

| Role | Username | Password | Purpose & Scope |
| :--- | :--- | :--- | :--- |
| **Customer** | `demo_customer` | `SolarGuard2026!` | Views own installation, submits inspections, logs maintenance requests |
| **Technician** | `demo_tech` | `SolarGuard2026!` | Assigned arrays, verifies AI predictions, completes work orders |
| **Administrator** | `demo_admin` | `SolarGuard2026!` | Fleet overview, approves layout drafts, assigns technicians, audit trail |

---

## 6. Daily Git Collaboration Workflow

We maintain a clean 3-branch structure:
- `main` — **Stable production-ready code only**. Direct pushes to `main` are restricted.
- `tanushree-dev` — Tanushree's active development branch.
- `teammate-dev` — Teammate's active development branch.

### Initial Branch Setup (First Time Only)

```powershell
# Create and switch to your feature branch
# (If you are the teammate):
git checkout -b teammate-dev

# (If you are Tanushree):
git checkout -b tanushree-dev
```

### Daily Work Loop

#### 1. Start of Day: Sync with Latest `main`
Always pull the latest changes from `main` before writing new code:
```powershell
git checkout main
git pull origin main
git checkout teammate-dev
git merge main
```

#### 2. Making and Testing Changes
Edit files, run tests, and check status:
```powershell
# Run Django system checks
python manage.py check

# Run automated tests
python manage.py test core.test_runtime_repair core.test_v3_smoke core.test_phase10_journey

# Inspect modified files
git status
```

#### 3. Committing Changes
Write descriptive, concise commit messages:
```powershell
git add <files_you_modified>
git commit -m "feat(layout): improve grid snapping on 4-3-4 arrays"
```

#### 4. Pushing Your Branch
Push your branch to GitHub:
```powershell
git push -u origin teammate-dev
```

#### 5. Creating a Pull Request (PR)
1. Go to the repository on GitHub.
2. Click **New Pull Request**.
3. Set **base: `main`** and **compare: `teammate-dev`**.
4. Add a summary of what changed and test results.
5. Request review from the other team member.
6. Once approved, merge using **Squash and merge** or **Merge pull request**.

#### 6. After PR is Merged
Update your local `main` and branch:
```powershell
git checkout main
git pull origin main
git checkout teammate-dev
git merge main
```

---

## 7. Database & Migration Collaboration Rules

1. **Each developer maintains their own local `db.sqlite3`**.
   - `db.sqlite3` is in `.gitignore` and **must NEVER be committed**.
2. **Schema changes must always be tracked via Django migrations**:
   - If you modify `core/models.py`, run:
     ```powershell
     python manage.py makemigrations
     ```
   - Commit the generated migration file (e.g., `0010_auto_....py`) to Git.
3. **When you pull your teammate's changes**:
   - Always run migrations immediately:
     ```powershell
     python manage.py migrate
     ```
4. **Never edit an already-committed migration file**. Create a new migration instead.

---

## 8. Summary of Safe Practices

- **Never force-push (`git push -f`)** to shared branches.
- **Never commit `.env` or credentials**.
- **Never commit private customer photos** or raw training datasets.
- Keep tests passing before opening a Pull Request:
  ```powershell
  python manage.py check
  python manage.py makemigrations --check --dry-run
  python manage.py test
  ```
