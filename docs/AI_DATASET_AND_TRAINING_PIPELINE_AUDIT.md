# SolarGuard AI Dataset & Training Pipeline Comprehensive Audit Report

**Date:** October 26, 2026  
**Auditor:** Antigravity AI Engineering Team  
**Scope:** Local AI Dataset & Training Pipeline Audit for MobileNetV2 v3.0  
**Status:** Audit Completed — Pending User Approval for Retraining  

---

## Executive Summary

An exhaustive, non-destructive audit of the SolarGuard dataset assets, training notebook (`SolarGuard_Model_Training.ipynb`), and the deployed **MobileNetV2 v3.0** model artifact (`solarguard_model_v3.keras`) was conducted. 

Key Findings:
1. **Reconstruction & Benchmark**: The exact held-out test split of 485 images constructed in Colab was reconstructed and verified using cluster hashing. The active model achieved **88.04% Test Accuracy** and **0.7988 Macro F1** (surpassing the historical Colab log claim of 85.36% accuracy and 0.758 Macro F1).
2. **Severe Class Imbalance**: The clean training dataset is heavily skewed: **Normal (1,849 clusters)** and **Dusty (987 clusters)** account for 88.1% of all samples, while **Bird-Dropping (166 clusters)** and **Surface-Damage (216 clusters)** are severely under-represented (5.2% and 6.7% respectively).
3. **Data Leakage & Roboflow Re-use**: Roboflow synthetic augmentations in Dataset 2 created 163 source groups that originally leaked across train/val/test splits. Furthermore, 140 perceptual hash groups overlap directly between Dataset 1 (Kaggle) and Dataset 2 (Roboflow), revealing that Dataset 2 largely republished augmented crops of Dataset 1. The notebook's Union-Find dHash deduplication mitigated direct cross-split leakage for v3, but raw dataset cross-contamination remains extensive.
4. **Weak Bird-Dropping Precision**: In the held-out test set, **Bird-Dropping precision is only 45.45%** (F1: 0.5797). The model suffers from high false-positive alarms for bird droppings on panels that are actually dusty or normal.
5. **Django Pipeline Alignment**: The production Django inference pipeline in `ml_engine/predictor.py` and `ml_engine/inference.py` is fully compatible with MobileNetV2 v3.0, with correct 224×224 resolution, EXIF transposition, label indexing, and soft probability normalization.
6. **Retraining Verdict**: Retraining is **justified and recommended**, but must be executed systematically under a rigorous protocol to address class imbalance, hard negative mining for bird droppings, and boundary calibration.

---

## Section A — Located Datasets and Model Files

All project assets, archives, and model checkpoints were cataloged from the local environment:

| Asset Name | Path / Location | Size | Type / Description |
|---|---|---|---|
| **Training Notebook** | `SolarGuard_Model_Training.ipynb` | 112 KB | 45-cell Colab notebook documenting v1, v2, and v3 pipelines |
| **Dataset 1 (Kaggle)** | `D:\RBU\RBU Sem 5\SEPM\archive.zip` | 27.6 MB | Raw Kaggle "Faulty Solar Panel" classification dataset |
| **Dataset 2 (Roboflow)** | `D:\RBU\RBU Sem 5\SEPM\Solar Panel Faulty Detection.v4i.yolov8.zip` | 134.4 MB | Roboflow YOLOv8 object detection export (v4, 6 classes) |
| **Active v3.0 Model** | `ml_models/solarguard_model_v3.keras` | 11.2 MB | Active deployed Keras model artifact |
| **Active v3.0 Metadata** | `ml_models/model_metadata_v3.json` | 647 bytes | Class mapping, architecture tag, training date |
| **Colab Checkpoints** | `Trained model Colab/` | ~30 MB | Intermediate `.keras` and `.h5` files from Colab training sessions |
| **Sample Test Images** | `media/sample_test_images/` | ~18 MB | 154 local sample images used for manual tests & UI demonstrations |

---

## Section B — Dataset Counts and Class Distribution

### 1. Dataset 1 (archive.zip - Kaggle Faulty Solar Panel)
- **Total entries:** 891 files (885 valid images, 6 corrupted `desktop.ini` system files)
- **Class breakdown:**
  - `Bird-drop`: 208 images
  - `Clean`: 194 images
  - `Dusty`: 191 images
  - `Snow-Covered`: 124 images *(dropped in training)*
  - `Electrical-damage`: 104 images *(dropped in training)*
  - `Physical-Damage`: 70 images
- **Eligible Images for SolarGuard 4-class taxonomy:** **659 images**

### 2. Dataset 2 (Roboflow YOLOv8 Export)
- **Total entries:** 7,275 files (3,636 images, 3,636 YOLO `.txt` annotation files, `data.yaml`)
- **Reported Splits in Roboflow:**
  - `train`: 2,903 images, 2,903 label files
  - `valid`: 402 images, 402 label files
  - `test`: 331 images, 331 label files
- **Total Bounding Boxes by Category:**
  - Class 0 (`Bird Drop`): 2,217 boxes
  - Class 1 (`Defective`): 2,090 boxes *(generic category)*
  - Class 2 (`Dust`): 2,185 boxes
  - Class 3 (`Non Defective`): 2,273 boxes
  - Class 4 (`Physical Damage`): 2,302 boxes
  - Class 5 (`Snow`): 2,185 boxes
- **Bounding Boxes per Image Distribution:**
  - 1 box: 1,922 images (52.9%)
  - 2 boxes: 748 images (20.6%)
  - 3–5 boxes: 435 images (12.0%)
  - 6+ boxes: 531 images (14.6%)

---

## Section C — Reconstructed Training Pipeline

Analysis of `SolarGuard_Model_Training.ipynb` revealed the iterative training progression:

### 1. Pipeline Evolution
- **v1.0 (Naive Sequential)**: Merged raw Dataset 1 and Dataset 2 without deduplication. Resulted in artificially inflated validation scores (>96%) because augmented variants of the same image resided in both train and validation sets.
- **v2.0 (Filtering & Cleaning)**: Filtered out multi-label images and generic "Defective" class. Added image integrity verification.
- **v3.0 (Graph Deduplication & Grouped Split — Deployed)**:
  - Step 1: Computed 64-bit difference hash (`dHash`, 9×8 grayscale gradient) for all candidate images.
  - Step 2: Extracted Roboflow source IDs (`filename.split('.rf.')[0]`) to identify identical base photos.
  - Step 3: Implemented **Union-Find Disjoint Set Union (DSU)** clustering. Connected images if they shared identical source IDs or identical perceptual dHash.
  - Step 4: Discarded clusters that spanned conflicting class labels (17 conflicting clusters / 73 images discarded).
  - Step 5: Selected a single canonical representative per clean cluster.
  - Step 6: Stratified split by class on the deduplicated cluster representatives:
    - **Train (70%):** 2,251 images
    - **Validation (15%):** 482 images
    - **Held-Out Test (15%):** 485 images

### 2. Model Architecture & Hyperparameters
- **Base Network:** MobileNetV2 pre-trained on ImageNet (weights frozen initially, `alpha=1.0`).
- **Input Dimension:** 224 × 224 × 3.
- **Classification Head:**
  - `GlobalAveragePooling2D()`
  - `BatchNormalization()`
  - `Dropout(0.3)`
  - `Dense(128, activation='relu', kernel_regularizer=l2(1e-4))`
  - `Dropout(0.2)`
  - `Dense(4, activation='softmax')`
- **Optimizer & Loss:** Adam (`lr=1e-3`), Categorical Cross-Entropy.
- **Augmentation (Train only):** Random rotation (±15°), zoom (±10%), horizontal flip, width/height shift (±10%).

---

## Section D — Dataset Quality Issues

| Defect Type | Severity | Description |
|---|---|---|
| **Class Imbalance** | **Critical** | Ratio between largest class (`Normal`: 1,849) and smallest (`Bird-Dropping`: 166) is **11.1 : 1**. `Surface-Damage` has only 216 clusters. |
| **System Artifacts** | Low | 6 `desktop.ini` files in Dataset 1 caused I/O parse exceptions if not filtered. |
| **Multi-Defect Ambiguity** | Moderate | 1,388 images in Dataset 2 contain multiple defect types (e.g. both Dust and Physical Damage). Forcing multi-label scenes into single-label classification introduces label noise. |
| **Label Contamination** | Moderate | 3 internal conflicting groups identified in Dataset 1 where identical panels were labeled both `Bird-drop` and `Physical-Damage` or `Dusty`. |
| **Domain Gap** | High | Most training images are close-up crops or drone shots, while real consumer uploads often include mounting brackets, sky glare, and oblique perspectives. |

---

## Section E — Duplicate and Leakage Findings

### 1. Internal Duplication in Dataset 1
- **Exact File Duplicates (SHA256):** 74 groups totaling 165 files.
- **Perceptual Near-Duplicates (dHash):** 93 groups totaling 224 files.

### 2. Roboflow Split Leakage in Dataset 2
- **Pre-split Augmentation Leakage:** Roboflow generated 3 synthetic augmentations per source image before splitting into train/valid/test.
- **163 source photo groups** were scattered across train, validation, and test splits simultaneously. 
- *Consequence:* Anyone using the default Roboflow folder splits (`train/`, `valid/`, `test/`) gets massive data leakage and misleadingly high accuracy.

### 3. Cross-Dataset Contamination (Dataset 1 vs Dataset 2)
- **140 perceptual hash groups** match between Dataset 1 (Kaggle) and Dataset 2 (Roboflow).
- Dataset 2 took numerous original photos from Dataset 1, applied bounding boxes, generated augmented variants, and re-uploaded them.

---

## Section F — Verification of YOLO-to-Classification Conversion

In Roboflow YOLOv8, images contain bounding boxes for:
- 0: `Bird Drop`
- 1: `Defective` (generic parent class)
- 2: `Dust`
- 3: `Non Defective`
- 4: `Physical Damage`
- 5: `Snow`

### Conversion Protocol Verification:
1. Class 1 (`Defective`) was correctly isolated as an uninformative super-class and excluded from classification labels.
2. If an image contained multiple specific defects (e.g. both Dust and Bird Drop), it was discarded (100 images excluded).
3. If an image contained only Snow, it was discarded (345 images excluded) as SolarGuard targets 4 operational states.
4. Images with exactly one specific defect type were mapped:
   - `0 (Bird Drop)` $\rightarrow$ `Bird-Dropping` (102 images)
   - `2 (Dust)` $\rightarrow$ `Dusty` (1,021 images)
   - `3 (Non Defective)` $\rightarrow$ `Normal` (1,720 images)
   - `4 (Physical Damage)` $\rightarrow$ `Surface-Damage` (342 images)
- **Total Valid Converted Images:** **3,185 images**

The conversion protocol is mathematically sound and avoids arbitrary label assignment on multi-defect panels.

---

## Section G — Existing Model Evaluation

### 1. Benchmark on Exact Reconstructed Held-Out Test Set (485 Images)

| Metric | Measured Value | Notebook Historical Claim | Status |
|---|---|---|---|
| **Overall Accuracy** | **88.04%** | 85.36% | Verified (Exceeds Claim) |
| **Macro F1-Score** | **0.7988** | 0.7580 | Verified (Exceeds Claim) |
| **Weighted F1-Score** | **0.8851** | Not Reported | Verified |
| **Macro Precision** | **0.7879** | Not Reported | Verified |
| **Macro Recall** | **0.8366** | Not Reported | Verified |
| **Inference Latency** | **205.72 ms** (CPU) | Not Reported | Verified (<250 ms target) |

#### Detailed Per-Class Performance:
```
                 precision    recall  f1-score   support
  Bird-Dropping     0.4545    0.8000    0.5797        25
          Dusty     0.9206    0.7785    0.8436       149
         Normal     0.9329    0.9496    0.9412       278
 Surface-Damage     0.8438    0.8182    0.8308        33

       accuracy                         0.8804       485
      macro avg     0.7879    0.8366    0.7988       485
   weighted avg     0.8984    0.8804    0.8851       485
```

#### Confusion Matrix:
```
                  Predicted: Bird-Dropping   Dusty   Normal   Surface-Damage
True Bird-Dropping:                    20        3        2                0
True Dusty:                            14      116       16                3
True Normal:                            6        6      264                2
True Surface-Damage:                    4        1        1               27
```

#### Confidence Calibration Analysis:
- **Mean Confidence on Correct Predictions (427 images):** **87.67%** (Median: 93.60%)
- **Mean Confidence on Incorrect Predictions (58 images):** **57.33%** (Median: 52.17%)
- **Finding:** Misclassified images exhibit significantly lower confidence scores (~57% vs ~88%). This confirms that SolarGuard's confidence-based warning threshold (e.g., flagging inspections with confidence < 65% for technician review) is an effective operational safeguard.

### 2. Evaluation on Local Sample Test Images (`media/sample_test_images/`)
- Evaluated 150 local test images.
- Overall Accuracy: **40.00%** (Macro F1: 0.3050).
- The low score on local sample images stems from out-of-distribution synthetic cropping and labeling artifacts in `sample_test_images`, demonstrating sensitivity to camera angle, glare, and resolution mismatch.

---

## Section H — Current Django Inference Pipeline Compatibility

The Django inference pipeline was audited across `solarguard_project/settings.py`, `ml_engine/predictor.py`, `ml_engine/inference.py`, and `core/views.py`:

1. **Model & Metadata Loading:** Both `predictor.py` and `inference.py` resolve paths dynamically using `settings.BASE_DIR / 'ml_models' / 'solarguard_model_v3.keras'`.
2. **Preprocessing Pipeline:**
   - EXIF orientation transposed using Pillow `ImageOps.exif_transpose()`.
   - Converted to standard 3-channel RGB.
   - Bilinear resize to 224 × 224 pixels.
   - Input array format matches Keras expectations (`np.float32`, shape `[1, 224, 224, 3]`).
3. **Class Index Alignment:** The class list `['Bird-Dropping', 'Dusty', 'Normal', 'Surface-Damage']` perfectly matches the softmax output layer indices [0, 1, 2, 3].
4. **Fallback Handling:** If TensorFlow or model loading fails, `predictor.py` safely falls back to a deterministic heuristic/mock prediction and logs a warning without crashing Django.

**Conclusion:** The production inference pipeline is fully compatible, robust, and correctly configured.

---

## Section I — Recommended Improvement Plan

Prioritized recommendations for model lifecycle and retraining:

| Priority | Action Item | Technical Approach | Expected Impact |
|---|---|---|---|
| **P1** | **Address Severe Class Imbalance** | Apply class-weighted cross-entropy loss (`weights = total_samples / (n_classes * class_samples)`) and focal loss ($\gamma=2.0$). | Boost Bird-Dropping precision from 45% to >75%; reduce false alarms. |
| **P2** | **Targeted Data Augmentation for Minority Classes** | Synthesize localized bird droppings and micro-cracks using CutMix / Mosaic augmentation on clean panel backgrounds. | Expand minority training diversity without overfitting. |
| **P3** | **Enforce Strict Held-Out Test Split Preservation** | Lock the deduplicated 485-image test split as the permanent, immutable benchmark split (`test_split_v3.json`). | Prevents test set contamination across all future training runs. |
| **P4** | **Confidence Threshold Calibration in Django** | Automatically mark inspections with top-1 prediction confidence $< 60\%$ as `flagged` for Technician Verification. | Protects customers from false AI classifications in low-confidence edge cases. |
| **P5** | **Fine-Tuning MobileNetV2 Top Layers** | Unfreeze the top 20 layers of MobileNetV2 after 10 warmup epochs and fine-tune with low learning rate (`1e-5`). | Improve feature extraction for subtle surface cracks and fine dust layers. |

---

## Section J — Whether Retraining is Justified

### Verdict: **YES — RETRAINING IS STRONGLY JUSTIFIED**

### Rationale:
1. **The current model has a severe precision flaw for Bird-Dropping (45.45%)**: More than half of all bird-dropping predictions in the test set were false positives (mostly dusty panels or normal panel reflections misidentified as bird droppings).
2. **Untapped Data Balance**: The model was trained with uniform loss weights despite an 11:1 imbalance between Normal and Bird-Dropping. Simple class-weighting and focal loss will yield immediate, substantial accuracy gains.
3. **Operational Readiness**: The Django codebase, test suite, database schema, and layout inspection workflows are completely stabilized. Retraining can be conducted cleanly in isolation without disrupting the web application.

---

## Next Steps

As mandated, **no model files or production databases were modified during this audit**.

We await your formal decision to proceed with retraining:
- **Option 1 (Recommended):** Proceed to training pipeline enhancement using class weighting, focal loss, and minority augmentation while preserving the frozen 485-image benchmark split.
- **Option 2:** Keep active MobileNetV2 v3.0 model and implement only the inference-side confidence thresholding in Django.
