# SolarGuard — Real Solar Panel Dataset Audit Plan
## Verification, Class Label Analysis, and Google Colab Workflow Guide

**Project Owners:** Tanushree Burde and Aanchal Nasre  
**Course/Context:** Software Engineering & Project Management (SEPM)  
**Date:** October 2026  
**Status:** Working Plan — Awaiting Owner Execution in Google Colab  
**Target Milestone:** Gate 2 (Data Gate)

---

## 1. Executive Summary & Why This Audit is Mandatory

In our initial codebase audit ([docs/PROJECT_AUDIT.md](file:///d:/RBU/RBU%20Sem%205/SEPM/Sepm%20Project%20SolarGuard/docs/PROJECT_AUDIT.md)), we revealed that the current prototype's vision classifier was trained on **154 synthetic geometric drawings created with Python Pillow** (computer-drawn circles and zigzag lines). 

While it artificially claimed "100% accuracy", it will fail immediately when presented with real-world solar photographs. Furthermore, the repository's `split_dataset.py` script automatically renamed an entire folder called `Physical-Damage` to `Cracked`. In real solar engineering, physical damage includes cell delamination, burn marks, snail trails, and shattered glass—not just surface cracks.

### Core Rules for Gate 2 (from `SYSTEM_INSTRUCTIONS.md`):
1. **No Fake Data:** Do not fabricate datasets, model weights, evaluation metrics, or confidence scores.
2. **Audit Before Training:** Verify exact image counts, licensing, provenance, resolution, duplicates, and class ambiguities before training a single model.
3. **Do Not Automatically Equate Physical Damage with Cracked:** Conduct visual inspection of sample images before naming or scoping the 4th defect class.
4. **Leakage-Resistant Splits:** Use group-aware, duplicate-free splits. Never augment validation or test sets.
5. **Train on Cloud GPU (Google Colab):** Heavy deep learning training belongs on free cloud GPUs, not on a personal laptop CPU.

---

## 2. Dataset Identification and Licensing Audit

### 2.1 Candidate Public Datasets
The most widely used public dataset for this task in academic PV literature is the **Kaggle Solar Panel Images Dataset** (and related PV fault benchmarks).

| Dataset Candidate | Source & Link | Primary Published Classes | Stated Image Count | License & Terms |
| :--- | :--- | :--- | :--- | :--- |
| **Kaggle: Solar Panel Images Dataset** (Primary candidate) | Kaggle (e.g., `python10pm/solar-panel-images` or similar benchmark mirrors) | Clean, Dusty, Bird-Dropping, Physical-Damage (or Electrical-Damage) | ~1,200 – 2,000 images | Usually CC BY-SA 4.0 or Open Data. Must verify on download page. |
| **PVEL / Stanford PV Defect Dataset** | Research repositories | Cracks, Delamination, Soiling, Inactive strings | Multi-thousand high-res images | Academic / Non-Commercial Research use. |

### 2.2 Verification Checklist for Step 1
* [ ] **Verify License:** Confirm the dataset license permits academic educational reuse and course project demonstration without copyright infringement.
* [ ] **Verify Provenance:** Record where the photos were taken (e.g., rooftop installations, drone flyovers, laboratory test racks, or ground-level hand-held cameras).
* [ ] **Sensor Type:** Confirm whether the images are **visible-spectrum RGB photographs** (standard phone/camera) or **Electroluminescence (EL) / Thermal Infrared (IR)**. SolarGuard v1 operates strictly on standard RGB photographs.

---

## 3. Step-by-Step Data Audit Protocol

### Step 1: Raw Inventory & Exact File Counts
1. Download the uncompressed dataset into an isolated directory (in Google Colab).
2. Count the exact number of readable images in each class folder.
3. Check for non-image files (e.g., `.DS_Store`, `Thumbs.db`, `.txt`, `.csv`) and remove them.
4. Identify class imbalance (e.g., if "Clean" has 800 images but "Bird-Dropping" only has 90, standard accuracy will be misleading).

### Step 2: Physical-Damage vs. Cracked Deep-Dive (Visual Audit)
* **The Problem:** The existing prototype renames `Physical-Damage` $\rightarrow$ `Cracked`.
* **The Audit Task:**
  1. Randomly sample 30 images from the `Physical-Damage` directory.
  2. Visually categorize the visible defect in each sample:
     * Does it show glass surface fracture lines (micro-cracks or spider cracks)?
     * Does it show shattered / broken glass?
     * Does it show dark electrical burn marks or hotspots?
     * Does it show delamination (whitish peeling between glass and silicon)?
     * Does it show bent or warped metal frames?
  3. **Decision Rule:**
     * If $> 80\%$ of images are visible cracks: We can label the class `Cracked (Surface Fractures)`.
     * If the images are a diverse mix: We must honestly label the class `Physical & Surface Damage` and update the SRS accordingly.

### Step 3: Duplicate & Near-Duplicate Detection (MD5 & Perceptual Hash)
* Solar datasets often contain repeated identical photos or burst sequences (10 photos of the exact same panel taken 0.5 seconds apart).
* If burst photos are split between training and test sets, the model appears to score 98% accuracy when it simply memorized the exact same panel (data leakage).
* **Audit Task:**
  1. Compute the **MD5 cryptographic hash** of every image file. Identify and flag exact duplicates.
  2. Compute a **Perceptual Hash (dHash)** using OpenCV/Pillow to flag near-identical burst frames.
  3. Remove or quarantine duplicates before splitting.

### Step 4: Resolution, Aspect Ratio, and Quality Screening
* Check minimum, average, and maximum image dimensions (width $\times$ height).
* Identify extreme outliers (e.g., tiny $32\times32$ icons or massive $6000\times4000$ camera raw files).
* Determine target input resolution for training: **$224\times224$ pixels** (standard for MobileNetV2) or **$128\times128$ pixels** (ultra-lightweight custom CNN).

### Step 5: Defining the "Unable to Assess" Thresholds
To prevent the model from guessing blindly on bad photos, we audit image suitability metrics:
* **Blurriness (Laplacian Variance):**
  $$\text{Var}(\nabla^2 I) = \text{variance of Laplacian filter output}$$
  Images with variance $< 80.0$ are typically out of focus or blurred.
* **Under-exposure / Over-exposure:**
  * Mean brightness $< 20/255 \implies$ Underexposed / night photo.
  * Mean brightness $> 240/255 \implies$ Overexposed / glare whiteout.
* Calibrate these thresholds during the audit so they can be integrated into `ml_engine/adapter.py`.

### Step 6: Leakage-Resistant Train / Validation / Test Split
* **Split Ratios:** 
  * **70% Training Set:** Used by the neural network to learn weights.
  * **15% Validation Set:** Used during training to monitor epoch loss and tune early stopping.
  * **15% Test Set (Held-Out Final Evaluation):** Kept strictly locked away until training is completely finished; never touched during tuning.
* **Integrity Guardrails:**
  * Perform stratified splitting so each subset has identical proportions of each class.
  * Apply data augmentation (flips, slight rotations, brightness adjustments) **only to the training set**. Never augment validation or test sets, as that falsely inflates evaluation scores.

---

## 4. Google Colab Workflow Guide for Beginners

### 4.1 What is Google Colab and Why Use It?
Google Colaboratory (Colab) is a free cloud-based programming tool created by Google. It runs a full Jupyter Python notebook environment inside your browser.

**Why we use Colab instead of training on your laptop:**
1. **Free Cloud GPU (NVIDIA T4):** Training a deep neural network on a standard laptop CPU can take 3 to 6 hours and cause extreme fan noise and overheating. On a Colab T4 GPU, it finishes in **5 to 8 minutes**.
2. **Pre-configured ML Libraries:** Colab comes with TensorFlow 2.x, Keras, OpenCV, and Scikit-Learn pre-installed and matched to GPU drivers.
3. **No Environment Conflicts:** Windows often has binary compatibility conflicts between TensorFlow and NumPy 2.x. Colab bypasses all local setup problems.
4. **Clean Artifact Export:** Once Colab finishes training, we download a single lightweight file (~15 MB) containing the trained model, which runs quickly on your laptop CPU inside Django.

---

### 4.2 Step-by-Step Colab Execution Walkthrough

```
┌────────────────────────────────────────────────────────┐
│ Step 1: Open Colab & Select Free GPU Runtime          │
│ (Runtime -> Change runtime type -> T4 GPU)            │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│ Step 2: Download Real Dataset                         │
│ (Via Kaggle API or Google Drive Upload)                │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│ Step 3: Run Audit Script (Cells 1 to 5)                │
│ - Exact class counts and class imbalance report        │
│ - Visual inspection grid (Physical-Damage samples)     │
│ - MD5 / Perceptual hash duplicate removal              │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│ Step 4: Run Leakage-Resistant 70/15/15 Split          │
│ (Stratified train / val / test folders)                │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│ Step 5: Train Baseline Model (MobileNetV2 Transfer)   │
│ - Augmentation on Train set only                       │
│ - Early stopping to prevent overfitting                │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│ Step 6: Honest Evaluation on Test Set                 │
│ - Per-class Precision, Recall, Macro-F1                │
│ - Confusion Matrix plot                                │
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│ Step 7: Export Model Artifacts                        │
│ - solarguard_model.keras (~15 MB)                      │
│ - class_indices.json & metadata.json                   │
│ -> Download to local Django ml_engine/models/ folder   │
└────────────────────────────────────────────────────────┘
```

#### Detailed Beginner Steps:

1. **Open Google Colab:**
   * In your browser (Chrome/Edge), go to [https://colab.research.google.com](https://colab.research.google.com).
   * Sign in with your Google account and click **"New Notebook"**.
   * Rename the notebook at the top to: `SolarGuard_Data_Audit_and_Training.ipynb`.

2. **Enable the Free GPU:**
   * In the top menu, click **Runtime** $\rightarrow$ **Change runtime type**.
   * Under **Hardware accelerator**, select **T4 GPU**.
   * Click **Save**.

3. **Verify GPU Activation:**
   * In the first code cell, type and run (`Shift + Enter`):
     ```python
     !nvidia-smi
     ```
   * You should see a table displaying `Tesla T4` with ~15 GB VRAM.

4. **Connect Kaggle API (or Upload Dataset):**
   * Download `kaggle.json` from your Kaggle Account Settings.
   * Run the following cell to upload `kaggle.json` and download the dataset:
     ```python
     from google.colab import files
     files.upload() # Choose kaggle.json from your computer

     !mkdir -p ~/.kaggle
     !cp kaggle.json ~/.kaggle/
     !chmod 600 ~/.kaggle/kaggle.json

     # Download the dataset directly to Colab
     !kaggle datasets download -d python10pm/solar-panel-images
     !unzip -q solar-panel-images.zip -d solar_dataset
     ```

---

## 5. Audit Script Code (To Run in Colab)

Below is the complete, beginner-friendly Python script to paste into Colab cells to perform the complete audit:

### Cell 1: Count Images and Analyze Directory Structure
```python
import os
import glob
from pathlib import Path
import pandas as pd
from PIL import Image

DATASET_ROOT = "solar_dataset" # Adjust if nested

print("=== 1. CLASS INVENTORY ===")
class_counts = {}
for root, dirs, files in os.walk(DATASET_ROOT):
    image_files = [f for f in files if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    if image_files:
        folder_name = os.path.basename(root)
        class_counts[folder_name] = len(image_files)

df_counts = pd.DataFrame(list(class_counts.items()), columns=['Class Folder', 'Image Count'])
print(df_counts)
print(f"\nTotal Images Found: {df_counts['Image Count'].sum()}")
```

### Cell 2: Check for Exact Duplicate Files (MD5 Hash)
```python
import hashlib
from collections import defaultdict

print("=== 2. DUPLICATE IMAGE AUDIT ===")
hashes = defaultdict(list)

for root, _, files in os.walk(DATASET_ROOT):
    for f in files:
        if f.lower().endswith(('.jpg', '.jpeg', '.png')):
            filepath = os.path.join(root, f)
            with open(filepath, 'rb') as fp:
                file_hash = hashlib.md5(fp.read()).hexdigest()
            hashes[file_hash].append(filepath)

duplicates = {h: paths for h, paths in hashes.items() if len(paths) > 1}
print(f"Total Unique Images: {len(hashes)}")
print(f"Duplicate Image Sets Found: {len(duplicates)}")

if duplicates:
    print("\nSample Duplicates:")
    for h, paths in list(duplicates.items())[:5]:
        print(f"Hash {h[:8]}: {paths}")
```

### Cell 3: Visual Inspection Grid (Inspecting Physical-Damage vs. Cracked)
```python
import matplotlib.pyplot as plt
import random

# Find damage folder
damage_folder = None
for folder in class_counts.keys():
    if "damage" in folder.lower() or "crack" in folder.lower():
        damage_folder = folder
        break

if damage_folder:
    damage_path = [os.path.join(root, f) for root, _, files in os.walk(DATASET_ROOT) 
                   if os.path.basename(root) == damage_folder 
                   for f in files if f.lower().endswith(('.jpg', '.png'))]
    
    samples = random.sample(damage_path, min(12, len(damage_path)))
    
    plt.figure(figsize=(15, 10))
    for idx, img_path in enumerate(samples):
        img = Image.open(img_path)
        plt.subplot(3, 4, idx + 1)
        plt.imshow(img)
        plt.title(f"Sample {idx+1}: {img.size}")
        plt.axis('off')
    plt.suptitle(f"Visual Audit of Folder: '{damage_folder}'\nObserve: Are these cracks, shattering, burns, or delamination?", fontsize=14)
    plt.tight_layout()
    plt.show()
else:
    print("No damage/crack folder identified for visual inspection.")
```

### Cell 4: Image Dimensions and Blurriness Check
```python
import cv2
import numpy as np

print("=== 4. QUALITY & RESOLUTION AUDIT ===")
resolutions = []
blur_scores = []

sample_files = []
for root, _, files in os.walk(DATASET_ROOT):
    for f in files:
        if f.lower().endswith(('.jpg', '.png')):
            sample_files.append(os.path.join(root, f))

# Audit a representative sample of 200 images
for path in random.sample(sample_files, min(200, len(sample_files))):
    img = cv2.imread(path)
    if img is not None:
        h, w, c = img.shape
        resolutions.append((w, h))
        # Blurriness: Laplacian variance
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        variance = cv2.Laplacian(gray, cv2.CV_64F).var()
        blur_scores.append(variance)

widths, heights = zip(*resolutions)
print(f"Widths:  Min={min(widths)}, Median={int(np.median(widths))}, Max={max(widths)}")
print(f"Heights: Min={min(heights)}, Median={int(np.median(heights))}, Max={max(heights)}")
print(f"Blur Score (Laplacian Var): Min={min(blur_scores):.1f}, Median={np.median(blur_scores):.1f}, Max={max(blur_scores):.1f}")
print(f"Images with variance < 80 (potentially blurry): {sum(1 for b in blur_scores if b < 80)} / {len(blur_scores)}")
```

---

## 6. Model Training & Export Guide (For Gate 4)

Once the audit confirms the dataset clean and the class labels agreed, the notebook proceeds to training:

### 6.1 Recommended Architecture: MobileNetV2 (Transfer Learning)
* **Why MobileNetV2?**
  * It was engineered by Google specifically for high-efficiency mobile and edge devices.
  * It has already learned fundamental visual features (edges, color gradients, textures) from ImageNet.
  * By freezing base layers and training a lightweight classification head, it trains in ~5 minutes on Colab and achieves high macro-F1 with small dataset sizes.
  * The exported model is small (~12–16 MB) and executes on your laptop CPU inside Django in **less than 0.5 seconds**.

### 6.2 Evaluation Metrics That Matter in Your Viva
During your project defense, evaluators will scrutinize your results:
1. **Never claim 100% accuracy:** A real visual model typically achieves between 85% and 94% on real solar photographs.
2. **Focus on Missed Cracks (Recall on Damage):** If a model misses a crack, a fire or hardware failure could occur. Highlight the **Recall score on the Cracked/Damage class**.
3. **Confusion Matrix:** Always present the confusion matrix showing exactly which classes were confused (e.g., slight confusion between heavy dust and bird droppings).

### 6.3 Exporting Artifacts for the Django Project
At the end of training in Colab, export and download these three files:
1. `solarguard_model.keras` — The trained neural network weights.
2. `class_indices.json` — The exact dictionary mapping class indices to human-readable names:
   ```json
   {
     "0": "Bird-Dropping",
     "1": "Cracked / Surface Damage",
     "2": "Dusty",
     "3": "Normal"
   }
   ```
3. `model_metadata.json` — Version, training date, input dimensions ($224\times224$), preprocessing normalization parameters, and test set Macro-F1 score.

---

## 7. Deliverables Required from Gate 2 Before Gate 3 Code Begins

Before we make any changes to the Django codebase, we will review the outputs from this Colab execution:
1. **The Completed Audit Table:** Exact image counts per class folder and license verification.
2. **Visual Inspection Finding:** Confirmation of whether the 4th class is strictly `Cracked` or broader `Surface Damage`.
3. **Audit Sign-Off:** Approval by project owners (Tanushree & Aanchal) to freeze class definitions and proceed to the Foundation Implementation Gate.
