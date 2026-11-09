"""
SolarGuard — Random Forest Degradation Risk Predictor Training Script

CONTEXT & METHODOLOGY:
In utility and distributed solar PV operations, multi-decade ground-truth degradation failure logs
with full environmental telemetry are proprietary and scarce. For this SEPM academic prototype,
we generate a domain-grounded synthetic dataset (2,000 samples) based on established photovoltaic
physics and reliability principles:
  1. Arrhenius Thermal Acceleration: Higher average operating temperatures accelerate EVA browning,
     solder joint fatigue, and PID (Potential Induced Degradation).
  2. Soiling & Cleaning Intervals: Longer intervals without cleaning combined with high dust indices
     cause persistent hot-spot stress and uneven cell loading.
  3. Cumulative Fault History: Panels with recent recurring anomalies exhibit higher latent defect
     propagation rates.
  4. Operational Ageing: Baseline linear degradation (~0.5% - 0.8%/year power loss).

This heuristic formula creates a realistic non-linear relationship between operating features
and degradation risk buckets (Low / Medium / High).
"""

import os
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score

BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / 'ml_engine' / 'models'
MODELS_DIR.mkdir(parents=True, exist_ok=True)

MODEL_PATH = MODELS_DIR / 'rf_degradation.joblib'
METADATA_PATH = MODELS_DIR / 'rf_metadata.joblib'

FEATURE_NAMES = [
    'panel_age_months',
    'fault_count_last_6_months',
    'days_since_last_cleaning',
    'avg_temp_exposure',
    'dust_index_avg'
]

RISK_CLASSES = ['Low', 'Medium', 'High']


def generate_synthetic_degradation_data(n_samples=2000, random_state=42):
    """
    Generate synthetic PV telemetry with domain-grounded non-linear risk mapping.
    """
    np.random.seed(random_state)

    # 1. Feature distributions
    # Age: 1 to 120 months (up to 10 years)
    panel_age_months = np.random.uniform(1.0, 120.0, size=n_samples)

    # Recent faults: Poisson distribution centered around 1-3 faults
    fault_count = np.random.poisson(lam=1.8, size=n_samples)
    fault_count = np.clip(fault_count, 0, 10)

    # Days since last cleaning: 0 to 180 days
    days_since_cleaning = np.random.uniform(0.0, 180.0, size=n_samples)

    # Avg Temp Exposure: Normal distribution centered around 36 deg C
    avg_temp_exposure = np.random.normal(loc=36.0, scale=8.0, size=n_samples)
    avg_temp_exposure = np.clip(avg_temp_exposure, 15.0, 55.0)

    # Dust / Soiling Index: Beta distribution representing clear to heavily soiled sites
    dust_index = np.random.beta(a=2.5, b=3.0, size=n_samples)
    dust_index = np.clip(dust_index, 0.05, 0.95)

    X = np.column_stack([
        panel_age_months,
        fault_count,
        days_since_cleaning,
        avg_temp_exposure,
        dust_index
    ])

    # 2. Domain Heuristic Risk Score (0.0 to 100.0)
    # Normalized sub-scores
    age_factor = panel_age_months / 120.0  # Weight: 0.28
    fault_factor = np.clip(fault_count / 5.0, 0.0, 1.0)  # Weight: 0.25
    cleaning_factor = np.clip(days_since_cleaning / 120.0, 0.0, 1.0)  # Weight: 0.20
    temp_factor = np.clip((avg_temp_exposure - 25.0) / 25.0, 0.0, 1.0)  # Weight: 0.15
    dust_factor = dust_index  # Weight: 0.12

    # Synergistic interaction: high dust + high days without cleaning causes soiling penalty
    interaction_soiling = (cleaning_factor * dust_factor) * 0.15

    # Random noise to simulate real-world variance & environmental unobservables
    noise = np.random.normal(loc=0.0, scale=3.0, size=n_samples)

    raw_risk_score = (
        0.28 * age_factor +
        0.24 * fault_factor +
        0.18 * cleaning_factor +
        0.16 * temp_factor +
        0.14 * dust_factor +
        interaction_soiling
    ) * 100.0 + noise

    raw_risk_score = np.clip(raw_risk_score, 0.0, 100.0)

    # 3. Balanced Discretization: Low (<35), Medium (35-62), High (>=62)
    y = np.empty(n_samples, dtype=object)
    for i, score in enumerate(raw_risk_score):
        if score < 35.0:
            y[i] = 'Low'
        elif score < 62.0:
            y[i] = 'Medium'
        else:
            y[i] = 'High'

    return X, y, raw_risk_score


def train_and_evaluate(n_samples=2000):
    print("=" * 70)
    print("[SolarGuard] Training Random Forest Degradation Risk Predictor")
    print("=" * 70)
    print(f"[*] Generating {n_samples} domain-grounded synthetic telemetry samples...")

    X, y, raw_scores = generate_synthetic_degradation_data(n_samples=n_samples)

    class_counts = {c: int(np.sum(y == c)) for c in RISK_CLASSES}
    print(f"[*] Balanced class distribution: {class_counts}")

    # Train / Test split (80/20)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )

    print(f"[*] Training dataset size: {X_train.shape[0]} samples")
    print(f"[*] Testing dataset size:  {X_test.shape[0]} samples")

    # Train lightweight Random Forest Classifier
    rf_model = RandomForestClassifier(
        n_estimators=80,
        max_depth=7,
        min_samples_split=4,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1
    )

    rf_model.fit(X_train, y_train)

    # Evaluation
    y_pred = rf_model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)

    print("\n" + "-" * 50)
    print(f"[OK] Random Forest Validation Accuracy: {accuracy * 100:.2f}%")
    print("-" * 50)
    print("\nDetailed Classification Report:\n")
    print(classification_report(y_test, y_pred, target_names=RISK_CLASSES))

    print("\nFeature Importances Breakdown:")
    importances = rf_model.feature_importances_
    sorted_indices = np.argsort(importances)[::-1]
    for idx in sorted_indices:
        print(f"   * {FEATURE_NAMES[idx]:<30}: {importances[idx] * 100:.2f}%")

    # Save trained model & metadata
    joblib.dump(rf_model, MODEL_PATH)
    joblib.dump({
        'feature_names': FEATURE_NAMES,
        'risk_classes': RISK_CLASSES,
        'accuracy': float(accuracy),
    }, METADATA_PATH)

    print(f"\n[OK] Model saved to: {MODEL_PATH}")
    print(f"[OK] Metadata saved to: {METADATA_PATH}")
    print("=" * 70)


if __name__ == '__main__':
    train_and_evaluate(n_samples=2000)
