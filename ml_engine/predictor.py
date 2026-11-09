"""
SolarGuard — Unified Dual-Model Inference & Fallback Engine

Coordinates:
1. Visual Fault Classification: Custom CNN (fault_cnn.h5) with OpenCV Heuristic Fallback
2. Operational Degradation Prediction: Random Forest (rf_degradation.joblib) with Heuristic Fallback
"""

import os
import sys
import json
from pathlib import Path
import numpy as np
from PIL import Image
import joblib

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / 'ml_engine' / 'models'

CNN_MODEL_PATH = MODELS_DIR / 'fault_cnn.h5'
CLASSES_JSON_PATH = MODELS_DIR / 'classes.json'
VISION_MODEL_PATH = MODELS_DIR / 'vision_classifier.joblib'
VISION_METADATA_PATH = MODELS_DIR / 'vision_metadata.joblib'
RF_MODEL_PATH = MODELS_DIR / 'rf_degradation.joblib'
RF_METADATA_PATH = MODELS_DIR / 'rf_metadata.joblib'

# Cached model references in memory to prevent reloading on each web request
_CACHED_CNN = None
_CACHED_CLASSES = None
_CACHED_VISION = None
_CACHED_RF = None


def get_cnn_model():
    global _CACHED_CNN, _CACHED_CLASSES
    if _CACHED_CNN is not None:
        return _CACHED_CNN, _CACHED_CLASSES

    if CNN_MODEL_PATH.exists() and CLASSES_JSON_PATH.exists():
        try:
            import tensorflow as tf
            _CACHED_CNN = tf.keras.models.load_model(CNN_MODEL_PATH)
            with open(CLASSES_JSON_PATH, 'r') as f:
                _CACHED_CLASSES = json.load(f)
            return _CACHED_CNN, _CACHED_CLASSES
        except Exception as e:
            print(f"[!] Note: CNN model found but could not be loaded ({e}).")
            return None, None
    return None, None


def get_vision_model():
    global _CACHED_VISION
    if _CACHED_VISION is not None:
        return _CACHED_VISION

    if VISION_MODEL_PATH.exists():
        try:
            _CACHED_VISION = joblib.load(VISION_MODEL_PATH)
            return _CACHED_VISION
        except Exception as e:
            print(f"[!] Note: Vision classifier found but could not be loaded ({e}).")
            return None
    return None


def get_rf_model():
    global _CACHED_RF
    if _CACHED_RF is not None:
        return _CACHED_RF

    if RF_MODEL_PATH.exists():
        try:
            _CACHED_RF = joblib.load(RF_MODEL_PATH)
            return _CACHED_RF
        except Exception as e:
            print(f"[!] Note: RF model found but could not be loaded ({e}). Using heuristic fallback.")
            return None
    return None


def extract_visual_features_for_inference(image_path):
    """
    Extracts multi-domain visual feature vector matching the trained vision classifier.
    """
    import cv2
    img = cv2.imread(str(image_path))
    if img is None:
        pil_img = Image.open(image_path).convert('RGB')
        img = np.array(pil_img)[:, :, ::-1]

    img_resized = cv2.resize(img, (128, 128))
    gray = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img_resized, cv2.COLOR_BGR2HSV)
    lab = cv2.cvtColor(img_resized, cv2.COLOR_BGR2LAB)

    features = []

    # 1. Color statistics in RGB, HSV, LAB
    for ch in range(3):
        features.extend([
            float(np.mean(img_resized[:, :, ch])),
            float(np.std(img_resized[:, :, ch])),
            float(np.percentile(img_resized[:, :, ch], 10)),
            float(np.percentile(img_resized[:, :, ch], 90)),
        ])
        features.extend([
            float(np.mean(hsv[:, :, ch])),
            float(np.std(hsv[:, :, ch])),
        ])
        features.extend([
            float(np.mean(lab[:, :, ch])),
            float(np.std(lab[:, :, ch])),
        ])

    # 2. Texture & Grayscale statistics
    features.extend([
        float(np.mean(gray)),
        float(np.std(gray)),
        float(np.percentile(gray, 5)),
        float(np.percentile(gray, 95)),
    ])

    # 3. Edge statistics (Sobel, Laplacian, Canny)
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    features.extend([
        float(lap.var()),
        float(np.mean(np.abs(lap))),
        float(np.percentile(np.abs(lap), 90)),
        float(np.percentile(np.abs(lap), 99)),
    ])

    canny = cv2.Canny(gray, 50, 150)
    features.append(float(np.mean(canny > 0)))

    sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    sobel_mag = np.sqrt(sobelx**2 + sobely**2)
    features.extend([
        float(np.mean(sobel_mag)),
        float(np.std(sobel_mag)),
        float(np.percentile(sobel_mag, 95)),
    ])

    # 4. Localized Bright/Opaque spot detection (for Bird-Dropping)
    _, bright_thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(bright_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    bright_spot_count = sum(1 for c in contours if cv2.contourArea(c) > 15)
    bright_spot_area = sum(cv2.contourArea(c) for c in contours if cv2.contourArea(c) > 15)
    features.extend([float(bright_spot_count), float(bright_spot_area)])

    # 5. Color Histograms
    hist_h = cv2.calcHist([hsv], [0], None, [16], [0, 180]).flatten() / (128 * 128)
    hist_s = cv2.calcHist([hsv], [1], None, [16], [0, 256]).flatten() / (128 * 128)
    hist_v = cv2.calcHist([hsv], [2], None, [16], [0, 256]).flatten() / (128 * 128)
    features.extend([float(v) for v in hist_h])
    features.extend([float(v) for v in hist_s])
    features.extend([float(v) for v in hist_v])

    return np.array(features, dtype=np.float32)


from ml_engine.priority_engine import calculate_maintenance_priority


def check_image_quality(image_path):
    """
    Evaluates image clarity and lighting to triage unsuitable images
    before sending them to classifiers.
    """
    import cv2
    img = cv2.imread(str(image_path))
    if img is None:
        try:
            pil_img = Image.open(image_path).convert('RGB')
            img = np.array(pil_img)[:, :, ::-1]
        except Exception:
            return False, "Unable to decode image."

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    mean_brightness = float(np.mean(gray))

    # Dark / underexposed check
    if mean_brightness < 18.0:
        return False, "Photo is underexposed or taken in near darkness."
    
    # Overexposed / whiteout glare check
    if mean_brightness > 242.0:
        return False, "Photo is severely overexposed with heavy glare."

    # Extreme blur check
    if laplacian_var < 15.0:
        return False, "Photo is out of focus or excessively blurred."

    return True, "Quality acceptable"


def predict_fault_with_opencv_heuristic(image_path):
    """
    OpenCV image metric analysis used as a development mock when no deep learning model is loaded.
    """
    import cv2

    img = cv2.imread(str(image_path))
    if img is None:
        pil_img = Image.open(image_path).convert('RGB')
        img = np.array(pil_img)[:, :, ::-1]

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    sat_mean = np.mean(hsv[:, :, 1])
    gray_std = np.std(gray)

    # 1. Distinct bright opaque spots for bird droppings
    _, bright_thresh = cv2.threshold(gray, 185, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(bright_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    bright_spot_count = sum(1 for cnt in contours if cv2.contourArea(cnt) > 25)

    # 2. Classification rule order
    if sat_mean < 25.0 and gray_std < 28.0:
        predicted_class = "Dusty"
        confidence = min(96.0, 85.0 + (30.0 - gray_std))
    elif bright_spot_count >= 2:
        predicted_class = "Bird-Dropping"
        confidence = min(95.0, 82.0 + bright_spot_count * 3.0)
    elif laplacian_var > 4500.0 or (laplacian_var > 3000.0 and gray_std > 48.0):
        predicted_class = "Cracked"
        confidence = min(96.0, 84.0 + (laplacian_var / 300.0))
    else:
        predicted_class = "Normal"
        confidence = 91.5 + (gray_std % 5.0)

    return {
        'predicted_class': predicted_class,
        'confidence_score': round(float(confidence), 1),
        'engine': 'Development Mock (OpenCV Rule Heuristic)',
        'is_mock': True,
        'is_fallback': True
    }


from ml_engine.inference import run_cnn_inference, load_model_service


def predict_fault(image_path):
    """
    Main entry point for visual condition classification.
    Runs the real Colab-trained MobileNetV2 CNN by default.
    Never silently falls back to synthetic or mock models when real inference fails.
    """
    use_dev_mock = False
    try:
        from django.conf import settings
        use_dev_mock = getattr(settings, 'SOLARGUARD_USE_DEV_MOCK', False)
    except Exception:
        use_dev_mock = os.environ.get('SOLARGUARD_USE_DEV_MOCK', 'False').lower() in ('true', '1', 'yes')

    # If explicit dev mock requested via environment/settings:
    if use_dev_mock:
        is_ok, reason = check_image_quality(image_path)
        if not is_ok:
            return {
                'status': 'unreadable',
                'predicted_class': 'Unable to assess / Retake photo',
                'confidence_score': 0.0,
                'class_probabilities': {},
                'engine': f'Quality Triage Gate ({reason})',
                'model_identifier': f'Quality Triage Gate ({reason})',
                'is_mock': True,
                'is_fallback': True,
                'triage_reason': reason
            }
        mock_res = predict_fault_with_opencv_heuristic(image_path)
        mock_res['class_probabilities'] = {}
        mock_res['status'] = 'success'
        mock_res['model_identifier'] = mock_res.get('engine', 'Development Mock')
        return mock_res

    # Real MobileNetV2 CNN Inference (Primary & Default)
    cnn_res = run_cnn_inference(image_path)
    
    # Return structured result maintaining backwards-compatibility with existing views
    return {
        'status': cnn_res.get('status', 'success'),
        'predicted_class': cnn_res['predicted_class'],
        'confidence_score': cnn_res['confidence_score'],
        'class_probabilities': cnn_res.get('class_probabilities', {}),
        'margin': cnn_res.get('margin', 0.0),
        'engine': cnn_res['model_identifier'],
        'model_identifier': cnn_res['model_identifier'],
        'model_version': cnn_res.get('model_version', '3.0'),
        'is_mock': cnn_res.get('is_mock', False),
        'is_fallback': cnn_res.get('is_fallback', False),
        'is_low_confidence': cnn_res.get('is_low_confidence', False),
        'is_close_margin': cnn_res.get('is_close_margin', False),
        'is_uncertain': cnn_res.get('is_uncertain', False),
        'needs_manual_review': cnn_res.get('needs_manual_review', False),
        'uncertainty_notes': cnn_res.get('uncertainty_notes', []),
        'assessment_disclaimer': cnn_res.get('assessment_disclaimer', ''),
        'experimental_note': cnn_res.get('experimental_note', ''),
        'error_message': cnn_res.get('error_message')
    }



def predict_degradation(panel, visual_finding="Normal"):
    """
    Main entry point for maintenance priority determination.
    Uses the transparent, deterministic Rules-Based Maintenance Priority Engine.
    Also provides backward-compatible degradation_probability and risk_category.
    """
    res = calculate_maintenance_priority(panel, visual_finding)
    
    return {
        'risk_category': res['priority_level'],
        'degradation_probability': float(res['priority_score']),
        'priority_score': res['priority_score'],
        'priority_level': res['priority_level'],
        'summary_advice': res['summary_advice'],
        'breakdown': res['breakdown'],
        'explanation_text': res['explanation_text'],
        'engine': res['engine'],
        'is_mock': False
    }

