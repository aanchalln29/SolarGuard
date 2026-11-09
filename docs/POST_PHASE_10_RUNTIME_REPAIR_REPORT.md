# SolarGuard — Post-Phase-10 Critical Runtime Repair Report

**Date:** October 27, 2026  
**System:** SolarGuard PV Asset Health & Maintenance Management Platform  
**Target Artifact:** `ml_models/solarguard_model_v3.keras` (MobileNetV2 CNN v3.0)  
**Status:** FULLY RESOLVED & LIVE VERIFIED  

---

## 1. Executive Summary & Root Cause Analysis

### The Reported Issue
The user experienced the following error upon uploading an inspection image:
```text
Model Unavailable: Failed to load Keras model artifact 'D:\RBU\RBU Sem 5\SEPM\Sepm Project SolarGuard\ml_models\solarguard_model_v3.keras': No module named 'tensorflow'
```
Simultaneously, earlier inspection reports exhibited misleading UI state:
- A green banner stating *"Real CNN Inference Active"*
- Visual Condition showing *"Normal"* despite `confidence_score = 0.0%`
- Priority assigned as *"Routine"* rather than *"Unable to Assess"*

### Root Cause
1. **Interpreter Divergence:**
   - The virtual environment at `.venv\Scripts\python.exe` had `tensorflow==2.21.0` and `keras==3.15.1` installed.
   - When running `python manage.py runserver` from an unactivated terminal or default system shell, Windows resolved `python` to `C:\Python313\python.exe`.
   - The system Python interpreter (`C:\Python313`) had Django 6.1 and Pillow installed, but lacked `tensorflow`.
2. **Permanent Error Latching in `ml_engine/inference.py`:**
   - In `load_model_service()`, if an initial model load failed, `_MODEL_LOAD_ERROR` was stored in memory and an unconditioned check (`if _MODEL_LOAD_ATTEMPTED and not force_reload and _MODEL_LOAD_ERROR: return None, None, _MODEL_LOAD_ERROR`) prevented any subsequent retry attempts for the lifetime of that process.
3. **Flawed Fallback Defaults in Priority Engine & Models:**
   - In `priority_engine.py` and `core/models.py`, any finding that did not match specific fault strings ('damage', 'bird', 'dust') defaulted to `else:` blocks producing `'Normal'` and `'Routine'` maintenance triage.

---

## 2. Environment Alignment & Resolution

### Dependency Installation
Compatible `tensorflow==2.21.0` and `keras==3.15.1` were installed into `C:\Python313\python.exe`:
```bash
python -m pip install "tensorflow==2.21.0"
```
Both environments were verified to load TensorFlow and the MobileNetV2 v3.0 weights:
- **System Python (`C:\Python313\python.exe`):** TensorFlow 2.21.0, Keras 3.15.1
- **Workspace Venv (`.venv\Scripts\python.exe`):** TensorFlow 2.21.0, Keras 3.15.1

### Self-Healing Guard in `manage.py`
Updated `manage.py` to automatically detect if it is being invoked under an interpreter missing TensorFlow or Django, and transparently delegate execution to `.venv\Scripts\python.exe`.

### Removal of Failure Latching in `ml_engine/inference.py`
Removed the static failure latch in `load_model_service()`. When a model is successfully loaded into `_CACHED_MODEL`, it returns instantaneously. If `_CACHED_MODEL` is `None` (such as after a transient failure), it retries loading rather than permanently failing until the process is restarted.

---

## 3. UI & Business Rule Hardening

1. **Deterministic Priority Engine (`ml_engine/priority_engine.py`):**
   - Added Rule 5: Explicitly matches `'unavailable'`, `'offline'`, `'failed'`, and `'error'`. Sets `level='Unable to Assess'`, providing transparent explanation that automated triage is withheld while honoring independent rules (e.g. overdue wash $\ge 90$ days).
   - Rule 6: Strictly requires an explicit `'normal'` or `'clean'` visual finding to assign `'Routine'`.
   - Rule 7: Catch-all returns `'Unable to Assess'`.
2. **Derived Visual Condition (`core/models.py`):**
   - In `get_derived_condition()`, catches model downtime and returns `status='review'`, `category='Inspection Needs Review'`, `label='AI Model Unavailable — Needs Review'`, and `confidence=0.0`.
3. **Inspection Result Page (`core/templates/core/result.html`):**
   - Replaced false "Real CNN Inference Active" banner with a high-visibility warning alert: *"AI Model Unavailable — Inspection Needs Review"* with a direct *"Retry Inspection"* button.
   - Visual finding displays *"Unable to Determine Visual Condition"*.
   - Confidence score displays *"N/A (Inference Offline)"*.

---

## 4. Historical Database Audit & Remediation Tool

### Database Audit & Remediation Execution
An audit identified 8 historical inspection records created during model downtime:
- **Inspections #40, #41, #42, #47:** Panel `SG-10-P001` with `predicted_class='Model Unavailable'`, `confidence_score=0.0`, and erroneous prior priority `'Routine'`.
- **Inspections #50, #51, #52, #53:** Created during test runs with `predicted_class='AI Model Unavailable'`, `confidence_score=0.0`, and priority `'Unable to Assess'`.
- **Remediation Outcome (Executed):** All 8 records were re-evaluated with real MobileNetV2 CNN v3.0 inference using `python manage.py remediate_failed_inspections --mode reevaluate`.
  - Record #40: `Surface-Damage` (76.3%), Priority: `Manual Inspection Recommended`
  - Record #41: `Dusty` (91.1%), Priority: `Cleaning Recommended`
  - Record #42: `Surface-Damage` (52.8%), Priority: `Manual Inspection Recommended`
  - Record #47: `Dusty` (91.1%), Priority: `Cleaning Recommended`
  - Records #50, #51, #52: `Dusty` (91.1%), Priority: `Cleaning Recommended`
  - Record #53: `Surface-Damage` (59.3%), Priority: `Manual Inspection Recommended`
- **Subsequent Audit:** Re-running `python manage.py remediate_failed_inspections --mode audit` verified **0 suspect records remain**. The database is clean.

### Management Command: `remediate_failed_inspections`
Created `core/management/commands/remediate_failed_inspections.py` supporting three operational modes:
- `--mode audit`: Inspects suspect records and verifies file existence on disk.
- `--mode mark_offline`: Formally updates legacy records to `AI Model Unavailable`, `Unable to Assess`, and `review_status='flagged'`.
- `--mode reevaluate`: Re-runs real MobileNetV2 CNN v3.0 inference against original photos, recomputes priority rules, and appends an immutable remediation audit note.
- `--dry-run`: Allows non-destructive simulation before committing changes.

---

## 5. Verification & Test Evidence

### 1. Regression Test Suite
Executed `python manage.py test core.test_runtime_repair`:
```text
Found 8 test(s).
........
----------------------------------------------------------------------
Ran 8 tests in 4.764s

OK
```
All 8 test assertions passed:
- `test_1_tensorflow_and_keras_import_cleanly`
- `test_2_mobilenet_v3_model_loads_without_error`
- `test_3_single_image_inference_returns_valid_output`
- `test_4_failed_inference_never_results_in_normal_condition`
- `test_5_failed_inference_never_results_in_routine_priority`
- `test_6_real_cnn_inference_active_banner_only_appears_when_appropriate`
- `test_7_failed_inference_displays_needs_review_and_retry_button`
- `test_8_failed_inference_sets_review_status_flagged`

### 2. Live HTTP End-to-End Verification
Executed `scratch/verify_live_inspection.py` against active server on `127.0.0.1:8000`:
- **Inspection #56** created:
  - Banner: `Real CNN Inference Active: MobileNetV2 CNN v3.0`
  - Visual Finding: `Surface-Damage`
  - Softmax Confidence: `59.3%`
  - Maintenance Priority: `Manual Inspection Recommended`
  - Zero load errors, zero fallback warnings.
