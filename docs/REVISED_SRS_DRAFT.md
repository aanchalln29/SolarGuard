# Software Requirements Specification (SRS) — Revised Draft
## SolarGuard: AI-Assisted Solar Panel Inspection & Maintenance Platform

**Project Owners:** Tanushree Burde and Aanchal Nasre  
**Course/Context:** Software Engineering & Project Management (SEPM)  
**Document Status:** Working Draft (Reflecting Approved Architecture Decisions)  
**Date:** October 2026  
**Document Version:** 2.0-DRAFT  

---

## Document Roadmap & Beginner's Guide

> [!NOTE]
> **Why is this SRS revised?**  
> The original SRS proposed two machine learning components: a Convolutional Neural Network (CNN) for image defect detection and a Random Forest (RF) model predicting "Degradation Probability %". During our technical audit ([docs/PROJECT_AUDIT.md](file:///d:/RBU/RBU%20Sem%205/SEPM/Sepm%20Project%20SolarGuard/docs/PROJECT_AUDIT.md)), we discovered that the existing codebase had no real CNN model weights on disk, the vision classifier was trained on synthetic Pillow drawings (artificial circles and lines), and the Random Forest was trained on synthetic mathematical formulas.
> 
> Presenting synthetic models as verified real-world AI during project evaluations creates severe academic vulnerability. This revised SRS establishes an **honest, academically defensible, and product-focused baseline** based on the approved decisions in [DECISIONS.md](file:///d:/RBU/RBU%20Sem%205/SEPM/Sepm%20Project%20SolarGuard/DECISIONS.md).

---

## 1. Introduction

### 1.1 Purpose
This Software Requirements Specification (SRS) details the functional and non-functional requirements for **SolarGuard**, a web-based, AI-assisted solar photovoltaic (PV) panel inspection and maintenance management platform. 

SolarGuard enables residential solar owners and commercial facility maintenance personnel to:
1. Capture or upload standard RGB photographs of solar panels.
2. Receive an **assistive visual condition assessment** (e.g., Normal, Dusty, Bird-Dropping, Cracked / Surface Damage, or Unable to Assess).
3. Evaluate an explainable, **rules-based maintenance priority** based on operational factors (age, cleaning history, past defects).
4. Track the end-to-end lifecycle of maintenance issues (`Open` $\rightarrow$ `In Progress` $\rightarrow$ `Resolved`), including follow-up verification inspections.

### 1.2 Scope and Product Boundary
* **What SolarGuard IS:**
  * A practical web application built with Django and SQLite (development) / PostgreSQL (production-ready).
  * An assistive triage tool providing preliminary visual observations of panel surfaces.
  * A structured system of record for tracking solar installations, inspection histories, and maintenance actions.
  * An explainable maintenance prioritization system based on transparent, deterministic operational rules.
* **What SolarGuard IS NOT:**
  * **Not an electrical diagnostic device:** It cannot certify electrical safety, ground-fault integrity, or inverter health.
  * **Not a power loss / degradation meter:** It cannot measure real kilowatt-hour generation loss or remaining useful lifespan from a single photograph.
  * **Not an autonomous system:** It does not operate drones, control robotic cleaning machinery, or process continuous live video streams.
  * **Not an automated guarantee:** The visual classification is an advisory finding; it never automatically marks hardware "safe" or "repaired" without human verification.

### 1.3 Definitions, Acronyms, and Abbreviations
* **RGB Image:** A standard color photograph consisting of Red, Green, and Blue color channels (such as taken by a smartphone or digital camera).
* **PV (Photovoltaic):** Technology that converts light directly into electricity using semiconductor solar cells.
* **CNN (Convolutional Neural Network):** A category of deep learning models specifically designed to identify visual patterns, shapes, and textures in images.
* **Transfer Learning:** An ML technique where a neural network pre-trained on millions of everyday images (e.g., MobileNetV2) is fine-tuned to recognize specialized targets (such as solar panel surface anomalies), requiring significantly less data and training time.
* **ORM (Object-Relational Mapping):** A Django programming technique that allows developers to manipulate database tables and records using standard Python classes and objects instead of writing raw SQL queries.
* **Synthetic Demo Classifier:** A mock/heuristic classifier currently present in the codebase that uses non-deep-learning statistical features on synthetic geometric drawings. It is strictly retained for local unit testing and development stubbing.
* **Validated Real-Image Model:** The target deep learning classifier to be trained on verified photographic datasets (e.g., Kaggle/research PV datasets) in Google Colab and integrated via an inference adapter.
* **Rules-Based Maintenance Priority Engine:** An explainable decision system that assigns Low, Medium, or High maintenance priority based on transparent, deterministic mathematical rules rather than unvalidated black-box predictions.

### 1.4 References
1. IEEE Std 830-1998: *IEEE Recommended Practice for Software Requirements Specifications*.
2. Project Charter & Engineering Rules: [SYSTEM_INSTRUCTIONS.md](file:///d:/RBU/RBU%20Sem%205/SEPM/Sepm%20Project%20SolarGuard/SYSTEM_INSTRUCTIONS.md).
3. Visual and User Experience Direction: [BRAND_GUIDELINES.md](file:///d:/RBU/RBU%20Sem%205/SEPM/Sepm%20Project%20SolarGuard/BRAND_GUIDELINES.md).
4. Project Decisions Log: [DECISIONS.md](file:///d:/RBU/RBU%20Sem%205/SEPM/Sepm%20Project%20SolarGuard/DECISIONS.md).
5. Codebase Health Check & Audit: [docs/PROJECT_AUDIT.md](file:///d:/RBU/RBU%20Sem%205/SEPM/Sepm%20Project%20SolarGuard/docs/PROJECT_AUDIT.md).
6. Open Architecture Questions: [docs/OPEN_QUESTIONS.md](file:///d:/RBU/RBU%20Sem%205/SEPM/Sepm%20Project%20SolarGuard/docs/OPEN_QUESTIONS.md).
7. Original Academic SRS: `sepm srs doc.docx`.

---

## 2. Overall Description

### 2.1 Product Perspective
SolarGuard is a modular, standalone web application. It follows Django's Model-View-Template (MVT) pattern, decoupled into clear operational layers:
1. **Presentation Layer:** Django templates styled with the SolarGuard design system (`BRAND_GUIDELINES.md` palette: Forest Green `#176B52`, Solar Gold `#D6A545`, Light Canvas `#F7F9F6`, Slate `#192B27`), responsive for mobile and desktop web browsers.
2. **Application / Business Logic Layer:** Django views and service modules managing authentication, panel registration, inspection processing, maintenance tracking, and maintenance priority scoring.
3. **ML Inference Adapter Layer:** An isolated interface (`ml_engine/adapter.py`) that separates the web application from the underlying machine learning runtime. This architecture allows swapping between the Development Mock Classifier and the Real-Image Deep Learning Classifier without touching database models or web views.
4. **Data Persistence Layer:** Django ORM connected to SQLite (for lightweight local development) and designed for seamless migration to PostgreSQL for production.

```
┌────────────────────────────────────────────────────────┐
│                   Web Browser Client                   │
│        (Owner Simplified View / Professional View)     │
└───────────────────────────┬────────────────────────────┘
                            │ HTTP / HTTPS
┌───────────────────────────▼────────────────────────────┐
│                  Django Application Core               │
│  ┌───────────────────────┐   ┌──────────────────────┐  │
│  │   Auth & Access Control │   │  Installation/Panels │  │
│  └───────────────────────┘   └──────────────────────┘  │
│  ┌───────────────────────┐   ┌──────────────────────┐  │
│  │  Inspection Management│   │  Maintenance Issues  │  │
│  └───────────┬───────────┘   └──────────────────────┘  │
└──────────────┼───────────────────────────┬─────────────┘
               │                           │
┌──────────────▼────────────┐   ┌──────────▼─────────────┐
│    ML Inference Adapter   │   │  Django ORM & Database │
│  ┌─────────────────────┐  │   │  (SQLite / PostgreSQL) │
│  │ Quality/Triage Gate │  │   │                        │
│  └──────────┬──────────┘  │   │  - Users & Sites       │
│             │             │   │  - Panels & Inspections│
│  ┌──────────▼──────────┐  │   │  - Maintenance Issues  │
│  │ Real CNN / Dev Mock │  │   │  - Action Logs         │
│  └─────────────────────┘  │   └────────────────────────┘
│  ┌─────────────────────┐  │
│  │ Priority Rule Engine│  │
│  └─────────────────────┘  │
└───────────────────────────┘
```

### 2.2 User Classes & Personas

SolarGuard supports two primary end-user personas and one administrative persona:

| User Class | Profile & Goals | Key Needs | Technical Complexity |
| :--- | :--- | :--- | :--- |
| **Individual Solar Owner** | Homeowner with a rooftop solar array (4–20 panels). Goal: verify if panels are dirty or damaged without climbing the roof. | Simple dashboard; 1-click photo upload; non-technical plain English advice; no mandatory serial numbers. | Low (Needs approachable UX, clear warnings against climbing onto roofs). |
| **Professional Facility / Site Manager** | Solar farm technician or facility manager maintaining hundreds of panels across commercial sites. | Site-wide filtering; panel serial number tracking; maintenance queue triage (`Open` $\rightarrow$ `Resolved`); exportable audit trails. | Moderate to High (Needs dense tables, batch tracking, status filters). |
| **System Administrator** | College project evaluator, instructor, or system administrator. | Account management, system health metrics, inspecting raw database records via Django Admin. | High (Needs full administrative access). |

### 2.3 Operating Environment
* **Server Operating System:** Windows 10/11, macOS, or Ubuntu Linux 22.04 LTS.
* **Runtime:** Python 3.10 – 3.12.
* **Web Framework:** Django 5.x / 6.x.
* **Database:** SQLite 3 (local development); PostgreSQL 14+ (production).
* **Client Browsers:** Modern standards-compliant browsers (Google Chrome 110+, Mozilla Firefox 110+, Apple Safari 16+, Microsoft Edge 110+).
* **Inference Hardware:** Local CPU inference for deployed web app; Cloud GPU (Google Colab T4) for model training and validation.

---

## 3. Approved Decisions Baseline vs. Unresolved Requirements

To maintain strict academic and engineering integrity, this section clearly demarcates what has been formally approved versus what is currently deferred awaiting audit results.

### 3.1 Approved Architectural Decisions (Baseline)
*(Per [DECISIONS.md](file:///d:/RBU/RBU%20Sem%205/SEPM/Sepm%20Project%20SolarGuard/DECISIONS.md) approved on 2026-10-17)*:
1. **Decision 1 (Maintenance Intelligence):** The unvalidated synthetic Random Forest model is decommissioned. It is replaced by an explainable, deterministic **Rules-Based Maintenance Priority Engine**.
2. **Decision 2 (Target Condition Classes):** Baseline investigation targets 4 conditions: `Normal`, `Dusty`, `Bird-Dropping`, and `Cracked / Surface Damage` (provisional). A mandatory `Unable to assess / Retake photo` outcome is enforced for blurry, dark, or out-of-distribution uploads.
3. **Decision 3 (Audience Separation):** A unified platform supporting both Individual Owners and Professional Teams with distinct views and strict server-side authorization.
4. **Decision 4 (Maintenance Lifecycle):** Full maintenance ticket workflow with statuses `Open`, `In Progress`, and `Resolved`, linked to inspection findings and follow-up inspections.
5. **Decision 5 (Training Strategy):** Deep learning model training is executed off-host in Google Colab using GPU resources; trained lightweight artifacts are integrated for CPU inference.
6. **Decision 6 (Brand Identity):** Adoption of the calm, credible visual language defined in `BRAND_GUIDELINES.md`.

### 3.2 Unresolved Decisions & Open Questions
*(These items are explicitly NOT finalized and MUST NOT be assumed until Gate 2 completes)*:

> [!WARNING]
> **UNRESOLVED DECISION 1: 4th Class Exact Definition (`Cracked` vs. `Surface Damage`)**  
> *Status:* PENDING DATASET AUDIT.  
> *Problem:* Kaggle and academic datasets frequently group shattered glass, cell delamination, burn marks, and micro-cracks under a single folder named `Physical-Damage`. Renaming all of these images to `Cracked` is factually inaccurate.  
> *Action:* Gate 2 audit ([docs/DATA_AUDIT_PLAN.md](file:///d:/RBU/RBU%20Sem%205/SEPM/Sepm%20Project%20SolarGuard/docs/DATA_AUDIT_PLAN.md)) will inspect actual sample images. The label will remain `Cracked / Surface Damage` until verified.

> [!WARNING]
> **UNRESOLVED DECISION 2: Dataset Licensing and Provenance**  
> *Status:* PENDING DATASET AUDIT.  
> *Problem:* The exact distribution rights (CC-BY, Academic Only, Commercial) and provenance of public solar datasets need verification to ensure no copyright or ethical violations in academic submission.

> [!WARNING]
> **UNRESOLVED DECISION 3: Deep Learning Architecture Selection**  
> *Status:* PENDING GATE 2 EXPERIMENTS.  
> *Problem:* Trade-off between a lightweight custom CNN (~4 layers, trained from scratch) versus MobileNetV2 (transfer learning pre-trained on ImageNet).  
> *Resolution Criteria:* Evaluated based on Colab validation macro-F1 score, export size (< 25 MB), and local CPU inference latency (< 2 seconds).

> [!WARNING]
> **UNRESOLVED DECISION 4: Quality & Uncertainty Thresholds**  
> *Status:* PENDING BENCHMARKING.  
> *Problem:* The mathematical cutoffs for triggering `Unable to assess` (e.g., Laplacian variance threshold for blur, brightness histograms for underexposure, and softmax entropy for classification uncertainty) require empirical tuning against real test images.

> [!WARNING]
> **UNRESOLVED DECISION 5: Multi-User Organization Sharing**  
> *Status:* DEFERRED TO POST-V1.  
> *Decision:* In v1, individual ownership is enforced per-user account. Multi-user shared team organizations (e.g., five technicians accessing the same company site) are deferred to keep v1 simple and robust.

---

## 4. Specific Functional Requirements (FR)

### Module 1: User Authentication, Roles, and Data Isolation

#### FR-1.1: User Registration and Account Types
* The system shall allow users to register an account with a unique username, email address, and secure password.
* During registration or initial onboarding, the user shall select their primary account type: **Individual Solar Owner** or **Professional Maintenance User**.
* The system shall allow users to switch their active viewing mode if authorized.

#### FR-1.2: Authentication & Session Security
* The system shall authenticate users using Django's PBKDF2 with SHA-256 password hashing.
* Unauthenticated requests to protected routes (`/dashboard/`, `/inspect/`, `/maintenance/`, `/sites/`) shall redirect to `/login/` with a next-destination parameter.
* The system shall provide secure logout that terminates the user session and invalidates session cookies.

#### FR-1.3: Server-Side Data Isolation (Critical Security Requirement)
* **The system shall enforce data ownership at the database query level for every request.**
* An individual owner or professional user shall strictly only view, inspect, edit, or delete installations, panels, inspections, and maintenance records that belong to their user account.
* Attempting to access another user's inspection record (e.g., via direct URL manipulation `/inspect/result/99/`) shall return an HTTP 403 Forbidden or HTTP 404 Not Found response.
* System Administrators (`is_staff=True`) shall retain global oversight via the Django Admin interface.

---

### Module 2: Installation and Panel Management

#### FR-2.1: Site / Installation Registration
* The system shall allow users to register an Installation/Site with:
  * Name / Nickname (e.g., "Rooftop Array 1", "North Facility Site A") — Mandatory.
  * Street Address / Location — Optional.
  * Installation Date — Optional (defaults to current date if unknown).
  * System Capacity in kW — Optional.
  * Notes / Description — Optional.
* For **Individual Owners**, an installation shall serve as their complete home array, without requiring individual panel definitions.

#### FR-2.2: Individual Panel Inventory (Professional View)
* The system shall allow **Professional Users** to register individual panels belonging to a site with:
  * Serial Number / Identifier (unique within the site) — Mandatory for professional mode.
  * Panel Brand / Model — Optional.
  * Array Zone / Sub-string — Optional.
  * Baseline Dust / Shading Index — Optional.
* The system shall allow editing, updating, and deactivating panels without deleting historical inspection logs.

---

### Module 3: Image Inspection & Triage Engine

#### FR-3.1: Image Upload and Pre-Validation
* The system shall accept image uploads via web form and mobile camera file picker.
* Supported formats shall be restricted to **JPEG (`.jpg`, `.jpeg`)** and **PNG (`.png`)**.
* The system shall reject files larger than **10 MB**.
* **Safety Verification:** The system shall verify image integrity by opening and decoding the image header using Pillow. Corrupted, non-image files, or renamed executables shall be rejected with a user-friendly error message before reaching the ML layer.

#### FR-3.2: Image Pre-Processing & Storage
* The system shall save uploaded images to a secure path (`media/inspections/YYYY/MM/DD/`) with sanitized, randomized file names to prevent directory traversal or file overwrites.
* The system shall generate a standard thumbnail representation for rapid rendering on dashboard summary tables.

#### FR-3.3: Image Quality & "Unable to Assess" Triage
* Before executing defect classification, the system shall evaluate basic image quality metrics:
  * **Blurriness Detection:** Calculate the Laplacian variance of the image. Images scoring below the minimum clarity threshold shall trigger an `Unable to assess` status.
  * **Extreme Lighting Detection:** Calculate mean pixel brightness. Images determined to be pitch-black (< 15/255 mean) or severely overexposed (> 245/255 mean) shall trigger `Unable to assess`.
* When an image is flagged as `Unable to assess`, the system shall:
  * Record the inspection with status `UNABLE_TO_ASSESS`.
  * Display constructive, non-blaming guidance: *"We couldn't assess this image reliably. Please ensure the panel is well-lit, in focus, and captured from a clear, front-facing angle."*
  * Provide an immediate "Retake / Try Another Photo" button.

---

### Module 4: Machine Learning Inference Architecture

#### FR-4.1: Modular Inference Adapter
* The system shall interact with machine learning models strictly through an isolated adapter interface (`ml_engine/adapter.py`).
* The adapter shall provide a standardized method signature:
  ```python
  inspect_panel_image(image_path: str) -> InspectionOutput
  ```
  Returning structured results:
  * `condition_label`: One of `Normal`, `Dusty`, `Bird-Dropping`, `Cracked / Surface Damage`, or `Unable to assess`.
  * `confidence_score`: Float between 0.0 and 1.0 (calibrated if supported, or explicitly marked raw softmax).
  * `model_identifier`: String indicating model version and source (e.g., `mobilenetv2_v1_colab` or `synthetic_dev_mock`).
  * `is_mock`: Boolean flag explicitly indicating whether the inference was generated by a mock model.

#### FR-4.2: Development Mock vs. Real Model Isolation
* **Development Mode:** When no trained deep learning weight file exists on disk, the system shall invoke the Development Mock Adapter.
* **UI Transparency:** If a mock adapter is active, the web interface shall display an unambiguous banner:  
  *⚠️ Development Demonstration: This result was generated using mock statistical logic. Real deep learning weights are pending dataset audit.*
* **Production Integrity:** The system shall never silently substitute synthetic predictions for missing real-model weights without explicit indicator flags.

#### FR-4.3: Defect Class Reporting & Safety Disclaimers
* The system shall display the primary visual finding with standardized, cautious brand language:
  * **Normal:** *"No visible surface anomalies detected in this photograph."* (Never *"Panel is 100% healthy"*).
  * **Dusty:** *"Possible surface dust / soiling accumulation detected. Consider safe cleaning if efficiency has dropped."*
  * **Bird-Dropping:** *"Localized organic deposit detected. Periodic cleaning recommended to prevent hot-spot development."*
  * **Cracked / Surface Damage:** *"Possible visible fracture or surface damage detected. Do not handle electrical components; arrange professional physical inspection."*
* Every inspection report shall include the mandatory safety footer:  
  *ℹ️ SolarGuard visual assessment is an assistive screening tool. It does not certify electrical safety or measure live energy output.*

---

### Module 5: Rules-Based Maintenance Priority Engine

#### FR-5.1: Deterministic Priority Calculation
* The system shall calculate an explainable Maintenance Priority Score using a deterministic, rules-based expert formula (replacing the synthetic Random Forest).
* **Inputs to the Rules Engine:**
  1. **Visual Finding Severity ($S_v$):**
     * Normal: 0 points
     * Dusty: 30 points
     * Bird-Dropping: 45 points
     * Cracked / Surface Damage: 85 points
     * Unable to Assess: 15 points (informational review needed)
  2. **Days Since Last Cleaning ($T_c$):**
     * $< 30$ days: 0 points
     * $30 - 90$ days: 15 points
     * $> 90$ days (or unknown): 30 points
  3. **Panel Age ($A_p$):**
     * $< 2$ years: 5 points
     * $2 - 5$ years: 15 points
     * $> 5$ years: 25 points
  4. **Historical Defect Frequency ($H_d$):**
     * 0 past defects in 6 months: 0 points
     * 1–2 past defects: 15 points
     * $3+$ past defects: 30 points
* **Total Maintenance Priority Index ($MPI$):**
  $$MPI = \min(100, \, S_v \times 0.50 + T_c \times 0.20 + A_p \times 0.15 + H_d \times 0.15)$$

#### FR-5.2: Priority Categorization & Transparency
* The system shall map the calculated $MPI$ to three clear categories:
  * **Low Priority ($MPI < 40$):** Routine monitoring; no immediate intervention required.
  * **Medium Priority ($40 \le MPI < 70$):** Maintenance review recommended within regular service cycle (e.g., scheduled cleaning).
  * **High Priority ($MPI \ge 70$):** Prompt technician attention recommended (e.g., potential physical crack or chronic heavy soiling).
* **Explainability Requirement:** The inspection result page shall break down exactly why this priority was assigned (e.g., *"+42 pts from visual crack finding, +15 pts from 120 days since last cleaning, +8 pts from panel age"*).

---

### Module 6: Maintenance Issue Lifecycle & Follow-up Tracking

#### FR-6.1: Issue Ticket Creation
* From any completed inspection report showing an anomaly (or on user demand), the user shall be able to click **"Log Maintenance Issue"**.
* The issue ticket shall automatically inherit:
  * Linked Installation and/or Panel.
  * Linked Inspection record and inspection photograph.
  * Initial visual finding and priority level.
  * Status set to `Open`.
  * User-specified description, scheduled date, and assigned technician/owner notes.

#### FR-6.2: Issue Status Progression
* The system shall support four standardized lifecycle states:
  * `Open`: Issue created, awaiting review or assignment.
  * `In Progress`: Maintenance work or cleaning currently scheduled or underway.
  * `Resolved`: Action completed and verified.
  * `Needs Review`: Inconclusive follow-up or recurring anomaly.
* Status changes shall be recorded with a timestamp and the user who updated the record.

#### FR-6.3: Maintenance Action Logging
* Authorized users shall be able to append maintenance action records to an issue:
  * Action Type: `Cleaning`, `Physical Repair`, `Wiring/Electrical Check`, `Panel Replacement`, `Routine Inspection`.
  * Performed Date and Performed By (Technician name or "Self").
  * Cost / Incurred Expense (optional).
  * Detailed Notes regarding techniques or materials used.

#### FR-6.4: Verification Follow-up Inspection
* The system shall allow users to upload a **Follow-up Verification Inspection** directly attached to an open or recently resolved issue.
* The system shall display a side-by-side **Before / After** comparison showing:
  * Pre-maintenance photograph, date, and original finding.
  * Post-maintenance photograph, date, and verification finding.
* **Integrity Guardrail:** The system shall **not** automatically mark an issue `Resolved` based solely on a "Normal" prediction from a follow-up image. Resolution requires explicit human confirmation.

---

### Module 7: Dashboards and Visual Reporting

#### FR-7.1: Individual Owner Dashboard
* The Owner Dashboard shall present a streamlined, uncluttered overview:
  * **Quick Inspection Card:** Direct drag-and-drop / camera upload button.
  * **Rooftop Condition Card:** Plain-language summary of latest inspection.
  * **Active Maintenance Reminders:** Cards showing open cleaning or repair reminders.
  * **Recent Inspection History:** Compact timeline of past photo assessments with dates and results.

#### FR-7.2: Professional Fleet Dashboard
* The Professional Dashboard shall present operational facility management metrics:
  * **Fleet Overview KPI Cards:** Total Monitored Panels, Active High-Priority Issues, Open Cleaning Tasks, Inspections Completed this Month.
  * **High-Priority Watchlist:** Filterable list of panels requiring immediate physical attention.
  * **Condition Distribution Chart:** Responsive Chart.js visual breakdown of findings (Normal, Dusty, Bird-Dropping, Cracked/Surface Damage, Unable to Assess).
  * **Filterable Historical Table:** Paginated inspection table filterable by Site, Panel Serial Number, Date Range, and Visual Finding.
  * **Data Integrity:** All charts and KPI cards must derive from real database records; empty states must show clear explanatory text rather than dummy statistics.

---

## 5. Non-Functional Requirements (NFR)

### NFR-1: Performance & Latency
* **NFR-1.1:** The system shall complete image validation, quality triage, and local CPU inference within **3.0 seconds** for an uploaded image up to 5 MB on a standard dual-core laptop processor.
* **NFR-1.2:** Dashboard pages displaying up to 500 inspection records shall load in under **1.5 seconds** using Django ORM optimized queries (`select_related` and pagination).
* **NFR-1.3:** Rules-based maintenance priority calculation shall execute synchronously in under **50 milliseconds**.

### NFR-2: Usability & Accessibility
* **NFR-2.1 (Brand System Alignment):** The UI shall strictly follow the color tokens and typography in `BRAND_GUIDELINES.md` (Forest Green `#176B52`, Solar Gold `#D6A545`, Light Canvas `#F7F9F6`, Deep Slate `#192B27`).
* **NFR-2.2 (Contrast & Accessibility):** All body text, buttons, and alert states shall meet WCAG 2.1 Level AA contrast standards (minimum 4.5:1 for normal text).
* **NFR-2.3 (Information Hierarchy):** Statuses shall never be conveyed by color alone; every badge shall include clear text and descriptive icons.
* **NFR-2.4 (Mobile Responsiveness):** All inspection upload and issue tracking pages shall be fully functional and easily tappable on mobile phone screens (viewport width 360px+).

### NFR-3: Reliability, Error Handling, and Graceful Degradation
* **NFR-3.1:** The system shall never raise an unhandled 500 Internal Server Error when provided invalid, corrupted, or non-image files; descriptive user feedback must be returned.
* **NFR-3.2:** If an ML model weight file fails to load or encounters an inference exception, the system shall log the internal error, alert the user that visual assessment is temporarily unavailable, and preserve the uploaded image and metadata without data loss.
* **NFR-3.3:** The database shall use atomic transactions (`transaction.atomic`) when creating inspections and associated issues to ensure partial failures do not leave orphan records.

### NFR-4: Security and Privacy
* **NFR-4.1 (Secret Management):** `SECRET_KEY`, database credentials, and debug flags shall be loaded from environment variables (`.env`). No production secrets shall exist in version control.
* **NFR-4.2 (Safe Uploads):** Uploaded files shall be validated by reading binary header bytes (magic numbers) and verifying safe image decoding with Pillow, preventing MIME-type spoofing and directory traversal attacks.
* **NFR-4.3 (CSRF Protection):** All state-modifying POST/PUT requests shall enforce Django's built-in Cross-Site Request Forgery (CSRF) token validation.
* **NFR-4.4 (User Privacy):** Uploaded panel photographs and site location details shall be restricted to the authenticated owning user. Direct media URL enumeration shall be mitigated through randomized file naming (`uuid4`).

### NFR-5: Maintainability and Architecture
* **NFR-5.1 (Decoupled Inference):** The application core shall remain independent of machine learning frameworks (TensorFlow, PyTorch, or ONNX). All ML interaction shall pass through `ml_engine/adapter.py`.
* **NFR-5.2 (Test Coverage):** Every major workflow (auth, panel creation, image upload, priority calculation, issue lifecycle) shall have corresponding automated tests in `core/tests.py`.
* **NFR-5.3 (Code Standards):** Python code shall adhere to PEP 8 standards with descriptive docstrings and type annotations on all service methods.

### NFR-6: Academic and SEPM Project Integrity
* **NFR-6.1 (No Fabricated Metrics):** The system documentation, user interface, and presentation materials shall never claim 100% accuracy based on synthetic data.
* **NFR-6.2 (Honest Classification Claims):** The visual classifier shall be presented as an assistive tool operating on visible RGB surface characteristics, not an omniscient sensor.
* **NFR-6.3 (Clear Labeling of Heuristics):** Maintenance priority formulas shall be explicitly documented as an expert deterministic rule engine in project defense vivas.

---

## 6. Data Model Specification (Schema Design)

The revised relational schema connects all entities with explicit ownership and traceability:

```
┌──────────────────┐
│   auth.User      │
│ (Django Builtin) │
└─────────┬────────┘
          │ 1:N
          ▼
┌──────────────────┐       1:N       ┌──────────────────┐
│   Installation   ├────────────────►│      Panel       │
│  (Rooftop/Site)  │                 │  (Serial Number) │
└─────────┬────────┘                 └─────────┬────────┘
          │                                    │
          │ 1:N                                │ 1:N
          ▼                                    ▼
┌───────────────────────────────────────────────────────┐
│                      Inspection                       │
│  - image (media path)                                 │
│  - condition_label (Normal/Dusty/Bird/Crack/Unable)   │
│  - confidence_score                                   │
│  - model_identifier & is_mock_prediction              │
│  - maintenance_priority_score (0-100) & level         │
│  - explainability_breakdown (JSON)                    │
│  - inspected_at (timestamp)                           │
└──────────────────────────┬────────────────────────────┘
                           │ 1:1 or 1:N
                           ▼
┌───────────────────────────────────────────────────────┐
│                   MaintenanceIssue                    │
│  - status (Open, In Progress, Resolved, Needs Review) │
│  - priority (Low, Medium, High)                       │
│  - description & scheduled_date                       │
│  - follow_up_inspection_id (nullable FK)              │
│  - created_at, resolved_at                            │
└──────────────────────────┬────────────────────────────┘
                           │ 1:N
                           ▼
┌───────────────────────────────────────────────────────┐
│                   MaintenanceLog                      │
│  - action_type (Cleaning, Repair, Inspection, Other)  │
│  - performed_at, performed_by                         │
│  - notes, cost                                        │
└───────────────────────────────────────────────────────┘
```

---

## 7. Acceptance Criteria (Definition of Done for v1)

1. **User Experience:** An individual owner can register, create an installation, upload a real panel photo, receive an immediate visual finding and maintenance priority, and log a follow-up action without encountering errors.
2. **Professional Experience:** A professional user can filter multi-panel sites, triage high-priority issues, transition an issue from `Open` to `Resolved`, and view before/after inspection photos.
3. **Data Protection:** User A cannot view, query, or edit User B's installations or inspection photos.
4. **Error Resilience:** Uploading a corrupt file, an unsupported `.exe` or `.txt`, or a pitch-black photo triggers a graceful, user-friendly error or `Unable to assess` message without crashing the server.
5. **Transparency:** All UI results explicitly disclose whether they are generated by a development mock or a validated real-image model, and maintenance priority is fully explained.
6. **Passing Tests:** The automated test suite (`python manage.py test`) runs cleanly with 100% pass rate covering authentication, permissions, upload triage, and priority calculation.
