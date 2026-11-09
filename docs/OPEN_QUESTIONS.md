# SolarGuard — Open Architecture & Requirements Questions

**Project:** SolarGuard — AI-Assisted Solar Panel Inspection & Maintenance Platform  
**Target Owners:** Tanushree Burde and Aanchal Nasre  
**Date:** October 2026  
**Status:** Awaiting Project Owner Decisions Before Code Implementation  

---

## Purpose of this Document
In software engineering (SEPM), building features on unverified assumptions leads to rework, confusion during project evaluations, and academic vulnerability. This document lists the core design and architectural decisions that require **explicit owner approval** before proceeding to write or modify application code.

Please review each question below. You can answer them directly in our discussion.

---

### Question 1: Degradation Prediction vs. Maintenance Priority Rules Engine
* **Background:** The initial SRS proposed a "Random Forest Degradation Prediction Model" trained on heuristic/synthetic numbers to output a "Degradation Probability %". However, `SYSTEM_INSTRUCTIONS.md` specifically notes that predicting true physical degradation from synthetic tabular data is unvalidated and should not be presented as genuine predictive machine learning during academic evaluation.
* **Options:**
  - **Option A (Recommended):** Rebrand and implement this component as a **Rules-Based Maintenance Priority Engine**. It transparently calculates an explainable risk score (Low, Medium, High) based on panel age, operating temperature, soiling intervals, and past faults. In your SEPM project viva, this is defended as an honest, deterministic expert system.
  - **Option B:** Keep the Random Forest model trained on synthetic equations, but clearly label it in the UI and documentation as an "Experimental / Academic Heuristic ML Demonstration".
* **Your Decision:** `[ ] Option A (Recommended) | [ ] Option B`

---

### Question 2: Vision Defect Classes & Handling Unsuitable Images
* **Background:** The initial SRS targets 4 visual conditions: `Normal`, `Dusty`, `Bird-Dropping`, and `Cracked`. However, real-world solar datasets on Kaggle often label damage as `Physical-Damage` (which includes shattering, frame bends, and cell delamination, not just micro-cracks). Furthermore, if a user uploads a blurry photo, a landscape, or a photo taken in the dark, the current system forces a guess instead of warning the user.
* **Options:**
  - **Option A (Recommended):** Adopt the 4 baseline classes (`Normal`, `Dusty`, `Bird-Dropping`, `Cracked / Surface Damage`) and add a mandatory **"Unable to assess / Retake photo"** fallback when image clarity, lighting, or model confidence is too low.
  - **Option B:** Expand to 6 classes matching Kaggle's full dataset (`Clean`, `Dusty`, `Bird-Dropping`, `Physical-Damage`, `Electrical-Burn`, `Snow-Covered`).
* **Your Decision:** `[ ] Option A (Recommended) | [ ] Option B`

---

### Question 3: User Roles & Audience Scope for Version 1
* **Background:** `SYSTEM_INSTRUCTIONS.md` and `BRAND_GUIDELINES.md` specify two distinct user types:
  1. **Individual Solar Owner:** Needs a simple flow (select home array → upload photo → see plain English advice like "clean with water" → save history). Does not know or have complex serial numbers, tilt angles, or dust indices.
  2. **Professional Facility / Site Manager:** Needs multi-panel site lists, filters, high-risk watchlists, serial numbers, and maintenance team dispatch tracking.
* **Options:**
  - **Option A (Recommended):** Single unified platform with a toggle or role setting upon login (`Individual Owner View` vs. `Professional Fleet View`). Owner view hides complex telemetry fields; Professional view enables detailed arrays, serial numbers, and fleet tables.
  - **Option B:** Focus exclusively on the **Professional / Maintenance Team** perspective for the SEPM submission (keeps the current fleet dashboard focus, but adds direct panel creation and issue tracking).
* **Your Decision:** `[ ] Option A (Recommended) | [ ] Option B`

---

### Question 4: Maintenance Lifecycle & Issue Tracking
* **Background:** In the current prototype, `MaintenanceLog` exists in the database but cannot be accessed or created from the website (only via Django Admin). When an inspection detects a crack or heavy soiling, there is no way to create an "Issue Ticket" or track its progress.
* **Options:**
  - **Option A (Recommended):** Implement an intuitive Issue & Maintenance tracking workflow:
    1. An inspection detecting a fault allows the user to click **"Log Maintenance Issue"** (Status: `Open`).
    2. A technician or owner records actions taken (e.g., "Cleaned on Oct 18", Status: `In Progress` or `Resolved`).
    3. The user can upload a follow-up inspection photo to verify the panel is now clean/fixed.
  - **Option B:** Keep a simple read-only log table where users simply record dates and notes without an active status lifecycle.
* **Your Decision:** `[ ] Option A (Recommended) | [ ] Option B`

---

### Question 5: Model Training Strategy & Hardware Limits
* **Background:** Deep learning models (CNNs) require significant computation to train. Running training scripts locally on low-RAM dual/quad-core laptop CPUs can cause freezing, battery drain, or environment library conflicts (like TensorFlow with NumPy 2.x on Windows).
* **Options:**
  - **Option A (Recommended):** Develop a Google Colab notebook (free cloud GPU) for training the CNN on the real Kaggle solar dataset. Train there, export the lightweight model weights (`.keras` / `.h5`) and class metadata, and commit the small trained model file into the local repository for instant local CPU inference.
  - **Option B:** Train a lightweight Scikit-Learn or MobileNet model entirely on your local machine if hardware permits.
* **Your Decision:** `[ ] Option A (Recommended) | [ ] Option B`

---

### Question 6: Brand Identity & UI Aesthetic
* **Background:** The current UI uses standard Bootstrap dark grey navigation with bright blue buttons. `BRAND_GUIDELINES.md` proposes an elegant, calm, trustworthy visual design tailored for solar energy:
  - Deep Forest Green (`#176B52`) for primary actions and active navigation.
  - Solar Gold (`#D6A545`) for restrained solar accents and high-priority highlights.
  - Soft Light Canvas (`#F7F9F6`) and clean white cards (`#FFFFFF`).
  - Dark Slate (`#192B27`) for high-contrast, readable typography.
* **Options:**
  - **Option A (Recommended):** Adopt the `BRAND_GUIDELINES.md` visual system and design tokens across all templates.
  - **Option B:** Keep the standard Bootstrap blue/dark theme.
* **Your Decision:** `[ ] Option A (Recommended) | [ ] Option B`

---

## Summary of Next Actions Once Approved
Once you provide your preferences for these questions, we will:
1. Create `docs/DECISIONS.md` recording your approved choices as the official baseline.
2. Draft the proposed updated SRS reflecting these agreed boundaries.
3. Proceed to **Step 2 (Data Gate)** and **Step 3 (Foundation Gate)** to build out the approved features.
