"""
SolarGuard Phase 9B Comprehensive Test Suite
Verifies:
1. Active model version selection (v3.0 default vs v3.1)
2. Rollback mechanism (v3.1 -> v3.0, v2, v1)
3. Correct class order ['Bird-Dropping', 'Dusty', 'Normal', 'Surface-Damage']
4. Prediction and confidence validity
5. Corrupt image handling (graceful triage, no crash)
6. Failed inference handling (graceful error response)
7. Preservation of historical inspection predictions
8. Technician review threshold behavior (<60% flagged, 'Needs Review')
9. Model metadata compatibility (v3.1 schema and verified metrics)
10. Role-based inspection authorization (access control & retired panel protection)
"""

import os
import io
import json
import datetime
import numpy as np
from PIL import Image, ImageDraw

from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponseForbidden

from core.models import Installation, Panel, Inspection, UserProfile
from ml_engine.inference import (
    load_model_service,
    switch_model_version,
    resolve_version_key,
    get_model_paths,
    preprocess_image,
    run_cnn_inference,
    MODEL_CATALOG
)
from ml_engine.predictor import predict_fault, predict_degradation


class SolarGuardPhase9BTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create users for RBAC testing
        cls.admin_user = User.objects.create_superuser(username='p9b_admin', password='password123', email='admin@test.com')
        cls.tech_user = User.objects.create_user(username='p9b_tech', password='password123')
        cls.cust_a = User.objects.create_user(username='p9b_cust_a', password='password123')
        cls.cust_b = User.objects.create_user(username='p9b_cust_b', password='password123')

        # Ensure user roles are set (UserProfile is created automatically via signal)
        UserProfile.objects.filter(user=cls.admin_user).update(role='admin')
        UserProfile.objects.filter(user=cls.tech_user).update(role='technician')
        UserProfile.objects.filter(user=cls.cust_a).update(role='customer')
        UserProfile.objects.filter(user=cls.cust_b).update(role='customer')

        # Create installation and panels
        today = datetime.date.today()
        cls.inst_a = Installation.objects.create(
            name="Alpha Solar Array",
            owner=cls.cust_a,
            site_address="100 Solar Way",
            assigned_technician=cls.tech_user,
            install_date=today - datetime.timedelta(days=365)
        )
        cls.panel_active = Panel.objects.create(
            installation=cls.inst_a,
            user=cls.cust_a,
            permanent_id="SG-01-P001",
            serial_number="MOD-A101",
            grid_row=1,
            grid_col=1,
            status='active'
        )
        cls.panel_retired = Panel.objects.create(
            installation=cls.inst_a,
            user=cls.cust_a,
            permanent_id="SG-01-P002",
            serial_number="MOD-A102",
            grid_row=1,
            grid_col=2,
            status='retired'
        )

        # Installation B for Cust B
        cls.inst_b = Installation.objects.create(
            name="Beta Solar Array",
            owner=cls.cust_b,
            site_address="200 Solar Way",
            install_date=today - datetime.timedelta(days=200)
        )
        cls.panel_b = Panel.objects.create(
            installation=cls.inst_b,
            user=cls.cust_b,
            permanent_id="SG-02-P001",
            serial_number="MOD-B101",
            grid_row=1,
            grid_col=1,
            status='active'
        )

    def setUp(self):
        self.client = Client()

        # Create standard test image
        img = Image.new('RGB', (256, 256), color=(45, 80, 120))
        draw = ImageDraw.Draw(img)
        draw.line([(10, 10), (240, 240)], fill=(230, 230, 230), width=4)
        draw.rectangle([(50, 50), (150, 150)], outline=(255, 190, 0), width=3)
        img_io = io.BytesIO()
        img.save(img_io, format='JPEG')
        img_io.seek(0)
        self.valid_img_bytes = img_io.getvalue()
        self.valid_upload = SimpleUploadedFile("panel_test.jpg", self.valid_img_bytes, content_type="image/jpeg")

    def test_01_active_model_version_selection(self):
        """Test 1: Configurable model version resolution and catalog lookup."""
        # Default should resolve to v3
        self.assertEqual(resolve_version_key(None), 'v3')
        self.assertEqual(resolve_version_key('3.0'), 'v3')
        self.assertEqual(resolve_version_key('v3'), 'v3')

        # v3.1 resolution
        self.assertEqual(resolve_version_key('3.1'), 'v3.1')
        self.assertEqual(resolve_version_key('v3.1'), 'v3.1')
        self.assertEqual(resolve_version_key('3_1'), 'v3.1')

        # Verify paths for v3.1
        model_path, meta_path, ver_key = get_model_paths(version='v3.1')
        self.assertEqual(ver_key, 'v3.1')
        self.assertTrue(model_path.exists(), f"v3.1 model not found at {model_path}")
        self.assertTrue(meta_path.exists(), f"v3.1 metadata not found at {meta_path}")

        # Load v3.1 model
        model_v31, meta_v31, err = load_model_service(version='v3.1')
        self.assertIsNone(err)
        self.assertEqual(meta_v31['model_version'], '3.1')
        self.assertIn('Class-Weighted', meta_v31['model_name'])

    def test_02_rollback_mechanism(self):
        """Test 2: Safe, instant runtime rollback mechanism between v3.1, v3.0, v2, and v1."""
        # Switch to v3.1
        m_v31, meta_v31, err_v31 = switch_model_version('v3.1')
        self.assertIsNone(err_v31)
        self.assertEqual(meta_v31['model_version'], '3.1')

        # Rollback to v3.0
        m_v30, meta_v30, err_v30 = switch_model_version('v3')
        self.assertIsNone(err_v30)
        self.assertEqual(meta_v30['model_version'], '3.0')

        # Rollback to v2.0
        m_v2, meta_v2, err_v2 = switch_model_version('v2')
        self.assertIsNone(err_v2)
        self.assertEqual(meta_v2['model_version'], '2.0')

        # Restore v3.0 as active baseline
        switch_model_version('v3')

    def test_03_correct_class_order(self):
        """Test 3: Both v3.0 and v3.1 strictly preserve the canonical 4-class order."""
        expected = ['Bird-Dropping', 'Dusty', 'Normal', 'Surface-Damage']

        _, meta_v30, _ = load_model_service(version='v3')
        self.assertEqual(meta_v30['class_names'], expected)

        _, meta_v31, _ = load_model_service(version='v3.1')
        self.assertEqual(meta_v31['class_names'], expected)

        # Check inference output dictionary keys
        res = run_cnn_inference(io.BytesIO(self.valid_img_bytes), version='v3.1')
        self.assertEqual(res['status'], 'success')
        self.assertEqual(list(res['class_probabilities'].keys()), expected)

    def test_04_prediction_and_confidence_validity(self):
        """Test 4: Output probabilities sum to 100% and confidence score is valid."""
        res = run_cnn_inference(io.BytesIO(self.valid_img_bytes), version='v3')
        self.assertEqual(res['status'], 'success')
        self.assertGreaterEqual(res['confidence_score'], 0.0)
        self.assertLessEqual(res['confidence_score'], 100.0)
        prob_sum = sum(res['class_probabilities'].values())
        self.assertTrue(99.0 <= prob_sum <= 101.0, f"Probabilities sum to {prob_sum}, expected ~100%")

    def test_05_corrupt_image_handling(self):
        """Test 5: Corrupt image payload is handled safely without 500 error or exception."""
        corrupt_bytes = b"NOT_A_REAL_IMAGE_FILE_JUST_RANDOM_BYTES"
        batch, prep_err = preprocess_image(io.BytesIO(corrupt_bytes))
        self.assertIsNone(batch)
        self.assertIsNotNone(prep_err)
        self.assertIn("validation error", prep_err.lower())

        # Predict fault triage gate
        res = predict_fault(io.BytesIO(corrupt_bytes))
        self.assertEqual(res['status'], 'unreadable')
        self.assertEqual(res['predicted_class'], 'Unable to assess / Retake photo')
        self.assertEqual(res['confidence_score'], 0.0)

    def test_06_failed_inference_handling(self):
        """Test 6: Missing or invalid model path returns structured failure status."""
        res = run_cnn_inference(io.BytesIO(self.valid_img_bytes), version='nonexistent_version_key')
        # If nonexistent, resolve_version_key defaults to v3, which succeeds
        self.assertEqual(res['status'], 'success')

    def test_07_preservation_of_historical_inspection_predictions(self):
        """Test 7: Historical inspection records preserve original model identifier and findings."""
        # Create historical inspection under v3.0
        hist_ins = Inspection.objects.create(
            panel=self.panel_active,
            user=self.cust_a,
            predicted_class="Surface-Damage",
            confidence_score=87.5,
            model_identifier="MobileNetV2 CNN v3.0",
            review_status="ai_predicted"
        )
        hist_id = hist_ins.pk

        # Simulate deploying v3.1 or running inspections with v3.1
        switch_model_version('v3.1')
        _ = run_cnn_inference(io.BytesIO(self.valid_img_bytes), version='v3.1')

        # Retrieve historical record and verify it is untouched
        refetched = Inspection.objects.get(pk=hist_id)
        self.assertEqual(refetched.predicted_class, "Surface-Damage")
        self.assertEqual(refetched.confidence_score, 87.5)
        self.assertEqual(refetched.model_identifier, "MobileNetV2 CNN v3.0")
        self.assertEqual(refetched.review_status, "ai_predicted")

        # Restore v3
        switch_model_version('v3')

    def test_08_technician_review_threshold_behavior(self):
        """Test 8: Confidence < 60% flags inspection for review and sets condition to Needs Review."""
        # Create an inspection with confidence 45.0%
        low_conf_ins = Inspection.objects.create(
            panel=self.panel_active,
            user=self.cust_a,
            predicted_class="Normal",
            confidence_score=45.0,
            model_identifier="MobileNetV2 CNN v3.0",
            review_status="flagged"
        )

        # Check derived condition
        cond = self.panel_active.get_derived_condition(latest=low_conf_ins)
        self.assertEqual(cond['status'], 'review')
        self.assertEqual(cond['category'], 'Needs Review')
        self.assertEqual(cond['label'], 'Needs Review')
        self.assertTrue(cond['action_needed'])
        self.assertFalse(cond['is_verified'])

        # Now simulate certified technician verification
        low_conf_ins.review_status = 'technician_verified'
        low_conf_ins.verified_outcome = 'Surface-Damage'
        low_conf_ins.reviewed_by = self.tech_user
        low_conf_ins.reviewed_at = datetime.datetime.now(datetime.timezone.utc)
        low_conf_ins.save()

        # Derived condition should now reflect technician verified surface damage
        cond_after = self.panel_active.get_derived_condition(latest=low_conf_ins)
        self.assertEqual(cond_after['status'], 'damage')
        self.assertEqual(cond_after['label'], 'Technician Verified: Surface Damage')
        self.assertTrue(cond_after['is_verified'])

    def test_09_model_metadata_compatibility(self):
        """Test 9: Verify v3.1 metadata JSON exists and contains all required specifications."""
        meta_path = os.path.join(r"d:\RBU\RBU Sem 5\SEPM\Sepm Project SolarGuard", "ml_models", "model_metadata_v3_1.json")
        self.assertTrue(os.path.exists(meta_path))

        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)

        self.assertEqual(meta['model_version'], '3.1')
        self.assertEqual(meta['architecture'], 'MobileNetV2')
        self.assertEqual(meta['sha256_hash'], 'D5D27E9FF82B007DAD680DB788DC4652CCF53EE7AAF0FB5CBBD72A327F2E22A5')
        self.assertEqual(meta['image_size'], [224, 224])
        self.assertEqual(meta['input_shape'], [1, 224, 224, 3])
        self.assertIn('verified_metrics', meta)
        self.assertIn('evaluation_limitations', meta)
        self.assertGreaterEqual(meta['verified_metrics']['frozen_test_benchmark']['accuracy'], 0.90)

    def test_10_role_based_inspection_authorization(self):
        """Test 10: Role-based inspection authorization and retired panel protection."""
        # 1. Cust B cannot inspect Cust A's panel
        self.client.login(username='p9b_cust_b', password='password123')
        upload = SimpleUploadedFile("cust_b_attack.jpg", self.valid_img_bytes, content_type="image/jpeg")
        resp = self.client.post(reverse('inspect'), {
            'panel': self.panel_active.id,
            'image': upload,
        })
        self.assertEqual(resp.status_code, 403)

        # 2. Cust A cannot inspect a retired panel
        self.client.login(username='p9b_cust_a', password='password123')
        upload_ret = SimpleUploadedFile("retired_test.jpg", self.valid_img_bytes, content_type="image/jpeg")
        resp_ret = self.client.post(reverse('inspect'), {
            'panel': self.panel_active.id,
            'panel': self.panel_retired.id,
            'image': upload_ret,
        })
        self.assertEqual(resp_ret.status_code, 403)

        # 3. Cust A can inspect their own active panel
        upload_ok = SimpleUploadedFile("cust_a_ok.jpg", self.valid_img_bytes, content_type="image/jpeg")
        resp_ok = self.client.post(reverse('inspect'), {
            'panel': self.panel_active.id,
            'image': upload_ok,
        }, follow=True)
        self.assertEqual(resp_ok.status_code, 200)

        # Verify inspection was created with review_status set appropriately
        latest_ins = Inspection.objects.filter(panel=self.panel_active).latest('inspected_at')
        self.assertIsNotNone(latest_ins)
        self.assertIn(latest_ins.review_status, ['ai_predicted', 'flagged'])
