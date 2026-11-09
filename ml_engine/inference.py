"""
SolarGuard — Dedicated Real CNN Inference Service
Integrates trained MobileNetV2 transfer learning model from Google Colab export.
Supports Version 3 (default), Version 2, and Version 1 with seamless rollback.
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List
import numpy as np
from PIL import Image, ImageOps

import threading

logger = logging.getLogger(__name__)

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_MODELS_DIR = BASE_DIR / 'ml_models'

# Model Catalog for Version 1, Version 2, Version 3, and Version 3.1
MODEL_CATALOG = {
    'v1': {
        'model_file': 'solarguard_model.keras',
        'metadata_file': 'model_metadata.json',
        'version': '1.0',
        'name': 'Version 1 (Initial MobileNetV2 baseline)',
    },
    'v2': {
        'model_file': 'solarguard_model_v2.keras',
        'metadata_file': 'model_metadata_v2.json',
        'version': '2.0',
        'name': 'Version 2 (MobileNetV2 420-test)',
    },
    'v3': {
        'model_file': 'solarguard_model_v3.keras',
        'metadata_file': 'model_metadata_v3.json',
        'version': '3.0',
        'name': 'Version 3 (MobileNetV2 Argmax 485-test)',
    },
    'v3.1': {
        'model_file': 'solarguard_model_v3_1.keras',
        'metadata_file': 'model_metadata_v3_1.json',
        'version': '3.1',
        'name': 'Version 3.1 (MobileNetV2 Class-Weighted)',
    },
}

# Thread safety lock for model loading
_MODEL_LOCK = threading.Lock()

# Process-level cached singleton references
_CACHED_MODEL = None
_CACHED_METADATA = None
_CACHED_VERSION: Optional[str] = None
_MODEL_LOAD_ATTEMPTED = False
_MODEL_LOAD_ERROR: Optional[str] = None


def resolve_version_key(version: Optional[str] = None) -> str:
    """Normalizes model version string to 'v1', 'v2', 'v3', or 'v3.1'."""
    if not version:
        try:
            from django.conf import settings
            version = getattr(settings, 'SOLARGUARD_MODEL_VERSION', None)
        except Exception:
            pass
    if not version:
        version = os.environ.get('SOLARGUARD_MODEL_VERSION', 'v3')

    ver = str(version).lower().strip()
    if ver in ('3.1', 'v3.1', '3_1', 'v3_1', 'version3.1', 'v3.1.0'):
        return 'v3.1'
    elif ver in ('3', 'v3', '3.0', 'version3', 'v3.0'):
        return 'v3'
    elif ver in ('2', 'v2', '2.0', 'version2', 'v2.0'):
        return 'v2'
    elif ver in ('1', 'v1', '1.0', 'version1', 'v1.0'):
        return 'v1'
    return 'v3'


def get_model_paths(version: Optional[str] = None) -> Tuple[Path, Path, str]:
    """
    Resolves model and metadata paths respecting Django settings or environment variables.
    Supports easy rollback between 'v3' (default), 'v2', and 'v1'.
    """
    ver_key = resolve_version_key(version)
    spec = MODEL_CATALOG[ver_key]

    model_override = os.environ.get('SOLARGUARD_CNN_MODEL_PATH')
    metadata_override = os.environ.get('SOLARGUARD_CNN_METADATA_PATH')

    if not model_override:
        try:
            from django.conf import settings
            if version is None and hasattr(settings, 'CNN_MODEL_PATH'):
                model_override = str(settings.CNN_MODEL_PATH)
        except Exception:
            pass

    if not metadata_override:
        try:
            from django.conf import settings
            if version is None and hasattr(settings, 'CNN_METADATA_PATH'):
                metadata_override = str(settings.CNN_METADATA_PATH)
        except Exception:
            pass

    if model_override:
        model_path = Path(model_override)
    else:
        model_path = DEFAULT_MODELS_DIR / spec['model_file']
        if not model_path.exists():
            colab_path = BASE_DIR / 'Trained model Colab' / spec['model_file']
            if colab_path.exists():
                model_path = colab_path

    if metadata_override:
        metadata_path = Path(metadata_override)
    else:
        metadata_path = DEFAULT_MODELS_DIR / spec['metadata_file']
        if not metadata_path.exists():
            colab_meta = BASE_DIR / 'Trained model Colab' / spec['metadata_file']
            if colab_meta.exists():
                metadata_path = colab_meta

    return model_path, metadata_path, ver_key


def load_model_service(force_reload: bool = False, version: Optional[str] = None) -> Tuple[Optional[Any], Optional[Dict[str, Any]], Optional[str]]:
    """
    Loads Keras model and metadata once per application process.
    Uses compile=False as specified. Never guesses class order.
    Thread-safe lazy loading guarded by _MODEL_LOCK.
    Returns: (model, metadata_dict, error_message)
    """
    global _CACHED_MODEL, _CACHED_METADATA, _CACHED_VERSION, _MODEL_LOAD_ATTEMPTED, _MODEL_LOAD_ERROR

    req_ver = resolve_version_key(version)
    with _MODEL_LOCK:
        if _CACHED_MODEL is not None and _CACHED_METADATA is not None and not force_reload:
            if _CACHED_VERSION == req_ver or version is None:
                return _CACHED_MODEL, _CACHED_METADATA, None

        _MODEL_LOAD_ATTEMPTED = True
        model_path, metadata_path, resolved_ver = get_model_paths(version=version)
        _CACHED_VERSION = resolved_ver

        # 1. Verify file existence
        if not metadata_path.exists():
            _MODEL_LOAD_ERROR = f"Model metadata file missing at '{metadata_path}'."
            logger.error(_MODEL_LOAD_ERROR)
            return None, None, _MODEL_LOAD_ERROR

        if not model_path.exists():
            _MODEL_LOAD_ERROR = f"Model artifact file missing at '{model_path}'."
            logger.error(_MODEL_LOAD_ERROR)
            return None, None, _MODEL_LOAD_ERROR

        # 2. Parse metadata JSON
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            if 'class_names' not in metadata or not isinstance(metadata['class_names'], list):
                _MODEL_LOAD_ERROR = "Invalid metadata: 'class_names' array is required."
                logger.error(_MODEL_LOAD_ERROR)
                return None, None, _MODEL_LOAD_ERROR
            expected_classes = ['Bird-Dropping', 'Dusty', 'Normal', 'Surface-Damage']
            if metadata['class_names'] != expected_classes:
                logger.warning(
                    f"Model classes {metadata['class_names']} differ from expected baseline {expected_classes}"
                )
        except Exception as e:
            _MODEL_LOAD_ERROR = f"Failed to parse model metadata JSON: {e}"
            logger.error(_MODEL_LOAD_ERROR)
            return None, None, _MODEL_LOAD_ERROR

        # 3. Load Keras model with compile=False
        try:
            import tensorflow as tf
            model = tf.keras.models.load_model(str(model_path), compile=False)
            _CACHED_MODEL = model
            _CACHED_METADATA = metadata
            _MODEL_LOAD_ERROR = None
            logger.info(
                f"Loaded SolarGuard CNN model ({resolved_ver}) from '{model_path}' with classes: {metadata['class_names']}"
            )
            return _CACHED_MODEL, _CACHED_METADATA, None
        except Exception as e:
            _MODEL_LOAD_ERROR = f"Failed to load Keras model artifact '{model_path}': {e}"
            logger.exception(_MODEL_LOAD_ERROR)
            return None, None, _MODEL_LOAD_ERROR


def switch_model_version(version: str) -> Tuple[Optional[Any], Optional[Dict[str, Any]], Optional[str]]:
    """
    Switches the active in-memory model to the requested version ('v3', 'v3.1', 'v2', or 'v1').
    Thread-safe dynamic rollback option at runtime.
    """
    global _CACHED_MODEL, _CACHED_METADATA, _CACHED_VERSION, _MODEL_LOAD_ATTEMPTED, _MODEL_LOAD_ERROR
    with _MODEL_LOCK:
        _CACHED_MODEL = None
        _CACHED_METADATA = None
        _CACHED_VERSION = None
        _MODEL_LOAD_ATTEMPTED = False
        _MODEL_LOAD_ERROR = None
    return load_model_service(force_reload=True, version=version)


def preprocess_image(image_input, target_size: Tuple[int, int] = (224, 224)) -> Tuple[Optional[np.ndarray], Optional[str]]:
    """
    Validates image contents using Pillow, handles EXIF orientation,
    converts to RGB, resizes to target_size, and returns float32 batch
    of shape (1, 224, 224, 3) with raw pixel values in range 0-255.
    
    CRITICAL: Does NOT apply external normalization or mobilenet_v2.preprocess_input,
    as Rescaling(1/127.5, offset=-1) is internal to the model.
    """
    try:
        # First pass: verify image integrity
        if hasattr(image_input, 'seek'):
            image_input.seek(0)
            with Image.open(image_input) as test_img:
                test_img.verify()
            image_input.seek(0)
            pil_img = Image.open(image_input)
        else:
            with Image.open(image_input) as test_img:
                test_img.verify()
            pil_img = Image.open(image_input)

        # Handle EXIF rotation (e.g. smartphone camera orientation)
        pil_img = ImageOps.exif_transpose(pil_img)

        # Convert to RGB (discards alpha, converts grayscale to 3-channel RGB)
        if pil_img.mode != 'RGB':
            pil_img = pil_img.convert('RGB')

        # Resize to target size (224, 224) using bilinear interpolation
        pil_img = pil_img.resize(target_size, Image.Resampling.BILINEAR)

        # Convert to float32 array in range 0-255
        img_arr = np.array(pil_img, dtype=np.float32)

        if img_arr.shape != (target_size[0], target_size[1], 3):
            return None, f"Unexpected image shape {img_arr.shape}; expected ({target_size[0]}, {target_size[1]}, 3)."

        # Create batch of shape (1, 224, 224, 3) with raw float32 pixels [0, 255]
        batch = np.expand_dims(img_arr, axis=0)
        return batch, None

    except Exception as e:
        return None, f"Image decoding or validation error: {e}"


def run_cnn_inference(image_input, confidence_threshold: Optional[float] = None, version: Optional[str] = None, margin_threshold: Optional[float] = None) -> Dict[str, Any]:
    """
    Primary inference function for solar panel image classification.
    
    Version 3 specifications:
    - Architecture: MobileNetV2
    - Classes: ['Bird-Dropping', 'Dusty', 'Normal', 'Surface-Damage']
    - Input: RGB, 224x224, raw float32 [0-255]
    - Forward pass: model(batch, training=False)
    - Decision rule: standard argmax (no 0.70 Bird-Dropping threshold)
    - Transparency: uncalibrated softmax scores and uncertainty tracking
    
    Returns structured dictionary:
    {
        'status': 'success' | 'unreadable' | 'model_unavailable' | 'error',
        'predicted_class': str,
        'confidence_score': float, # 0.0 - 100.0 (uncalibrated model score)
        'class_probabilities': dict, # {class_name: float_percentage}
        'margin': float, # top-2 margin in percentage points
        'model_identifier': str,
        'model_version': str,
        'is_mock': bool,
        'is_fallback': bool,
        'is_low_confidence': bool,
        'is_close_margin': bool,
        'is_uncertain': bool,
        'needs_manual_review': bool,
        'uncertainty_notes': list,
        'assessment_disclaimer': str,
        'experimental_note': str,
        'error_message': Optional[str]
    }
    """
    # 1. Load model and metadata
    model, metadata, load_err = load_model_service(version=version)
    if load_err or model is None or metadata is None:
        return {
            'status': 'model_unavailable',
            'predicted_class': 'AI Model Unavailable',
            'confidence_score': 0.0,
            'class_probabilities': {},
            'margin': 0.0,
            'model_identifier': 'Model Unavailable (TensorFlow / Artifact Offline)',
            'model_version': 'Unavailable',
            'is_mock': False,
            'is_fallback': False,
            'is_low_confidence': True,
            'is_close_margin': False,
            'is_uncertain': True,
            'needs_manual_review': True,
            'uncertainty_notes': [f"Model artifact could not be loaded: {load_err}"],
            'assessment_disclaimer': 'Model artifact could not be loaded. No automated visual condition could be derived.',
            'experimental_note': 'The CNN model could not be loaded. Please ensure the Python environment has TensorFlow installed and valid model weights.',
            'error_message': load_err or 'Model artifact could not be loaded.'
        }

    class_names = metadata.get('class_names', ['Bird-Dropping', 'Dusty', 'Normal', 'Surface-Damage'])
    active_ver = resolve_version_key(version)
    catalog_spec = MODEL_CATALOG.get(active_ver, {})
    model_ver = metadata.get('model_version', catalog_spec.get('version', '3.0'))
    model_version_name = f"MobileNetV2 CNN v{model_ver}"
    target_size = tuple(metadata.get('image_size', [224, 224]))

    # 2. Validate and preprocess image
    batch, prep_err = preprocess_image(image_input, target_size=target_size)
    if prep_err or batch is None:
        return {
            'status': 'unreadable',
            'predicted_class': 'Unable to assess / Retake photo',
            'confidence_score': 0.0,
            'class_probabilities': {},
            'margin': 0.0,
            'model_identifier': model_version_name,
            'model_version': model_ver,
            'is_mock': False,
            'is_fallback': False,
            'is_low_confidence': False,
            'is_close_margin': False,
            'is_uncertain': False,
            'needs_manual_review': False,
            'uncertainty_notes': ['Image decoding or validation error'],
            'assessment_disclaimer': 'The image content could not be read or decoded cleanly. Please retake the photo under clear lighting.',
            'experimental_note': 'The image content could not be read or decoded cleanly. Please retake the photo under clear lighting.',
            'error_message': prep_err
        }

    # 3. Model Prediction with training=False
    try:
        import tensorflow as tf
        
        # Explicitly invoke model with training=False to disable data augmentation and dropout layers
        raw_preds = model(batch, training=False)
        if hasattr(raw_preds, 'numpy'):
            raw_output = raw_preds.numpy()[0]
        else:
            raw_output = np.array(raw_preds)[0]

        # Check if softmax is required (apply softmax if raw logits are returned)
        if not np.isclose(np.sum(raw_output), 1.0, atol=1e-2):
            probs = tf.nn.softmax(raw_output).numpy()
        else:
            probs = raw_output

        # Construct probability dictionary using exact class_names ordering
        probabilities = {}
        for idx, cname in enumerate(class_names):
            if idx < len(probs):
                probabilities[cname] = round(float(probs[idx]) * 100.0, 2)
            else:
                probabilities[cname] = 0.0

        # Standard argmax across the four outputs — no experimental 0.70 threshold applied
        top_idx = int(np.argmax(probs))
        predicted_class = class_names[top_idx]
        confidence_score = round(float(probs[top_idx]) * 100.0, 1)

        # Evaluate prediction uncertainty and margin between top two classes
        sorted_probs = np.sort(probs)[::-1]
        prob_margin = float(sorted_probs[0] - sorted_probs[1]) if len(sorted_probs) > 1 else 1.0
        margin_pct = round(prob_margin * 100.0, 1)

        # Configurable low-confidence and margin baselines
        if confidence_threshold is None:
            try:
                from django.conf import settings
                confidence_threshold = getattr(settings, 'CNN_CONFIDENCE_THRESHOLD', 60.0)
            except Exception:
                confidence_threshold = 60.0

        if margin_threshold is None:
            try:
                from django.conf import settings
                margin_threshold = getattr(settings, 'CNN_MARGIN_THRESHOLD', 15.0)
            except Exception:
                margin_threshold = 15.0

        is_low_conf = bool(confidence_score < confidence_threshold)
        is_close_margin = bool(margin_pct < margin_threshold) # Top-2 classes within 15 percentage points
        is_uncertain = is_low_conf or is_close_margin
        needs_manual_review = bool(is_uncertain or predicted_class in ('Surface-Damage', 'Bird-Dropping'))

        uncertainty_notes = []
        if is_low_conf:
            uncertainty_notes.append(
                f"Model score ({confidence_score}%) is below confidence baseline ({confidence_threshold}%)."
            )
        if is_close_margin:
            uncertainty_notes.append(
                f"Top predictions are closely contested (margin {margin_pct}%)."
            )
        if needs_manual_review and predicted_class == 'Surface-Damage':
            uncertainty_notes.append(
                "Potential physical surface damage detected; on-site manual review strongly recommended."
            )

        assessment_disclaimer = (
            "AI-assisted visual assessment; scores represent uncalibrated model probabilities and "
            "must not be interpreted as definitive electrical or physical fault diagnoses."
        )
        experimental_note = " ".join(uncertainty_notes) if uncertainty_notes else assessment_disclaimer

        return {
            'status': 'success',
            'predicted_class': predicted_class,
            'confidence_score': confidence_score,
            'class_probabilities': probabilities,
            'margin': margin_pct,
            'model_identifier': model_version_name,
            'model_version': model_ver,
            'is_mock': False,
            'is_fallback': False,
            'is_low_confidence': is_low_conf,
            'is_close_margin': is_close_margin,
            'is_uncertain': is_uncertain,
            'needs_manual_review': needs_manual_review,
            'uncertainty_notes': uncertainty_notes,
            'assessment_disclaimer': assessment_disclaimer,
            'experimental_note': experimental_note,
            'error_message': None
        }

    except Exception as e:
        logger.exception(f"Inference execution failed: {e}")
        return {
            'status': 'error',
            'predicted_class': 'Unable to assess / Retake photo',
            'confidence_score': 0.0,
            'class_probabilities': {},
            'margin': 0.0,
            'model_identifier': model_version_name,
            'model_version': model_ver,
            'is_mock': False,
            'is_fallback': False,
            'is_low_confidence': False,
            'is_close_margin': False,
            'is_uncertain': False,
            'needs_manual_review': False,
            'uncertainty_notes': [f"Inference execution error: {e}"],
            'assessment_disclaimer': 'Inference pipeline encountered an error during prediction.',
            'experimental_note': 'Inference pipeline encountered an error during prediction.',
            'error_message': str(e)
        }


def evaluate_prediction_uncertainty(
    class_probabilities: Optional[Dict[str, float]] = None,
    predicted_class: Optional[str] = None,
    confidence_score: Optional[float] = None,
    confidence_threshold: Optional[float] = None,
    margin_threshold: Optional[float] = None,
    is_unavailable: bool = False,
) -> Dict[str, Any]:
    """
    Transparent, rule-based uncertainty assessment for SolarGuard predictions.
    
    Triage Rules:
    - If model output is invalid, offline, or unavailable: status = 'Analysis Unavailable'.
    - If leading score < confidence_threshold (default 60.0%) OR 
      top-two score margin < margin_threshold (default 15.0 percentage points):
      status = 'Review Recommended' (Uncertain Classification).
    - Otherwise:
      status = 'Clear Lead' (Standard Classification).
      
    NOTE: These thresholds are provisional UI/operational triage guidelines,
    NOT statistically calibrated confidence intervals or guarantees of physical fault absence.
    """
    # 1. Resolve thresholds from settings if not explicitly passed
    if confidence_threshold is None:
        try:
            from django.conf import settings
            confidence_threshold = getattr(settings, 'CNN_CONFIDENCE_THRESHOLD', 60.0)
        except Exception:
            confidence_threshold = 60.0

    if margin_threshold is None:
        try:
            from django.conf import settings
            margin_threshold = getattr(settings, 'CNN_MARGIN_THRESHOLD', 15.0)
        except Exception:
            margin_threshold = 15.0

    # 2. Check for unavailable / invalid outputs
    pred_str = (predicted_class or '').lower()
    is_unavail = (
        is_unavailable or 
        not class_probabilities or 
        'unavailable' in pred_str or 
        'offline' in pred_str or 
        'error' in pred_str or 
        'unable' in pred_str
    )

    if is_unavail or not class_probabilities:
        top_name = predicted_class if predicted_class and 'unavailable' not in pred_str else "Analysis Unavailable"
        return {
            'status': 'unavailable',
            'status_label': 'Analysis Unavailable',
            'status_sublabel': 'Offline / Unreadable',
            'is_unavailable': True,
            'is_uncertain': True,
            'needs_manual_review': True,
            'sorted_scores': [],
            'top_class': top_name,
            'top_score': float(confidence_score or 0.0),
            'second_class': None,
            'second_score': 0.0,
            'margin': 0.0,
            'is_low_confidence': False,
            'is_close_margin': False,
            'badge_class': 'badge-fault-unable',
            'triage_badge_class': 'bg-secondary text-white',
            'triage_title': 'Analysis Unavailable',
            'triage_detail': 'Automated classification is unavailable for this photograph. Model output was not obtained or is invalid.',
            'confidence_threshold': confidence_threshold,
            'margin_threshold': margin_threshold,
            'provisional_disclaimer': 'Model output unavailable. No automated visual condition could be derived.'
        }

    # 3. Sort class scores descending
    # Standard class badge & bar color mapping using SolarGuard Design System
    BADGE_MAP = {
        'Normal': 'badge-fault-normal',
        'Dusty': 'badge-fault-dusty',
        'Bird-Dropping': 'badge-fault-bird',
        'Surface-Damage': 'badge-fault-cracked',
        'Cracked': 'badge-fault-cracked',
    }
    
    BAR_COLOR_MAP = {
        'Normal': 'bg-success',
        'Dusty': 'bg-warning',
        'Bird-Dropping': 'bg-warning',
        'Surface-Damage': 'bg-danger',
        'Cracked': 'bg-danger',
    }

    sorted_items = sorted(class_probabilities.items(), key=lambda x: x[1], reverse=True)
    
    top_class, top_score = sorted_items[0]
    top_score = float(top_score)

    if len(sorted_items) > 1:
        second_class, second_score = sorted_items[1]
        second_score = float(second_score)
        margin = round(top_score - second_score, 2)
    else:
        second_class, second_score = None, 0.0
        margin = top_score

    is_low_conf = bool(top_score < confidence_threshold)
    is_close_margin = bool(margin < margin_threshold)
    is_uncertain = bool(is_low_conf or is_close_margin)
    needs_manual_review = bool(is_uncertain or top_class in ('Surface-Damage', 'Bird-Dropping'))

    sorted_scores = []
    for idx, (cname, sc) in enumerate(sorted_items):
        sc_val = float(sc)
        is_top = (idx == 0)
        bar_col = BAR_COLOR_MAP.get(cname, 'bg-primary') if is_top else 'bg-secondary bg-opacity-50'
        sorted_scores.append({
            'class_name': cname,
            'score': round(sc_val, 1),
            'raw_score': sc_val,
            'percentage_str': f"{sc_val:.1f}%",
            'bar_width': f"{min(max(sc_val, 0.0), 100.0):.1f}%",
            'is_top': is_top,
            'badge_class': BADGE_MAP.get(cname, 'badge-fault-unable'),
            'bar_color_class': bar_col,
        })

    uncertainty_reasons = []
    if is_low_conf:
        uncertainty_reasons.append(
            f"Top score ({top_score:.1f}%) is below the {confidence_threshold:.0f}% confidence baseline."
        )
    if is_close_margin:
        uncertainty_reasons.append(
            f"Top predictions are closely contested (margin of {margin:.1f}% between {top_class} and {second_class})."
        )

    if is_uncertain:
        status_label = 'Review Recommended'
        status_sublabel = 'Uncertain Classification'
        triage_badge_class = 'badge bg-warning-subtle text-warning-emphasis border border-warning-subtle'
        triage_title = 'Review Recommended — Uncertain Classification'
        triage_detail = " ".join(uncertainty_reasons) + " Ambiguous visual features detected; on-site technician review is recommended before work order commitment."
    else:
        status_label = 'Clear Lead'
        status_sublabel = 'Standard Classification'
        triage_badge_class = 'badge bg-success-subtle text-success-emphasis border border-success-subtle'
        triage_title = 'Standard Lead Classification'
        triage_detail = f"Leading prediction {top_class} exceeds baseline confidence ({top_score:.1f}%) with a clear margin ({margin:.1f}%)."

    return {
        'status': 'uncertain' if is_uncertain else 'clear',
        'status_label': status_label,
        'status_sublabel': status_sublabel,
        'is_unavailable': False,
        'is_uncertain': is_uncertain,
        'is_low_confidence': is_low_conf,
        'is_close_margin': is_close_margin,
        'needs_manual_review': needs_manual_review,
        'sorted_scores': sorted_scores,
        'top_class': top_class,
        'top_score': round(top_score, 1),
        'second_class': second_class,
        'second_score': round(second_score, 1),
        'margin': round(margin, 1),
        'badge_class': BADGE_MAP.get(top_class, 'badge-fault-unable'),
        'triage_badge_class': triage_badge_class,
        'triage_title': triage_title,
        'triage_detail': triage_detail,
        'uncertainty_notes': uncertainty_reasons,
        'confidence_threshold': confidence_threshold,
        'margin_threshold': margin_threshold,
        'provisional_disclaimer': (
            f"Scores represent uncalibrated model confidence scores, not guaranteed probabilities or accuracy. "
            f"Provisional triage thresholds applied: Top score < {confidence_threshold:.0f}% or Top-2 margin < {margin_threshold:.0f}%."
        )
    }

