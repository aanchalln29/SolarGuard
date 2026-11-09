# SolarGuard — System Instructions for Antigravity

**Status:** Working project charter, not a finalized SRS.  
**Project:** SolarGuard — AI-Assisted Solar Panel Inspection & Maintenance Platform  
**Owners:** Tanushree Burde and Aanchal Nasre (per initial SRS).

## 1. Mission
Build a trustworthy, product-style web platform for both individual solar panel owners and professional maintenance teams. Users should be able to inspect visible panel conditions using uploaded RGB photographs, track installations and maintenance activities, and review inspection history and trends.

The AI is an **assistive visual assessment**, not proof of electrical safety, actual energy loss, remaining useful life, or a substitute for professional inspection.

## 2. Source of truth and precedence
1. Explicit decisions approved by the project owner in the current task.
2. Approved, revised SRS (once available).
3. This system-instructions file and `BRAND_GUIDELINES.md`.
4. Initial SRS, as historical reference only.
5. Existing MVP code, as implementation evidence, not automatically the desired architecture.

When sources conflict or a requirement is unclear, **document the conflict and ask before implementing**. Do not silently invent requirements or assert that provisional decisions are final.

## 3. Current approved direction
- Hybrid AI inspection + maintenance tracking.
- Two primary audiences: individual owners and professional maintenance teams/facility managers.
- Initial visual-condition investigation: **Normal, Dusty, Cracked, Bird-Dropping**. Final labels are **not yet approved**; dataset audit comes first.
- Product-style application with simple owner workflows and professional site/panel workflows.
- True degradation forecasting is **not an approved v1 feature**. The initial SRS's Random Forest trained on heuristic data must not be represented as validated degradation prediction.
- Initial maintenance priority, if implemented, must be transparent, explainable, and labeled as rules-based until independently validated.
- No real-time video, autonomous cleaning, drone integration, thermal or electrical diagnosis in v1.

## 4. Required product capabilities (proposed v1)
### 4.1 Accounts and access
- Secure authentication, session handling, logout, and account ownership.
- Individual owner: simple setup and personal installation/inspection history.
- Professional user: manage sites, panels, inspections, and maintenance activities.
- Administrator: manage authorized accounts and system configuration.
- Enforce authorization in the backend for every data access. Users must not access other users' or organizations' records.

### 4.2 Installations and panels
- Register installations/sites and optionally individual panels.
- Store relevant metadata, such as installation date, location, panel identifier, and notes when available.
- Avoid making unknown serial numbers or dates mandatory for household users.
- Support editing and deactivation with appropriate permissions.

### 4.3 Image inspection
- Upload JPEG/PNG with file type, file size, and image decode validation.
- Associate an inspection with an installation or panel where possible.
- Preprocess images consistently with the model's recorded training configuration.
- Display supported visual finding(s), confidence when calibrated, limitations, and next-step guidance.
- Provide **Unable to assess / Retake photo** for invalid, unsuitable, or sufficiently uncertain inputs; do not automatically call them Normal.
- Handle inference failures without losing valid records or misleading the user.
- A single-label classifier is the provisional baseline; multi-label classification is a future decision contingent on verified annotations.

### 4.4 Maintenance lifecycle
- Create a maintenance issue or recommended follow-up from a relevant inspection.
- Allow authorized users to record cleaning, repair, notes, dates, and issue status.
- Support a follow-up inspection and retain before/after history.
- Do not mark a problem resolved automatically from a prediction alone.

### 4.5 Dashboards
- Owner: recent inspections, open issues, maintenance history, clear next actions.
- Professional: site/panel lists, filters, unresolved issues, inspection trends, and fault summaries.
- Charts must use real persisted data; show meaningful empty states instead of fake statistics.

## 5. ML and dataset rules
- **Do not fabricate datasets, model weights, evaluation metrics, confidence scores, or working predictions.**
- Before training: inventory dataset sources, exact image counts per class, image licenses, original provenance, resolution, quality, duplicates, class definitions, and ambiguous labels.
- Do not rename a broad **Physical Damage** category to **Cracked** without image-level verification.
- Do not assume datasets with similar published image counts are independent; detect duplicates and source overlap.
- Keep original data separate from derived/processed data and record dataset version and class mapping.
- Use group-aware, leakage-resistant train/validation/test splits. Never augment validation/test samples to inflate evaluation.
- Baselines to compare after dataset approval: small CNN and a pretrained lightweight model (e.g., MobileNetV2). EfficientNetB0 is optional.
- Evaluate per-class precision, recall, macro-F1, confusion matrix, uncertainty, model size, and CPU inference latency. Pay special attention to missed cracks.
- Model thresholds, preprocessing, labels, and artifact versions must be stored together.
- Do not claim a model is production-ready solely from one random split or synthetic-data accuracy.
- Heavy training and dataset preprocessing should run on cloud GPU resources (e.g., Colab/Kaggle), not the owner's older laptop. Local machine handles development and lightweight tests.
- Keep datasets, credentials, and large checkpoints out of Git. Never require the user to upload all data to the local machine.

## 6. Architecture — provisional, verify against MVP
The initial SRS proposes Django, Django templates, Django ORM, SQLite for development, PostgreSQL for production, TensorFlow/Keras for image inference, scikit-learn for tabular experiments, and Plotly for charts. **Prefer reusing this stack where it is functional, but do not rebuild or change frameworks without a written trade-off analysis and owner approval.**

Keep clear boundaries between:
- Authentication and authorization
- Installation/panel management
- Inspection orchestration and storage
- ML inference adapter (replaceable, versioned)
- Maintenance issue tracking
- Dashboard/analytics

Develop against a documented inference contract. While no approved trained model exists, use an **explicitly labeled demo/mock adapter only in development**; it must never masquerade as a real prediction in production.

Suggested entities to refine during architecture review: User, Organization/Membership (if needed), Site/Installation, Panel, Inspection, Prediction/ModelVersion, MaintenanceIssue, MaintenanceAction. Include timestamps and ownership. Do not implement this schema until reviewed.

## 7. Security, privacy, and reliability
- Validate uploads by content as well as extension; limit file size and decompression risk.
- Store uploads privately, use randomized storage names, and apply access controls.
- Avoid exposing user images or personal installation details to unrelated accounts.
- Use environment variables for secrets; never commit keys, passwords, `.env`, database dumps, or personal photos.
- Use framework-supported password hashing, CSRF protection, secure cookies where appropriate, and server-side authorization.
- Add structured error handling, basic logging without sensitive image data, and tests for permissions and upload failures.
- Provide deletion/retention behavior for user images and account data as a design decision before deployment.

## 8. Engineering workflow — mandatory
### Step 0: Inspect, don't rewrite
Before changing any code:
1. Inspect the repository structure, README, requirements, models, database, and existing UI.
2. Identify what works, what is broken, missing model files, and whether the existing MVP should be retained.
3. Report dependencies, security issues, and likely local CPU/storage bottlenecks.
4. Create `docs/PROJECT_AUDIT.md` and a proposed milestone plan.
5. Ask for approval before migrations, framework changes, bulk refactors, or deleting files.

### Step 1: Requirements gate
Create/update `docs/DECISIONS.md`, `docs/OPEN_QUESTIONS.md`, and a proposed revised SRS. Do not pretend unapproved decisions are final.

### Step 2: Data gate
Audit real dataset files and licenses; propose class labels and an evaluation plan. **No final model architecture or accuracy claims before this gate.**

### Step 3: Foundation gate
Implement accounts, panel/site management, inspection storage, and maintenance tracking in small commits with tests.

### Step 4: Model gate
Train externally, evaluate, export model artifact and metadata, integrate inference behind an adapter, test CPU performance.

### Step 5: Release gate
Perform end-to-end testing, accessibility review, security checks, deployment configuration, and documentation.

For every coding task: first state objective, affected files, assumptions, acceptance criteria, and test plan. Make the smallest practical change. Run available tests. Report exactly what passed, failed, or could not be tested. Never claim a feature is complete without evidence.

## 9. Agent collaboration
- Antigravity: primary codebase implementation and local testing.
- ChatGPT: planning, architecture review, ML/data reasoning, and requirement clarification.
- Claude: optional independent code/design review.
- Git repository and approved docs are the source of truth, **not any agent's chat history**.
- Work on one branch/task at a time; use meaningful commits. Do not let multiple agents concurrently overwrite the same files.

## 10. First instruction to Antigravity
**Do not build SolarGuard yet.** Read this file, `BRAND_GUIDELINES.md`, the initial SRS, and the existing repository. Produce a current-state audit, proposed architecture, gaps, dataset questions, and a phased implementation plan. Identify every decision that requires owner approval. Do not modify source files until the audit is reviewed.
