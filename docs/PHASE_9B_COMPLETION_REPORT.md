# SolarGuard Phase 9B — Model Verification, Safety Review & Backend Hardening Completion Report

**Date:** October 26, 2026  
**Module:** Machine Learning Engine (`ml_engine`) & Core Application (`core`)  
**Task:** Phase 9B — Verify Retraining Results, Surface-Damage Safety Review, Model Acceptance Gate, Safe Versioned Integration & Backend Hardening  
**Active Production Model:** MobileNetV2 v3.0 (`ml_models/solarguard_model_v3.keras`) — **RETAINED AS ACTIVE**  
**Staged Model Artifact:** MobileNetV2 v3.1 Candidate 2 (`ml_models/solarguard_model_v3_1.keras`)  
**Status:** Verification Complete — Candidate 1 Rejected at Safety Gate; v3.0 Retained Active; Backend Fully Hardened; All Tests Passing (Awaiting Approval)

---

## Executive Summary

Phase 9B conducted an exhaustive, empirical verification of the model retraining results from Phase 9A, performed a rigorous Surface-Damage safety review, executed the formal Model Acceptance Gate, implemented configurable versioned model infrastructure, and hardened the AI backend.

### Key Decisions & Findings:
1. **Candidate 1 (Baseline) is REJECTED at the Acceptance Gate**:
   - Although Candidate 1 improved overall test accuracy from 88.04% to 91.13%, its **Surface-Damage recall degraded significantly from 81.82% to 72.73%**, increasing false negatives from 6 to 9 missed damaged panels.
   - Critically, Candidate 1 misclassified **2 physically damaged panels as clean "Normal" with $>60\%$ confidence** (`1-52-_jpg.rf.2267d4f6c0cbb35f0d6af81e457685a6.jpg` at 74.2% conf, and `Physical_Damge_277_jpg.rf.3d186713f8ab64e52b0ce5533c325791.jpg` at 60.2% conf).
   - In solar maintenance operations, physical damage represents electrical arcing, hot-spot, and fire hazards. Concealing physical damage as "Normal" is an unacceptable safety failure.
2. **Active Production Model Remains MobileNetV2 v3.0**:
   - In strict adherence to the safety gate mandate (*"If approval criteria are not satisfied, do not change the active model"*), `ml_models/solarguard_model_v3.keras` and its companion metadata `ml_models/model_metadata_v3.json` remain the default active production model.
3. **Candidate 2 (Class-Weighted) is Staged as Qualified Candidate for v3.1**:
   - Candidate 2 achieved **87.88% Surface-Damage recall** (29 out of 33 detected — highest of all candidates), with **zero damaged panels missed as Normal or Dusty** (all 4 false negatives were called Bird-Dropping, ensuring an anomaly is always flagged).
   - Candidate 2 cut Bird-Dropping false positives by **50%** (FP dropped from 24 to 12, precision rose to 58.62%), achieved **90.93% overall test accuracy**, and **0.8179 Macro F1**.
   - It is staged in `ml_models/solarguard_model_v3_1.keras` with complete verified metadata in `ml_models/model_metadata_v3_1.json`.
4. **Backend Hardening & 60% Confidence Review Policy Fully Implemented**:
   - Thread-safe lazy loading with `threading.Lock()` across model loading and version switching.
   - Validated 60% confidence review threshold active across settings, views, and derived condition calculations.
   - Predictions below 60% confidence or with contested margins are automatically flagged (`review_status = 'flagged'`) and labeled **"Needs Review"** (never "Appears Normal").
   - Atomic database transactions wrap inspection saves, eliminating partial/orphaned records.
   - Early RBAC and retired panel protection implemented on inspection uploads.

---

## Part A — Corrected Metric Comparison & Anomaly Resolution

### 1. Recomputed Benchmark Metrics (Frozen Test Set — 485 Images)

Both models and all candidates were evaluated from raw archive images using identical preprocessing (`ImageOps.exif_transpose`, RGB, bilinear resize to $224 \times 224$, float32 $[0, 255]$ with internal model rescaling):

| Model / Checkpoint | Test Acc | Macro F1 | Weighted F1 | BD Prec | BD Rec | BD F1 | Dusty F1 | Normal F1 | SD Prec | SD Rec | SD F1 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **Active v3.0 (Current)** | 88.04% | 0.7988 | 0.8804 | 45.45% | **80.00%** | 57.97% | 84.36% | 94.12% | **84.38%** | 81.82% | **83.08%** |
| **Candidate 1 (Baseline)** ❌ | 91.13% | 0.8160 | 0.9087 | **77.78%** | 56.00% | 65.12% | 89.33% | 95.74% | 80.00% | 72.73% | 76.19% |
| **Candidate 2 (Class-Weighted)** 🌟 | 90.93% | 0.8179 | 0.9085 | 58.62% | 68.00% | 63.00% | 89.97% | 95.84% | 70.73% | **87.88%** | 78.38% |
| **Candidate 3 (Focal Loss)** | 90.52% | 0.8255 | 0.9042 | 62.07% | 72.00% | 66.67% | 88.81% | 95.26% | 72.50% | 87.88% | 79.45% |
| **Candidate 4 (Aug + Weighted)** | **91.55%** | **0.8327** | **0.9148** | 62.07% | 72.00% | 66.67% | **90.24%** | **96.17%** | 75.68% | 84.85% | 80.00% |

### 2. Recalculated Per-Class Confusion Matrix Metrics

#### Active Model v3.0 (485 Test Images):
- **Bird-Dropping** ($N=25$): $\text{TP}=20, \text{FP}=24, \text{FN}=5, \text{TN}=436 \implies \text{Prec}=45.45\%, \text{Rec}=80.00\%, \text{F1}=57.97\%$
- **Dusty** ($N=149$): $\text{TP}=116, \text{FP}=10, \text{FN}=33, \text{TN}=326 \implies \text{Prec}=92.06\%, \text{Rec}=77.85\%, \text{F1}=84.36\%$
- **Normal** ($N=278$): $\text{TP}=264, \text{FP}=19, \text{FN}=14, \text{TN}=181 \implies \text{Prec}=93.29\%, \text{Rec}=94.96\%, \text{F1}=94.12\%$
- **Surface-Damage** ($N=33$): $\text{TP}=27, \text{FP}=5, \text{FN}=6, \text{TN}=447 \implies \text{Prec}=84.38\%, \text{Rec}=81.82\%, \text{F1}=83.08\%$

#### Candidate 1 (Baseline — 485 Test Images):
- **Bird-Dropping** ($N=25$): $\text{TP}=14, \text{FP}=4, \text{FN}=11, \text{TN}=456 \implies \text{Prec}=77.78\%, \text{Rec}=56.00\%, \text{F1}=65.12\%$
- **Dusty** ($N=149$): $\text{TP}=134, \text{FP}=17, \text{FN}=15, \text{TN}=319 \implies \text{Prec}=88.74\%, \text{Rec}=89.93\%, \text{F1}=89.33\%$
- **Normal** ($N=278$): $\text{TP}=270, \text{FP}=16, \text{FN}=8, \text{TN}=184 \implies \text{Prec}=94.41\%, \text{Rec}=97.12\%, \text{F1}=95.74\%$
- **Surface-Damage** ($N=33$): $\text{TP}=24, \text{FP}=6, \text{FN}=9, \text{TN}=446 \implies \text{Prec}=80.00\%, \text{Rec}=72.73\%, \text{F1}=76.19\%$

#### Candidate 2 (Class-Weighted — 485 Test Images):
- **Bird-Dropping** ($N=25$): $\text{TP}=17, \text{FP}=12, \text{FN}=8, \text{TN}=448 \implies \text{Prec}=58.62\%, \text{Rec}=68.00\%, \text{F1}=63.00\%$
- **Dusty** ($N=149$): $\text{TP}=130, \text{FP}=10, \text{FN}=19, \text{TN}=326 \implies \text{Prec}=92.86\%, \text{Rec}=87.25\%, \text{F1}=89.97\%$
- **Normal** ($N=278$): $\text{TP}=265, \text{FP}=10, \text{FN}=13, \text{TN}=190 \implies \text{Prec}=96.36\%, \text{Rec}=95.32\%, \text{F1}=95.84\%$
- **Surface-Damage** ($N=33$): $\text{TP}=29, \text{FP}=12, \text{FN}=4, \text{TN}=440 \implies \text{Prec}=70.73\%, \text{Rec}=87.88\%, \text{F1}=78.38\%$

### 3. Investigation of the Bird-Dropping Inconsistency

The Phase 9A report highlighted: *"Total False Alarms for Bird-Dropping: 4 (Precision: 77.78% — 83% reduction in false alarms!)"*.

Our investigation confirms the exact mathematical explanation:
- **True Positives (TP)** = 14
- **False Positives (FP, False Alarms)** = 4 (3 Dusty panels + 1 Surface-Damage panel called Bird-Dropping)
- **Total Times Model Predicted Bird-Dropping** = $\text{TP} + \text{FP} = 14 + 4 = 18$
- $\text{Precision} = \frac{\text{TP}}{\text{TP} + \text{FP}} = \frac{14}{18} = 77.78\%$
- **False Negatives (FN, Missed Bird-Droppings)** = 11 (6 called Dusty, 3 called Normal, 2 called Surface-Damage)
- $\text{Recall} = \frac{\text{TP}}{\text{TP} + \text{FN}} = \frac{14}{25} = 56.00\%$

**Correction of Phase 9A Statement:**  
While claiming "only four false alarms" was mathematically correct regarding False Positives, it omitted the operational trade-off: **Candidate 1 became aggressively conservative**. False alarms dropped by 83%, but it failed to detect 11 out of 25 bird droppings (recall dropped by 24 percentage points). Presenting this as an unqualified victory in Phase 9A was misleading.

---

## Part B — Surface-Damage Safety Review

### 1. Root Cause of Surface-Damage F1 Drop (83.08% $\rightarrow$ 76.19%)

Candidate 1 experienced degradation in both precision and recall on Surface-Damage:
- **Recall fell from 81.82% to 72.73%**: Candidate 1 correctly identified only 24 of 33 damaged panels, missing 9 panels.
- **Precision fell from 84.38% to 80.00%**: 6 false alarms were generated.

### 2. Inspection of Misclassified Damaged Panels

We traced the fate of the 33 true Surface-Damage test images across all models:

| Destination of 33 True Damaged Panels | Active v3.0 | Candidate 1 (Baseline) | Candidate 2 (Class-Weighted) |
|---|---|---|---|
| **Correctly Detected as Damaged (TP)** | **27 (81.8%)** | **24 (72.7%)** | **29 (87.9%)** |
| Misclassified as Bird-Dropping | 4 | 1 | 4 |
| Misclassified as Dusty | 1 | 6 | **0** |
| **Misclassified as Normal (Clean)** | **1** | **2 (CRITICAL RISK)** | **0 (SAFE)** |
| **Total False Negatives (Missed)** | **6** | **9 (+50% increase)** | **4 (-33% reduction)** |

#### Specific Misclassified Panels under Candidate 1:
1. `train/images/1-52-_jpg.rf.2267d4f6c0cbb35f0d6af81e457685a6.jpg`: True Surface-Damage $\rightarrow$ **Predicted Normal (74.2% confidence)**.
2. `train/images/Physical_Damge_277_jpg.rf.3d186713f8ab64e52b0ce5533c325791.jpg`: True Surface-Damage $\rightarrow$ **Predicted Normal (60.2% confidence)**.
3. `train/images/Physical_Damge_330_jpg.rf.1360d6b8aac99d441d0ec615a8fe3b0d.jpg`: True Surface-Damage $\rightarrow$ Predicted Dusty (78.0% confidence).
4. `test/images/1-74-_jpg.rf.1c539b6ef13e6f687d1ee72c0effe397.jpg`: True Surface-Damage $\rightarrow$ Predicted Dusty (61.2% confidence).

### 3. Safety Hazard Assessment

In solar farm operations, a panel with surface damage (cracked cover glass, microcracks, busbar fracture, or backsheet delamination) is at imminent risk of moisture ingress, electrical insulation breakdown, reverse-bias thermal runaway, and electrical fire.

- When Candidate 1 labels a damaged panel as **"Normal"**, operators receive zero notification, and the panel continues operating under hazardous conditions.
- When Candidate 1 labels a damaged panel as **"Dusty"**, operators schedule a wash cycle; a washing technician spraying pressurized water onto a cracked high-voltage panel faces severe electrical shock hazards.
- By contrast, **Candidate 2 missed zero damaged panels as Normal and zero as Dusty**. All 4 of its missed panels were labeled Bird-Dropping, meaning every single damaged panel triggers an anomaly alert requiring physical technician presence.

**Conclusion:** Candidate 1's trade-off (sacrificing Surface-Damage recall for higher overall accuracy) is **wholly unacceptable for a maintenance screening tool**.

---

## Part C — Model Acceptance Gate Decision

| Criteria | Required Threshold | Active v3.0 | Candidate 1 | Candidate 2 | Gate Result |
|---|---|---|---|---|---|
| **Overall Accuracy** | $\ge 88.0\%$ | 88.04% | 91.13% | 90.93% | Candidate 1 & 2 pass |
| **Macro F1** | $\ge 0.800$ | 0.7988 | 0.8160 | 0.8179 | Candidate 1 & 2 pass |
| **Surface-Damage Recall** | $\ge 81.8\%$ (no degradation) | 81.82% | **72.73% (FAIL)** | **87.88% (PASS)** | **Candidate 1 FAILS** |
| **Surface-Damage False Negatives as Normal** | $\le 1$ | 1 | **2 (FAIL)** | **0 (PASS)** | **Candidate 1 FAILS** |
| **Bird-Dropping Precision** | $> 50.0\%$ | 45.45% | 77.78% | 58.62% | Candidate 1 & 2 pass |

### Formal Decision:
1. **REJECT Candidate 1 for v3.1 deployment.**
2. **RETAIN MobileNetV2 v3.0 (`solarguard_model_v3.keras`) as the active production model.**
3. **STAGE Candidate 2 (Class-Weighted) as the validated candidate for v3.1.**

---

## Part D — Safe Versioned Model Integration

To ensure production safety without altering active behaviour, versioned model architecture was implemented:

1. **Active Weights Untouched:** `ml_models/solarguard_model_v3.keras` and `ml_models/model_metadata_v3.json` were **not modified, overwritten, or renamed**.
2. **Versioned Artifact Staging:** Candidate 2 was copied to `ml_models/solarguard_model_v3_1.keras` (SHA256: `D5D27E9FF82B007DAD680DB788DC4652CCF53EE7AAF0FB5CBBD72A327F2E22A5`).
3. **Companion Metadata JSON:** Created `ml_models/model_metadata_v3_1.json` containing verified test benchmark metrics (90.93% accuracy, 0.8179 macro F1, 87.88% surface recall, 58.62% bird precision), model hash, 224x224 RGB input shape, and evaluation limitations.
4. **Configurable Model Catalog:** `solarguard_project/settings.py` and `ml_engine/inference.py` support version keys `'v1'`, `'v2'`, `'v3'`, and `'v3.1'`, defaulting safely to `'v3'`.
5. **Historical Inspection Immutability:** Historical inspection records retain their original `model_identifier` (e.g. `MobileNetV2 CNN v3.0`) and predictions; deploying v3.1 will never re-evaluate past inspections.

---

## Part E — Confidence Review Policy (60% Threshold)

### 1. Empirical Validation on Validation Split (482 Images)

| Confidence Interval | Sample Count | Empirical Accuracy | Operational Classification |
|---|---|---|---|
| **$0\% - 50\%$** | 16 | **43.8%** | Highly Uncertain — Mandatory Review |
| **$50\% - 60\%$** | 16 | **43.8%** | Overconfident Error Zone — Mandatory Review |
| **$60\% - 70\%$** | 25 | **80.0%** | Reliable Screen |
| **$70\% - 80\%$** | 31 | **67.7%** | Acceptable |
| **$80\% - 90\%$** | 30 | **93.3%** | Highly Reliable |
| **$90\% - 100\%$** | 364 | **97.8%** | Extremely Reliable |

### 2. Policy Implementation
- **Review Rate:** Only **6.6%** of all inspections exhibit confidence $<60.0\%$.
- **Error Interception:** By routing $<60\%$ predictions to technicians, SolarGuard filters out a sub-population where AI accuracy drops to 43.8%.
- **No False Normal:** In `core/models.py` (`Panel.get_derived_condition`), any panel whose latest inspection has confidence $<60.0\%$ or `review_status == 'flagged'` displays **"Needs Review"** (amber/purple badge), preventing uncertain predictions from ever masquerading as "Appears Normal".
- **Separation of Concerns:** Raw AI predictions (`predicted_class`, `confidence_score`) remain immutable; technician verifications are recorded in `verified_outcome`, `reviewed_by`, and `reviewed_at`.

---

## Part F — Backend Hardening Summary

1. **Thread Safety:** Implemented `threading.Lock()` (`_MODEL_LOCK`) in `ml_engine/inference.py` around `load_model_service()` and `switch_model_version()`, eliminating race conditions under concurrent web requests.
2. **Atomic Inspection Persistence:** In `core/views.py` (`inspect_view`), all database writes are wrapped inside `with transaction.atomic()`. If inference or priority scoring raises an exception, no orphaned "Analyzing..." records remain in the database.
3. **Early Authorization Gate:** In `core/views.py`, raw posted panel IDs are verified prior to form validation. Unauthorized customers attempting to inspect other users' panels, or any attempt to inspect retired panels, immediately returns `HttpResponseForbidden` (HTTP 403).
4. **EXIF Orientation & Preprocessing Consistency:** `ImageOps.exif_transpose()` auto-corrects rotated mobile phone photos before resizing to $224 \times 224$ float32 $[0, 255]$ for model consumption.
5. **Corrupt File Triage:** Corrupt images or non-image payloads are trapped gracefully by Pillow `img.verify()` and returned with status `'unreadable'` and message `'Unable to assess / Retake photo'`, preventing 500 server errors.

---

## Part G — Automated Tests & Verification Results

### 1. Test Suite Execution (`core.test_phase9b` & `core.test_v3_smoke`)
Ran via `.venv\Scripts\python.exe manage.py test core.test_phase9b core.test_v3_smoke`:

```
Found 16 test(s).
System check identified no issues (0 silenced).

[Smoke 1 PASS] V3 model loaded: solarguard_model_v3.keras (3.0)
[Smoke 2 PASS] Preprocessing output shape: (1, 224, 224, 3), dtype: float32, min: 18.0, max: 253.0
[Smoke 3 PASS] Output shape: (1, 4), deterministic: True, sum: 1.0000
[Smoke 4 PASS] Class mapping verified: ['Bird-Dropping', 'Dusty', 'Normal', 'Surface-Damage'], predicted: Normal, score: 74.4%
[Smoke 5 PASS] End-to-end Django inspection complete. Identifier: MobileNetV2 CNN v3.0
[Smoke 6 PASS] Rollback to V2 verified (MobileNetV2 CNN v2.0)
[Smoke 6 PASS] Rollback to V1 verified (MobileNetV2 CNN v1.0)
[Smoke 6 PASS] Active model restored to V3.

Ran 16 tests in 30.158s
OK
```

### 2. Specific Tests Implemented:
1. `test_01_active_model_version_selection`: Verifies default resolves to v3.0, and `v3.1` loads staged model.
2. `test_02_rollback_mechanism`: Verifies instant dynamic rollback from v3.1 to v3.0, v2.0, and v1.0.
3. `test_03_correct_class_order`: Verifies exact class array `['Bird-Dropping', 'Dusty', 'Normal', 'Surface-Damage']`.
4. `test_04_prediction_and_confidence_validity`: Validates probability sum = 100% and bounded confidence scores.
5. `test_05_corrupt_image_handling`: Verifies corrupt byte payloads return `'unreadable'` without crashing.
6. `test_06_failed_inference_handling`: Verifies missing model files fail safely with structured status.
7. `test_07_preservation_of_historical_inspection_predictions`: Confirms historical records are never altered.
8. `test_08_technician_review_threshold_behavior`: Confirms $<60\%$ confidence sets review_status to `'flagged'` and derived condition to `'Needs Review'`.
9. `test_09_model_metadata_compatibility`: Verifies schema, SHA256 hash, and metrics of `model_metadata_v3_1.json`.
10. `test_10_role_based_inspection_authorization`: Confirms customer isolation (HTTP 403 on unowned panel) and retired panel inspection blocking.

---

## Part H — Rollback Instructions

If an operator ever needs to switch or roll back model versions:

### Method 1: Environment Variable (Recommended for Production)
Set the environment variable before starting Django:
```powershell
# To roll back to Version 3.0 (Default Active):
$env:SOLARGUARD_MODEL_VERSION="v3"

# To roll back to Version 2.0:
$env:SOLARGUARD_MODEL_VERSION="v2"

# To roll back to Version 1.0:
$env:SOLARGUARD_MODEL_VERSION="v1"

# To activate Version 3.1:
$env:SOLARGUARD_MODEL_VERSION="v3.1"
```

### Method 2: Django Settings File
In `solarguard_project/settings.py`:
```python
SOLARGUARD_MODEL_VERSION = 'v3' # Change to 'v3.1', 'v2', or 'v1'
```

### Method 3: Runtime Python API
In management commands or Python console:
```python
from ml_engine.inference import switch_model_version
switch_model_version('v3') # Instantly swaps in-memory model and metadata
```

---

## Part I — Remaining Limitations

1. **Softmax Confidence Calibration:** Softmax probabilities reflect the model's relative output scores, not certifiable physical defect probabilities. Calibration techniques (e.g. temperature scaling) should be explored in future phases.
2. **Minority-Class Sample Uncertainty:** With only 25 Bird-Dropping and 33 Surface-Damage test images, individual misclassifications move metrics by 3–4%. Larger real-world field validation datasets should be gathered during Phase 10.
3. **Optical Inspection Boundary:** Visual RGB photography cannot detect internal silicon micro-cracks, bypass diode short-circuits, or PID without electroluminescence (EL) or thermal infrared imaging.
4. **Demonstration Dataset (`media/sample_test_images`):** The 150-image demonstration set exhibits domain shift (synthetic demonstration crops) and achieves only 40–55% accuracy across all models; it is strictly an interface demonstration set, not a diagnostic test suite.

---

## Status & Gate Check

Phase 9B verification, safety audit, acceptance gate, backend hardening, and test suites are **fully completed**.

**STOPPING HERE:** In accordance with the Phase 9B instructions, execution is stopped. We await user approval before proceeding to Phase 10.
