# SolarGuard — Project Audit & Technical Health Check

**Project:** SolarGuard — AI-Assisted Solar Panel Inspection & Maintenance Platform  
**Date of Audit:** October 2026  
**Auditor:** Antigravity (AI Engineering Assistant)  
**Owners:** Tanushree Burde and Aanchal Nasre  
**Status:** Audit Completed — Awaiting Owner Approval for Next Phase  

---

## 1. Executive Summary

SolarGuard is designed as an AI-assisted web platform that allows individual solar panel owners and professional maintenance technicians to inspect solar panels using RGB photographs, track maintenance history, and assess panel condition.

The existing repository contains a functioning **initial prototype (MVP)** built with Django and SQLite. The web server runs, the user can log in, upload an image, view a dashboard with charts, and inspect pre-seeded records. 

However, beneath the surface, there is a **major disconnect between what the application claims to do and what it actually does**:
1. **The Vision AI is trained on synthetic drawings, not real solar panels:** The current vision model was trained on 154 images created using basic computer graphics (lines and circles drawn with Python Pillow), achieving an artificial "100% accuracy" that will fail on real photos.
2. **There is no deep learning CNN model file:** The convolutional neural network described in the SRS (`fault_cnn.h5`) does not exist on disk, and TensorFlow is not installed in the environment.
3. **The Degradation Predictor is based on synthetic numbers:** The Random Forest model predicts degradation probabilities from fabricated mathematical formulas rather than verified sensor or field data.
4. **Core product workflows are missing:** Users cannot add panels, edit installations, or record maintenance actions from the web interface (these require the raw Django Admin backend). There is no user ownership or data privacy—every logged-in user can see all panels and inspections.

This audit provides a complete, beginner-friendly inventory of the codebase, explains what works, details what is broken or misleading, and recommends a clear roadmap to make SolarGuard genuine, robust, and presentation-ready.

---

## 2. Technology Stack Inventory

| Component | Technology | Version in Environment | Role in Project | Assessment |
| :--- | :--- | :--- | :--- | :--- |
| **Backend Web Framework** | Python / Django | Python 3.12 / Django 6.1 | Web server, routing, authentication, ORM | **Healthy & Working** |
| **Database** | SQLite 3 | `db.sqlite3` (160 KB) | Stores panels, inspections, maintenance logs, user accounts | **Functional for local dev** |
| **Frontend Templates** | Django Template Language (DTL) | Standard DTL | HTML page rendering, server-side data binding | **Functional** |
| **CSS & Design** | Bootstrap 5 + Custom CSS | Bootstrap 5.3.3 (CDN) | Layout, navigation, tables, responsive cards | **Works, but needs brand styling** |
| **Icons** | Bootstrap Icons | 1.11.3 (CDN) | UI iconography | **Healthy** |
| **Charts & Visualization** | Chart.js | 4.4.2 (CDN) | Interactive doughnut chart for fault distribution | **Healthy & Lightweight** |
| **Machine Learning (Tabular/Vision)** | Scikit-Learn | 1.9.0 | Trains Random Forest models for vision features & degradation | **Functional runtime** |
| **Image Processing** | OpenCV (`opencv-python`) | 5.0.0.93 | Extracts color histograms, edge sharpness, texture features | **Healthy** |
| **Image I/O** | Pillow | 12.3.0 | Image opening, format verification, mock image drawing | **Healthy** |
| **Numerical Processing** | NumPy | 2.5.2 | Array transformations and feature matrices | **Healthy** (Note: see TensorFlow notes below) |
| **Deep Learning Framework** | TensorFlow / Keras | *Not Installed* (commented in `requirements.txt`) | Intended for the custom CNN image classifier | **Missing / Inactive** |

---

## 3. Existing Features & Current Capabilities

Here is what currently exists in the project and can be interacted with right now:

### 3.1 Authentication & Sessions
- **Working:** Standard Django session-based login (`/login/`) and logout (`/logout/`).
- **Limitation:** Only one role is effectively used. There is a single pre-seeded admin user (`admin`). There is no public registration, password reset, or differentiation between an individual homeowner and a facility technician.

### 3.2 Monitored Panels Inventory
- **Working:** Database model (`Panel`) stores panel serial number, installation date, last cleaning date, location/array zone, temperature exposure, and dust index.
- **Limitation:** Panels cannot be added or edited from the user dashboard. Users must navigate to the backend Django Admin (`/admin/`) to register new solar panels.

### 3.3 Image Inspection Flow
- **Working:** Users can navigate to `/inspect/`, pick a panel from a dropdown, upload an image file (JPEG/PNG), add optional notes, and click "Run Dual-Model Analysis".
- **Working:** The uploaded file is saved to `media/inspections/YYYY/MM/DD/`, and predictions are calculated synchronously.
- **Working:** The result is rendered on a detailed report page (`/inspect/result/<id>/`) showing the image, predicted condition, confidence score, degradation probability, and automated advice.

### 3.4 Fleet Health Dashboard
- **Working:** Dashboard at `/` displays:
  - 4 KPI cards: Monitored Panels count, High Risk Panels count, Moderate Risk Watch count, Total Inspections count.
  - An urgent watchlist of high-risk panels.
  - A Chart.js doughnut chart showing the distribution of faults (Normal, Dusty, Bird-Dropping, Cracked).
  - A historical log table of recent inspections with links to full reports.

### 3.5 Django Administration
- **Working:** Full admin panel at `/admin/` with custom list displays, filters, search bars, and date hierarchies for `Panel`, `Inspection`, and `MaintenanceLog`.

### 3.6 Automated Tests
- **Working:** 3 automated end-to-end tests exist in `core/tests.py` testing the predictor execution, login redirect, and inspection upload flow. All 3 tests pass.

---

## 4. Machine Learning & Dataset Audit

This is the most critical area of the audit.

### 4.1 Vision Classifier (`ml_engine/train_vision.py` & `predictor.py`)
- **Claim:** The `README.md` states: *"Validation Accuracy: 100.0% (5-fold cross-validation)"*.
- **Reality:** The classifier was trained using `ml_engine/generate_mock_data.py`, which uses Pillow to draw artificial shapes (blue boxes with lines for "Normal", yellow tint for "Dusty", white circles for "Bird-Dropping", and zigzag lines for "Cracked"). 
- **Impact:** An ML model that gets 100% on synthetic geometric drawings will immediately fail or give random answers when presented with a real photograph of a solar panel taken from a phone or drone.
- **Academic & SEPM Risk:** Presenting synthetic 100% accuracy as a verified solar vision classifier violates academic project integrity and goes directly against Section 5 of `SYSTEM_INSTRUCTIONS.md` (*"Do not fabricate datasets, model weights, evaluation metrics, confidence scores, or working predictions"*).

### 4.2 Deep Learning CNN (`ml_engine/train_cnn.py`)
- **Status:** **Model weights do not exist.**
- **Details:** The expected weight file `ml_engine/models/fault_cnn.h5` and `classes.json` are absent. 
- **Environment Gap:** `tensorflow` is commented out in `requirements.txt` and not installed in `.venv`. Furthermore, `numpy` is version `2.5.2`; TensorFlow 2.x often has strict binary compatibility requirements with NumPy < 2.0 on Windows.
- **Fallback behavior:** Because the CNN file is missing, `predictor.py` silently falls back to Tier 2 (the synthetic vision classifier) or Tier 3 (an OpenCV rule-based edge/color heuristic).

### 4.3 Degradation Risk Predictor (`ml_engine/train_rf.py`)
- **Status:** Trained on 2,000 synthetic rows created by an internal mathematical formula (`generate_synthetic_degradation_data`).
- **Details:** The features (`panel_age_months`, `fault_count_last_6_months`, `days_since_last_cleaning`, `avg_temp_exposure`, `dust_index_avg`) are assigned risk scores based on hardcoded weightings (e.g., 28% age, 24% faults, 18% cleaning, 16% temperature, 14% dust).
- **Compliance Conflict:** `SYSTEM_INSTRUCTIONS.md` Section 3 explicitly notes: *"True degradation forecasting is not an approved v1 feature. The initial SRS's Random Forest trained on heuristic data must not be represented as validated degradation prediction. Initial maintenance priority, if implemented, must be transparent, explainable, and labeled as rules-based until independently validated."*

### 4.4 Dataset Preparation Script (`ml_engine/split_dataset.py`)
- **Status:** Functional script to split Kaggle datasets into train/validation folders.
- **Identified Flaw:** The script automatically renames Kaggle's folder `Physical-Damage` to `Cracked`. In real datasets, physical damage includes cell discoloration, delamination, shattered glass, and snail trails—not just surface cracks. This violates `SYSTEM_INSTRUCTIONS.md` Section 5 (*"Do not rename a broad Physical Damage category to Cracked without image-level verification"*).

---

## 5. Architectural & Codebase Gaps

### 5.1 Data Model & Authorization Gaps
1. **No User Ownership:** `Panel`, `Inspection`, and `MaintenanceLog` have no `user` or `organization` field. Any user who logs in can see, inspect, and modify every panel.
2. **Missing Maintenance Issue Lifecycle:** While `MaintenanceLog` exists in `core/models.py`, it is not linked to an `Inspection`. There is no concept of an `Issue` status (`Open`, `In Progress`, `Resolved`, `Needs Review`). If an inspection finds a "Cracked" panel, no issue ticket is created, and there is no way in the UI to mark it repaired or upload a verification follow-up photo.
3. **No Site/Installation Hierarchy:** The location is currently a raw string field (`site_location`). In professional setups, a `Site` contains multiple `Panels`. For individual owners, an `Installation` represents their home rooftop.

### 5.2 UI & User Experience Gaps
1. **Brand Identity Divergence:** The current UI uses Bootstrap's default dark top bar, bright blue buttons, and generic alert badges. `BRAND_GUIDELINES.md` specifies a thoughtful visual identity:
   - Primary: Forest Green (`#176B52`)
   - Accent: Warm Solar Gold (`#D6A545`)
   - Canvas: Soft Light Grey/Green (`#F7F9F6`)
   - Ink: Deep Slate (`#192B27`)
2. **Single User Persona:** The interface currently treats every user as a fleet manager with complex telemetry inputs (e.g., asking for "Dust Index 0.0 to 1.0" and "Average Temperature Exposure"). A residential homeowner has no idea what their dust index is and just wants to know: *"Is my roof panel dirty or damaged, and should I call a technician?"*
3. **Missing "Unable to Assess" State:** The current predictor will always guess one of the 4 classes, even if you upload a picture of a cat, a car, or a pitch-black photo. It must support an `Unable to assess / Retake photo` state with constructive guidance.

### 5.3 Security & Operational Settings
1. **Hardcoded Secret Key:** In `solarguard_project/settings.py`, `SECRET_KEY` is hardcoded as `'django-insecure-solarguard-sepm-prototype-key-2026-demo'`.
2. **Unrestricted Hosts:** `ALLOWED_HOSTS = ['*']` and `DEBUG = True`.
3. **Upload Validation:** `forms.py` only inspects the filename extension (`.jpg`, `.jpeg`, `.png`). It does not verify image magic numbers or decode safety to prevent malicious file uploads.

---

## 6. Recommendations: Keep, Repair, or Rebuild

| Component | Recommendation | Why? | Action Plan |
| :--- | :---: | :--- | :--- |
| **Django + SQLite Stack** | **KEEP** | Standard, clean, fast, easily demoed in college viva, runs on any laptop. | Keep existing Django 5/6 core setup and URL structure. |
| **Chart.js Dashboard Charts** | **KEEP** | Lightweight, responsive, renders smoothly on client browsers without heavy server overhead. | Keep Chart.js, restyle colors to match Brand Guidelines palette. |
| **Django Admin Configuration** | **KEEP** | Very helpful for viva evaluators and instructors to inspect backend records. | Keep and enhance with better filters. |
| **Core Models (`Panel`, `Inspection`, `MaintenanceLog`)** | **REPAIR** | The basic fields are good, but ownership, issue tracking, and site relationships are missing. | Add `user` ownership, link `MaintenanceLog` to `Inspection`, add status workflow (`Open`, `In Progress`, `Resolved`). |
| **ML Inference Architecture (`ml_engine/`)** | **REPAIR** | The file structure is clean, but the tiers and claims must be honest and modular. | Establish an explicit, versioned adapter. Use a clearly labeled development mock until real models are trained. Add "Unable to assess" detection. |
| **Degradation Prediction** | **REPAIR** | Synthetic RF model masquerading as real machine learning creates academic viva vulnerability. | Relabel transparently as **"Rules-Based Maintenance Priority Engine"** with fully explainable formulas. |
| **Synthetic Vision Classifier & Mock Images** | **REBUILD** | Training a model on 154 PIL geometric drawings and claiming 100% accuracy is unacceptable for a final project. | Discard synthetic model claims. Prepare a proper Kaggle/research dataset audit under Gate 2, train on external GPU (Colab), and import verified weights. |
| **User Interface & Brand Styling** | **REPAIR** | Layout works, but colors, typography, tone, and audience separation need alignment. | Apply Brand Guidelines palette (Forest Green/Solar Gold), create clear Owner vs Professional tabs/views, add panel creation modals. |

---

## 7. Next Steps & Recommended Milestones

In accordance with `SYSTEM_INSTRUCTIONS.md`, work should proceed in disciplined stages:

```
[ Step 0: Project Audit ] (CURRENT - Completed)
           │
           ▼
[ Step 1: Requirements Gate ]
• Resolve Open Questions with Project Owners (Tanushree & Aanchal)
• Finalize scope: Owner workflow vs Professional workflow
• Approve revised SRS & Decision Log (docs/DECISIONS.md)
           │
           ▼
[ Step 2: Data Gate ]
• Audit real solar panel image dataset (e.g., Kaggle Solar Panel Images)
• Confirm verified class labels (Normal, Dusty, Bird-Dropping, Cracked)
• Check image resolutions, licenses, and duplicate counts
           │
           ▼
[ Step 3: Foundation Gate (Web App & Workflows) ]
• Implement user ownership & roles (Owner vs Professional)
• Build Panel & Site management UI (add/edit without Django Admin)
• Build complete Maintenance Issue lifecycle (Open -> In Progress -> Resolved)
• Apply Brand Guidelines visual design tokens & styling
           │
           ▼
[ Step 4: Model Gate ]
• Train lightweight vision model on cloud GPU (Google Colab / Kaggle) using real data
• Export weights (`.keras` / `.joblib`) and metadata
• Connect to Django via modular adapter with "Unable to assess" handling
           │
           ▼
[ Step 5: Release & Viva Preparation Gate ]
• End-to-end testing, error handling review, demo dataset seeding
• Viva presentation cheat sheet and documentation
```
