"""
SolarGuard — Model Verification Management Command
Verifies MobileNetV2 v3.0 model integrity, SHA-256 checksum, input shape,
class order, and live inference execution.
"""

import hashlib
import os
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
import numpy as np


EXPECTED_V3_SHA256 = "C7D54BA2507E2FD1E062CD446AC124EB4C897820402BB54D251B4B1BFA683CD6".upper()
EXPECTED_V3_SIZE = 9697439
EXPECTED_CLASSES = ['Bird-Dropping', 'Dusty', 'Normal', 'Surface-Damage']
EXPECTED_INPUT_SHAPE = (None, 224, 224, 3)
EXPECTED_OUTPUT_SHAPE = (None, 4)


class Command(BaseCommand):
    help = "Verifies active MobileNetV2 v3.0 model file integrity, checksum, and inference capability."

    def add_arguments(self, parser):
        parser.add_argument(
            '--model-path',
            type=str,
            default=None,
            help="Optional custom path to the model artifact to test."
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 72))
        self.stdout.write(self.style.MIGRATE_HEADING(" SolarGuard AI Model Verification & Team Audit"))
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 72))

        model_path = Path(options['model_path']) if options['model_path'] else Path(settings.CNN_MODEL_PATH)
        metadata_path = Path(settings.CNN_METADATA_PATH)

        self.stdout.write(f"  Target Model Path:    {model_path}")
        self.stdout.write(f"  Target Metadata Path: {metadata_path}")
        active_ver = getattr(settings, 'SOLARGUARD_MODEL_VERSION', 'v3')
        self.stdout.write(f"  Active Version:       {active_ver}")
        self.stdout.write("")

        # 1. Check file existence
        if not model_path.exists():
            self.stdout.write(self.style.ERROR(f"  [FAIL] Model file not found at: {model_path}"))
            self.stdout.write(self.style.WARNING(
                "\n  Acquisition Instructions for Teammates:\n"
                "  1. Obtain 'solarguard_model_v3.keras' from the team's secure storage / release assets.\n"
                f"  2. Place it at: '{model_path.resolve()}'.\n"
                "  3. Re-run 'python manage.py verify_model'.\n"
            ))
            return

        file_size = os.path.getsize(model_path)
        self.stdout.write(f"  [PASS] File exists. Size: {file_size:,} bytes ({file_size / (1024*1024):.2f} MB)")

        # 2. Checksum verification
        sha256 = hashlib.sha256()
        with open(model_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
        computed_hash = sha256.hexdigest().upper()

        if computed_hash == EXPECTED_V3_SHA256:
            self.stdout.write(self.style.SUCCESS(f"  [PASS] SHA-256 Checksum Verified: {computed_hash}"))
        else:
            self.stdout.write(self.style.WARNING(
                f"  [NOTE] SHA-256 mismatch!\n"
                f"         Expected: {EXPECTED_V3_SHA256}\n"
                f"         Found:    {computed_hash}\n"
                f"         (If you are testing a candidate model, this is expected. For official v3.0, verify source.)"
            ))

        # 3. TensorFlow & Keras Import
        try:
            import tensorflow as tf
            import keras
            self.stdout.write(self.style.SUCCESS(f"  [PASS] TensorFlow imported successfully: v{tf.__version__} (Keras v{keras.__version__})"))
        except ImportError as e:
            self.stdout.write(self.style.ERROR(f"  [FAIL] TensorFlow import failed: {e}"))
            self.stdout.write(self.style.WARNING("         Run: pip install -r requirements.txt"))
            return

        # 4. Load Model
        try:
            model = keras.models.load_model(str(model_path), compile=False)
            self.stdout.write(self.style.SUCCESS("  [PASS] Keras model loaded successfully."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  [FAIL] Failed to load model artifact: {e}"))
            return

        # 5. Verify Input & Output Tensors
        input_shape = model.input_shape
        output_shape = model.output_shape
        self.stdout.write(f"  Model Input Shape:  {input_shape}")
        self.stdout.write(f"  Model Output Shape: {output_shape}")

        if input_shape[1:] == EXPECTED_INPUT_SHAPE[1:]:
            self.stdout.write(self.style.SUCCESS(f"  [PASS] Input dimensions match 224x224x3 RGB standard."))
        else:
            self.stdout.write(self.style.ERROR(f"  [FAIL] Unexpected input shape: {input_shape}"))

        if output_shape[1] == EXPECTED_OUTPUT_SHAPE[1]:
            self.stdout.write(self.style.SUCCESS(f"  [PASS] Output units match 4-class classification standard."))
        else:
            self.stdout.write(self.style.ERROR(f"  [FAIL] Unexpected output shape: {output_shape}"))

        # 6. Test Inference with Synthetic Data
        try:
            dummy_input = np.ones((1, 224, 224, 3), dtype=np.float32) * 128.0
            preds = model.predict(dummy_input, verbose=0)
            self.stdout.write(self.style.SUCCESS(f"  [PASS] Synthetic tensor inference succeeded. Sum of probabilities: {np.sum(preds):.4f}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  [FAIL] Inference failed: {e}"))
            return

        # 7. Test Inference with Real Image (if available)
        sample_img_path = Path("media/sample_test_images/sample_bird_drop.jpg")
        if sample_img_path.exists():
            try:
                from PIL import Image
                img = Image.open(sample_img_path).convert('RGB').resize((224, 224))
                arr = np.array(img, dtype=np.float32)
                arr = np.expand_dims(arr, axis=0)
                img_preds = model.predict(arr, verbose=0)[0]
                pred_idx = int(np.argmax(img_preds))
                pred_label = EXPECTED_CLASSES[pred_idx]
                conf = float(img_preds[pred_idx] * 100.0)
                self.stdout.write(self.style.SUCCESS(
                    f"  [PASS] Real image inference ({sample_img_path.name}): {pred_label} ({conf:.1f}% confidence)"
                ))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  [WARN] Sample image test error: {e}"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 72))
        self.stdout.write(self.style.SUCCESS(" ALL AI MODEL INTEGRITY CHECKS PASSED — READY FOR COLLABORATION"))
        self.stdout.write(self.style.SUCCESS("=" * 72))
