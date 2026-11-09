"""
SolarGuard Version 3 CNN Smoke Test Suite
Verifies:
1. Model loading (solarguard_model_v3.keras and model_metadata_v3.json)
2. Input preprocessing (RGB, 224x224, float32 range [0, 255], no external normalization)
3. Output shape (1, 4) with training=False execution
4. Class mapping exact order and standard argmax (no 0.70 bird dropping threshold)
5. End-to-end Django inspection workflow
6. Easy rollback to Version 2 and Version 1
"""

import os
import io
import datetime
import numpy as np
from PIL import Image, ImageDraw
import tensorflow as tf

from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile

from core.models import Panel, Inspection
from ml_engine.inference import (
    load_model_service,
    preprocess_image,
    run_cnn_inference,
    switch_model_version,
    get_model_paths,
    resolve_version_key,
    MODEL_CATALOG
)
from ml_engine.predictor import predict_fault, predict_degradation


class SolarGuardV3SmokeTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='v3tester', password='testpassword123')
        today = datetime.date.today()
        self.panel = Panel.objects.create(
            user=self.user,
            serial_number='SG-V3-TEST-PANEL',
            site_location='Solar Array V3 Lab',
            install_date=today - datetime.timedelta(days=180),
            last_cleaned_date=today - datetime.timedelta(days=20)
        )

        # Create a valid test image with geometric patterns
        img = Image.new('RGB', (300, 300), color=(40, 70, 110))
        draw = ImageDraw.Draw(img)
        draw.line([(20, 20), (280, 280)], fill=(220, 220, 220), width=4)
        draw.rectangle([(50, 50), (150, 150)], outline=(255, 200, 0), width=3)
        img_io = io.BytesIO()
        img.save(img_io, format='JPEG')
        img_io.seek(0)
        self.test_img_bytes = img_io.getvalue()
        self.uploaded_image = SimpleUploadedFile("test_panel_v3.jpg", self.test_img_bytes, content_type="image/jpeg")

    def test_01_model_loading_v3(self):
        """Smoke Test 1: Verify Version 3 model artifact and metadata load cleanly with compile=False."""
        model, metadata, err = load_model_service(force_reload=True, version='v3')
        self.assertIsNone(err, f"Model loading failed: {err}")
        self.assertIsNotNone(model, "Model object is None")
        self.assertIsNotNone(metadata, "Metadata dictionary is None")
        
        self.assertEqual(metadata.get('model_version'), '3.0')
        self.assertEqual(metadata.get('architecture'), 'MobileNetV2')
        self.assertEqual(metadata.get('decision_rule'), 'argmax')
        self.assertIsNone(metadata.get('bird_dropping_threshold'))
        
        model_path, metadata_path, ver_key = get_model_paths(version='v3')
        self.assertEqual(ver_key, 'v3')
        self.assertTrue(model_path.exists(), f"V3 model file missing at {model_path}")
        self.assertTrue(metadata_path.exists(), f"V3 metadata file missing at {metadata_path}")
        print(f"\n[Smoke 1 PASS] V3 model loaded: {model_path.name} ({metadata.get('model_version')})")

    def test_02_input_preprocessing(self):
        """Smoke Test 2: Input preprocessing must produce RGB, (1, 224, 224, 3), float32 in [0, 255] with no extra normalization."""
        # Test with raw image bytes
        batch, prep_err = preprocess_image(io.BytesIO(self.test_img_bytes), target_size=(224, 224))
        self.assertIsNone(prep_err)
        self.assertIsNotNone(batch)

        # Shape validation
        self.assertEqual(batch.shape, (1, 224, 224, 3))
        # Data type validation
        self.assertEqual(batch.dtype, np.float32)
        # Pixel range validation: raw pixel values [0, 255]
        self.assertGreaterEqual(float(np.min(batch)), 0.0)
        self.assertLessEqual(float(np.max(batch)), 255.0)
        # Verify it has not been externally normalized to [-1, 1] or [0, 1]
        self.assertGreater(float(np.max(batch)), 1.0, "Input appears inappropriately normalized to [0, 1]!")
        print(f"[Smoke 2 PASS] Preprocessing output shape: {batch.shape}, dtype: {batch.dtype}, min: {np.min(batch)}, max: {np.max(batch)}")

    def test_03_output_shape_and_training_false(self):
        """Smoke Test 3: Output shape must be (1, 4) with deterministic execution using training=False."""
        model, metadata, err = load_model_service(force_reload=False, version='v3')
        self.assertIsNone(err)

        dummy_batch = np.random.uniform(0, 255, size=(1, 224, 224, 3)).astype(np.float32)
        
        # Invoke model with training=False
        output_1 = model(dummy_batch, training=False).numpy()
        output_2 = model(dummy_batch, training=False).numpy()

        self.assertEqual(output_1.shape, (1, 4))
        # Deterministic check: with training=False, augmentation & dropout are inactive
        self.assertTrue(np.allclose(output_1, output_2, atol=1e-5), "Inference with training=False was not deterministic!")
        # Softmax sum check
        self.assertTrue(np.isclose(np.sum(output_1[0]), 1.0, atol=1e-2), "Model output does not sum to 1.0!")
        print(f"[Smoke 3 PASS] Output shape: {output_1.shape}, deterministic: True, sum: {np.sum(output_1[0]):.4f}")

    def test_04_class_mapping_and_argmax(self):
        """Smoke Test 4: Exactly 4 classes in exact order; pure argmax applied without 0.70 threshold."""
        model, metadata, err = load_model_service(force_reload=False, version='v3')
        self.assertIsNone(err)

        expected_classes = ['Bird-Dropping', 'Dusty', 'Normal', 'Surface-Damage']
        self.assertEqual(metadata['class_names'], expected_classes, "Class mapping or order does not match requirement!")

        # Verify argmax behavior: run inference
        res = run_cnn_inference(io.BytesIO(self.test_img_bytes), version='v3')
        self.assertEqual(res['status'], 'success')
        self.assertIn(res['predicted_class'], expected_classes)
        self.assertIn('class_probabilities', res)
        self.assertEqual(list(res['class_probabilities'].keys()), expected_classes)
        
        # Verify that predicted_class strictly equals the class with highest probability (pure argmax)
        probs_dict = res['class_probabilities']
        max_class = max(probs_dict, key=probs_dict.get)
        self.assertEqual(res['predicted_class'], max_class, "Decision rule did not use standard argmax!")
        print(f"[Smoke 4 PASS] Class mapping verified: {expected_classes}, predicted: {res['predicted_class']}, score: {res['confidence_score']}%")

    def test_05_end_to_end_django_inspection(self):
        """Smoke Test 5: End-to-end Django image upload, inference, and inspection report view."""
        self.client.login(username='v3tester', password='testpassword123')

        post_data = {
            'panel': self.panel.id,
            'image': self.uploaded_image,
            'notes': 'V3 smoke test inspection run'
        }

        response = self.client.post(reverse('inspect'), post_data, follow=True)
        self.assertEqual(response.status_code, 200)

        # Verify inspection record in database
        ins = Inspection.objects.filter(panel=self.panel).first()
        self.assertIsNotNone(ins)
        self.assertIn(ins.predicted_class, ['Bird-Dropping', 'Dusty', 'Normal', 'Surface-Damage'])
        self.assertIn('MobileNetV2 CNN v3.0', ins.model_identifier)
        self.assertFalse(ins.is_mock_prediction)

        # Verify report rendering
        detail_url = reverse('result_detail', kwargs={'pk': ins.id})
        res_page = self.client.get(detail_url)
        self.assertEqual(res_page.status_code, 200)
        self.assertContains(res_page, "Real CNN Inference Active")
        self.assertContains(res_page, "MobileNetV2 CNN v3.0")
        self.assertContains(res_page, "Uncalibrated Softmax Probabilities")
        self.assertContains(res_page, "AI-assisted visual assessment")
        print(f"[Smoke 5 PASS] End-to-end Django inspection complete. Identifier: {ins.model_identifier}")

    def test_06_easy_rollback_to_v2_and_v1(self):
        """Smoke Test 6: Verify smooth rollback to Version 2 and Version 1."""
        # Rollback to V2
        model_v2, meta_v2, err_v2 = switch_model_version('v2')
        self.assertIsNone(err_v2)
        self.assertIsNotNone(model_v2)
        self.assertEqual(meta_v2.get('model_version'), '2.0')

        res_v2 = run_cnn_inference(io.BytesIO(self.test_img_bytes), version='v2')
        self.assertEqual(res_v2['status'], 'success')
        self.assertEqual(res_v2['model_version'], '2.0')
        print(f"[Smoke 6 PASS] Rollback to V2 verified ({res_v2['model_identifier']})")

        # Rollback to V1
        model_v1, meta_v1, err_v1 = switch_model_version('v1')
        self.assertIsNone(err_v1)
        self.assertIsNotNone(model_v1)

        res_v1 = run_cnn_inference(io.BytesIO(self.test_img_bytes), version='v1')
        self.assertEqual(res_v1['status'], 'success')
        print(f"[Smoke 6 PASS] Rollback to V1 verified ({res_v1['model_identifier']})")

        # Restore V3 as active
        model_v3, meta_v3, err_v3 = switch_model_version('v3')
        self.assertIsNone(err_v3)
        self.assertEqual(meta_v3.get('model_version'), '3.0')
        print(f"[Smoke 6 PASS] Active model restored to V3.")
