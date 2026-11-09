# SolarGuard — Phased Implementation Plan
## Step-by-Step Engineering Milestones, Safety Guardrails, and Testing Protocols

**Project Owners:** Tanushree Burde and Aanchal Nasre  
**Course/Context:** Software Engineering & Project Management (SEPM)  
**Date:** October 2026  
**Status:** Proposed Roadmap — Awaiting Owner Approval Before Execution  
**Execution Guardrail:** Do not modify application code until this plan is formally approved.

---

## 1. Principles & Safety Guardrails for Beginners

As an engineering beginner, refactoring a working software prototype can feel intimidating. Small code mistakes can cause database migration errors, break passing tests, or accidentally erase saved data.

To protect our project, we will follow these strict safety rules:
1. **Preserve the Working Django Core:** We keep the existing Django architecture, URL structure, and SQLite database. We do not rebuild from scratch.
2. **Non-Destructive Database Migrations:** When we add new columns (such as `user` or `installation_id`), we will always set `null=True, blank=True` or assign safe defaults. This guarantees that existing panels, inspections, and accounts stored in `db.sqlite3` will never be deleted or corrupted.
3. **Safety Backup Before Every Step:** Before running database commands or altering models, we make a timestamped backup copy of `db.sqlite3`. If anything goes wrong, we can restore it in two seconds.
4. **Honest ML Separation:** We strictly separate the **Synthetic Demo Classifier** (used for offline development and unit tests) from the **Validated Real-Image Model** (trained on Colab). The user interface will always show an unambiguous banner whenever a mock prediction is rendered.
5. **No Blind Equating of Classes:** The 4th class is provisionally handled as `Cracked / Surface Damage` until the Gate 2 Colab visual audit confirms the exact contents of the dataset.
6. **Small, Verifiable Commits:** We implement one small milestone at a time, run automated tests, test in the browser, and verify completion criteria before moving to the next.

---

## 2. Milestone Overview Matrix

| Milestone | Title | Focus Area | Risk Level | Est. Scope |
| :---: | :--- | :--- | :---: | :---: |
| **M0** | Safety Checkpoint & Environment Hardening | Backup database, configure `.env` secrets | Very Low | Prep & Config |
| **M1** | Non-Destructive Data Model Expansion | Add User ownership, Site/Installation, MaintenanceIssue | Medium (Migration) | Core Models |
| **M2** | Inference Adapter & Rules Priority Engine | Decoupled adapter, blur/triage checks, deterministic priority | Low | ML & Logic |
| **M3** | Brand Redesign & Audience Dashboards | Forest Green/Solar Gold palette, Owner vs Pro views, Panel UI | Low | Templates & CSS |
| **M4** | Maintenance Lifecycle & Follow-up Verification | Issue tracking (`Open` $\rightarrow$ `Resolved`), Before/After view | Low | Views & Forms |
| **M5** | Real-Image Model Integration (Colab) | Import trained weights, class mapping, test CPU latency | Low | ML Engine |
| **M6** | Security Hardening, Tests & Viva Preparation | Upload verification, permission tests, viva presentation guide | Low | Testing & Docs |

---

## 3. Detailed Milestone Specifications

---

### Milestone 0: Safety Baseline & Environment Hardening

#### 0.1 Objective & Beginner Explanation
Before making any changes, we must freeze our current working baseline. We will back up the database and move secret keys out of plain code into an environment variable file (`.env`). In software development, hardcoding secrets in `settings.py` is a security vulnerability; using `.env` keeps passwords and keys private.

#### 0.2 Prerequisites
* Working Python 3.12 virtual environment (`.venv`).
* 3 existing tests in `core/tests.py` passing (`python manage.py test`).

#### 0.3 Files Likely to Change
* `db.sqlite3` (create backup copy `db.sqlite3.backup_baseline`)
* `.env` (create from `.env.example`)
* `solarguard_project/settings.py` (load `SECRET_KEY` and `DEBUG` via `os.environ` or `python-dotenv`)
* `requirements.txt` (ensure `python-dotenv` is listed)

#### 0.4 Risk & Data Loss Assessment
* **Risk:** None. This step makes no changes to database tables or application logic.
* **Mitigation:** Database is copied to an unmanaged backup file before editing settings.

#### 0.5 Manual Testing Steps
1. Create a backup of `db.sqlite3` in the root folder.
2. Verify that running `python manage.py runserver` still launches the site at `http://127.0.0.1:8000/`.
3. Verify that you can still log in using the configured administrator account.

#### 0.6 Automated Tests
* Run `python manage.py test core`. All 3 original tests must pass without errors.

#### 0.7 Completion Criteria
* Backup file `db.sqlite3.backup_baseline` exists.
* `SECRET_KEY` in `settings.py` reads from `.env` with a secure fallback for development.
* All existing tests pass.

---

### Milestone 1: Non-Destructive Data Model Expansion & Authorization

#### 1.1 Objective & Beginner Explanation
Currently, any logged-in user can see all panels and inspections in the database because models lack a `user` field. Furthermore, there is no concept of a "Site" or an "Issue Ticket" with a status (`Open`, `In Progress`, `Resolved`). In this milestone, we expand `core/models.py` to add these essential product features while ensuring we **do not lose or erase any existing panel or inspection data**.

#### 1.2 Prerequisites
* Milestone 0 completed and verified.

#### 1.3 Files Likely to Change
* `core/models.py` (expand models)
* `core/migrations/0002_user_ownership_and_maintenance_lifecycle.py` (auto-generated migration)
* `core/admin.py` (register new models and adjust list displays)

#### 1.4 Detailed Schema Changes
1. **New Model `Installation`:**
   * Represents a physical rooftop or commercial solar site.
   * Fields: `name`, `user` (FK to `auth.User`), `address`, `install_date`, `system_capacity_kw`, `is_active`.
2. **Update Model `Panel`:**
   * Add optional `installation` (FK to `Installation`, `null=True, blank=True`).
   * Add optional `user` (FK to `auth.User`, `null=True, blank=True`).
   * Keep all existing fields (`serial_number`, `site_location`, `last_cleaned_date`, etc.) completely intact so old records remain valid.
3. **Update Model `Inspection`:**
   * Add `user` (FK to `auth.User`, `null=True, blank=True`).
   * Add `condition_label` (stores `Normal`, `Dusty`, `Bird-Dropping`, `Cracked / Surface Damage`, `Unable to assess`).
   * Add `is_mock_prediction` (Boolean, default `True`).
   * Add `maintenance_priority_score` (Integer 0–100) and `maintenance_priority_level` (`Low`, `Medium`, `High`).
   * Add `priority_breakdown` (JSONField for explainability).
4. **New Model `MaintenanceIssue`:**
   * Represents an actionable maintenance ticket.
   * Fields: `panel` (FK), `inspection` (FK, nullable), `status` (`OPEN`, `IN_PROGRESS`, `RESOLVED`, `NEEDS_REVIEW`), `priority` (`LOW`, `MEDIUM`, `HIGH`), `description`, `scheduled_date`, `created_at`, `resolved_at`.
5. **Update Model `MaintenanceLog`:**
   * Add optional `issue` (FK to `MaintenanceIssue`, `null=True, blank=True`).
   * Add `user` (FK to `auth.User`, `null=True, blank=True`).

#### 1.5 Risk & Data Loss Assessment
* **Critical Risk:** If we add a required (non-null) ForeignKey without a default, Django migration will fail or demand manual input, potentially aborting migrations.
* **Mitigation Protocol:** 
  1. All new foreign keys are explicitly marked `null=True, blank=True`.
  2. A data migration or post-migration script will automatically assign existing pre-seeded panels and inspections to the default `admin` user.
  3. No existing columns are renamed or deleted.

#### 1.6 Manual Testing Steps
1. Run `python manage.py makemigrations`.
2. Run `python manage.py migrate`.
3. Open `http://127.0.0.1:8000/admin/` and verify that:
   * Existing panels are still present.
   * Existing inspection history is still present.
   * New models (`Installation`, `MaintenanceIssue`) appear in Django Admin and can be opened without errors.

#### 1.7 Automated Tests
* Write a new test in `core/tests.py`: `test_legacy_records_preserved()` ensuring pre-existing panel counts remain identical before and after migration.

#### 1.8 Completion Criteria
* Migration applies cleanly with zero warnings or errors.
* Existing database records remain accessible and fully intact.
* Admin panel allows creating an `Installation` and linking a `Panel` to it.

---

### Milestone 2: Modular ML Inference Adapter & Rules-Based Priority Engine

#### 2.1 Objective & Beginner Explanation
In this milestone, we separate our machine learning code from our web views by creating a clean "adapter" (`ml_engine/adapter.py`). We will also retire the unvalidated synthetic Random Forest model and replace it with our transparent, deterministic **Rules-Based Maintenance Priority Engine**. Finally, we will add automated image quality triage (detecting blurry or pitch-black photos) so the system returns `Unable to assess / Retake photo` instead of guessing randomly.

#### 2.2 Prerequisites
* Milestone 1 completed and verified.

#### 2.3 Files Likely to Change
* `ml_engine/adapter.py` (new modular inference adapter)
* `ml_engine/priority_engine.py` (new rules-based maintenance priority engine)
* `ml_engine/quality_checker.py` (new image blur and lighting triage using OpenCV/Pillow)
* `core/views.py` (update inspection upload view to use the new adapter)

#### 2.4 Detailed Architecture
1. **`ml_engine/quality_checker.py`:**
   * Calculates Laplacian variance. If score $< 80.0 \implies$ Flag as `BLURRY`.
   * Calculates mean RGB brightness. If $< 20 \implies$ Flag as `TOO_DARK`; if $> 240 \implies$ Flag as `OVEREXPOSED`.
2. **`ml_engine/priority_engine.py`:**
   * Computes the deterministic Maintenance Priority Score ($0 - 100$) based on visual defect weight, days since cleaning, panel age, and past fault history.
   * Outputs a transparent dictionary explaining the point breakdown.
3. **`ml_engine/adapter.py`:**
   * Checks if `ml_engine/models/solarguard_model.keras` exists:
     * If **YES**: Loads real deep learning weights and sets `is_mock=False`.
     * If **NO**: Calls development mock classifier and sets `is_mock=True`.
   * Executes image quality check first: if poor quality, immediately returns `condition_label="Unable to assess"` with actionable feedback.

#### 2.5 Risk & Data Loss Assessment
* **Risk:** Inspection upload view might fail if the adapter interface doesn't match view expectations.
* **Mitigation:** The adapter will provide standard dataclass / dictionary outputs with defensive fallback error handling (`try / except`).

#### 2.6 Manual Testing Steps
1. Upload a regular panel image at `/inspect/`. Verify result displays condition and explainable priority breakdown.
2. Upload a pitch-black image (or completely blurry image). Verify that the result screen displays:  
   *“Unable to assess / Retake photo: The image appears underexposed or blurred. Please take a clear, well-lit photo.”*
3. Verify that the UI displays the development mock indicator badge:  
   *⚠️ Development Demonstration: Using mock statistical logic. Real deep learning weights pending.*

#### 2.7 Automated Tests
* Test blur detection with a synthetic blurred image.
* Test pitch-black image triggering `Unable to assess`.
* Test deterministic priority calculation: verifying that a panel with a crack scores $MPI \ge 70$ (High Priority).

#### 2.8 Completion Criteria
* `ml_engine/adapter.py` functions cleanly without crashing on corrupt or bad inputs.
* Blurry and dark images are properly caught before classification.
* Synthetic Random Forest predictions are replaced with transparent rules engine outputs.

---

### Milestone 3: Brand Redesign & Audience-Tailored Dashboards

#### 3.1 Objective & Beginner Explanation
The current prototype uses default Bootstrap blue buttons and a dark grey navigation bar. In this milestone, we restyle the application to match the calm, trustworthy solar aesthetic specified in [BRAND_GUIDELINES.md](file:///d:/RBU/RBU%20Sem%205/SEPM/Sepm%20Project%20SolarGuard/BRAND_GUIDELINES.md) (Forest Green `#176B52`, Solar Gold `#D6A545`, Light Canvas `#F7F9F6`, Slate `#192B27`). We also create clear, separate views for **Individual Owners** (simple home view) and **Professional Managers** (multi-panel fleet view), plus a web modal allowing users to add panels directly from the dashboard without needing the raw Django Admin backend.

#### 3.2 Prerequisites
* Milestone 1 and Milestone 2 completed.

#### 3.3 Files Likely to Change
* `core/templates/core/base.html` (navbar, footer, brand colors, typography)
* `core/templates/core/dashboard.html` (Owner view vs Professional view tabs, KPI cards, restyled Chart.js doughnut chart)
* `core/templates/core/inspect.html` (upload form with drag-and-drop and camera support)
* `core/templates/core/report.html` (inspection result page matching Section 5 of Brand Guidelines)
* `core/static/css/solarguard.css` (custom design tokens and utility styles)
* `core/forms.py` (add direct `PanelForm` and `InstallationForm` for user-facing creation)

#### 3.4 Risk & Data Loss Assessment
* **Risk:** Visual redesign breaking mobile responsive layouts or breaking form POST submissions.
* **Mitigation:** Rely on standard Bootstrap 5 responsive grid classes while injecting custom CSS variables for brand colors. Test all forms with CSRF tokens.

#### 3.5 Manual Testing Steps
1. Navigate across all pages on desktop browser; verify high-contrast text and correct Forest Green/Solar Gold styling.
2. Open Developer Tools in browser (`F12`), toggle Device Toolbar (iPhone 12 / Galaxy S20), and verify navigation collapse and upload button usability.
3. Test the "Add Panel / Installation" modal directly on the dashboard; verify that a new panel is successfully created and appears in the list without opening Django Admin.
4. Toggle between "Individual Owner View" (simple summary) and "Professional Fleet View" (dense table and filters).

#### 3.6 Automated Tests
* Test that dashboard views render HTTP 200 for both owner and professional users.
* Test that `PanelForm` validates serial numbers and associates them with the logged-in user.

#### 3.7 Completion Criteria
* Brand Guidelines palette applied consistently across all templates.
* Direct panel/installation creation works smoothly from the user dashboard.
* No generic Bootstrap blue buttons remain.

---

### Milestone 4: Maintenance Lifecycle & Verification Inspection

#### 4.1 Objective & Beginner Explanation
Currently, when an inspection finds a fault, there is no way to take action or track repairs on the website. In this milestone, we implement the complete **Maintenance Issue Lifecycle**:
1. When a fault is found, the user clicks **"Log Maintenance Issue"** (Status: `Open`).
2. A technician or homeowner records cleaning or repair work (Status: `In Progress` or `Resolved`).
3. The user uploads a **Follow-up Verification Photo**, displaying a side-by-side **Before & After** comparison to verify the panel is now clean and working.

#### 4.2 Prerequisites
* Milestones 1, 2, and 3 completed.

#### 4.3 Files Likely to Change
* `core/views.py` (issue creation, issue detail view, maintenance action log view, follow-up upload view)
* `core/urls.py` (routes: `/issues/`, `/issues/<id>/`, `/issues/<id>/log-action/`, `/issues/<id>/verify/`)
* `core/templates/core/issue_list.html` (triage table of open/in-progress issues)
* `core/templates/core/issue_detail.html` (issue history, action log, before/after comparison)
* `core/forms.py` (`MaintenanceIssueForm`, `MaintenanceActionForm`)

#### 4.4 Risk & Data Loss Assessment
* **Risk:** Deleting an issue could accidentally delete historical inspections.
* **Mitigation:** Use `models.PROTECT` or `models.SET_NULL` on foreign keys so that inspection history is preserved forever, even if an issue ticket is updated or closed.

#### 4.5 Manual Testing Steps
1. Upload a dusty panel image at `/inspect/`.
2. On the result page, click **"Log Maintenance Issue"**. Fill in "Scheduled cleaning for this weekend". Click Save.
3. Verify that the issue appears on the Maintenance Queue (`/issues/`) with status `Open`.
4. Open the issue, click **"Record Action Taken"**, select `Cleaning`, enter "Wiped panel with demineralized water", and set status to `In Progress`.
5. Click **"Upload Follow-up Verification Photo"**, upload a clean panel photo.
6. Verify that the Before & After card renders both images side-by-side.
7. Click **"Mark Issue as Resolved"**.

#### 4.6 Automated Tests
* Write automated tests in `core/tests.py`:
  * `test_create_maintenance_issue_from_inspection()`
  * `test_issue_status_transitions()`
  * `test_follow_up_inspection_links_to_issue()`

#### 4.7 Completion Criteria
* Complete end-to-end maintenance workflow operates without errors.
* Before/After comparison displays cleanly.
* Issues can be filtered by `Open`, `In Progress`, and `Resolved`.

---

### Milestone 5: Real-Image Model Integration (Colab Pipeline)

#### 5.1 Objective & Beginner Explanation
Following the execution of the Data Audit in Google Colab ([docs/DATA_AUDIT_PLAN.md](file:///d:/RBU/RBU%20Sem%205/SEPM/Sepm%20Project%20SolarGuard/docs/DATA_AUDIT_PLAN.md)), we download the trained lightweight model weights (`solarguard_model.keras`), class mapping (`class_indices.json`), and metadata (`metadata.json`). We place them into `ml_engine/models/`. The adapter will detect these files and seamlessly switch from the development mock to the validated deep learning model.

#### 5.2 Prerequisites
* Milestone 4 completed.
* Google Colab audit and training notebook executed (Gate 2 & Gate 4).
* Artifacts downloaded to local machine.

#### 5.3 Files Likely to Change
* `ml_engine/models/solarguard_model.keras` (new model weight file, ~15 MB)
* `ml_engine/models/class_indices.json` (class index mapping)
* `ml_engine/models/model_metadata.json` (architecture details, training date, Macro-F1 score)
* `ml_engine/adapter.py` (load Keras model on CPU for local inference)

#### 5.4 Risk & Data Loss Assessment
* **Risk:** Loading TensorFlow/Keras on Windows CPU might be slow or encounter library version conflicts.
* **Mitigation:**
  * Use lightweight MobileNetV2 with input size $224\times224\times3$.
  * If full TensorFlow has local installation issues on Windows, export model to ONNX runtime or TFLite (`.tflite`), which requires zero heavy TensorFlow dependencies on CPU.
  * The adapter retains the mock fallback if the model file is temporarily missing or corrupted.

#### 5.5 Manual Testing Steps
1. Place downloaded `solarguard_model.keras` and JSON files into `ml_engine/models/`.
2. Restart the Django server.
3. Upload a sample test image from `media/sample_test_images/`.
4. Verify that:
   * Prediction renders in under 2.0 seconds.
   * The result badge changes from "Development Mock" to:  
     *✅ Validated Real-Image Model: MobileNetV2 (Trained on verified PV dataset).*
   * Class labels match the verified class mapping from Colab.

#### 5.6 Automated Tests
* Test that the adapter successfully loads model metadata and executes inference on a sample RGB image tensor without exceptions.
* Benchmark inference time to assert execution completes under 3.0 seconds on CPU.

#### 5.7 Completion Criteria
* Real deep learning model replaces synthetic vision classifier.
* CPU inference completes within the 3.0-second performance requirement (NFR-1.1).
* UI accurately reports model provenance and confidence.

---

### Milestone 6: Security Hardening, Verification, and Viva Preparation

#### 6.1 Objective & Beginner Explanation
This final milestone ensures the application is completely secure, robust, and presentation-ready for your academic SEPM project defense (viva). We will add file upload binary validation (preventing unsafe files), verify that users cannot view each other's private data, seed realistic demo records, and prepare an evaluator walkthrough script for Tanushree and Aanchal.

#### 6.2 Prerequisites
* Milestones 0 through 5 completed.

#### 6.3 Files Likely to Change
* `core/forms.py` (magic byte header validation with `python-magic` or Pillow verify)
* `core/views.py` (ensure strict `login_required` and query filtering: `.filter(user=request.user)`)
* `core/tests.py` (comprehensive test suite covering all roles and security rules)
* `solarguard_project/settings.py` (security headers, CSRF cookies, allowed hosts check)
* `docs/VIVA_PRESENTATION_GUIDE.md` (new document: evaluator questions & defense cheat sheet)

#### 6.4 Risk & Data Loss Assessment
* **Risk:** None. Final polish and testing phase.

#### 6.5 Manual Testing Steps
1. **Security Test:** Log in as User A. Try to open User B's inspection URL directly. Verify system blocks access with HTTP 403 or 404.
2. **File Safety Test:** Rename a `.txt` or `.exe` file to `test.jpg` and try to upload it. Verify that the form rejects it with: *"Invalid image file. File content is not a valid photograph."*
3. **Empty State Test:** Create a brand new user account. Verify that the dashboard shows clean, helpful empty states with clear instructions on how to upload the first inspection.

#### 6.6 Automated Tests
* Run full project test suite:
  ```bash
  python manage.py test
  ```
* Target: 100% passing tests covering:
  * Model relationships and cascading integrity.
  * Role and ownership isolation.
  * File upload security and decode validation.
  * Quality triage (blurry/dark rejection).
  * Deterministic priority engine calculation.
  * Maintenance issue lifecycle transitions.

#### 6.7 Completion Criteria
* All automated tests pass cleanly.
* Zero unhandled 500 errors on invalid inputs or unauthorized access attempts.
* Evaluator Viva Presentation Guide completed and ready for project demonstration.

---

## 4. Summary: Step-by-Step Approval Checkpoint

In accordance with `SYSTEM_INSTRUCTIONS.md` (Section 10) and our implementation guardrails:
* **No application code, models, or dependencies have been modified yet.**
* We will pause here and wait for project owner review and formal approval.
* Upon receiving your approval, we will proceed directly to **Milestone 0 (Safety Checkpoint)** and begin building out the platform step by step.
