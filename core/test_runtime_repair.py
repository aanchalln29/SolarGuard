"""
SolarGuard — Regression Tests for Runtime Repair & Failed-Inference Guardrails
SEPM Project SolarGuard (Post-Phase-10 Runtime Repair)

Tests:
1. Missing TensorFlow handled gracefully.
2. Missing or corrupted model file handled gracefully.
3. Successful model loading and prediction in compatible virtual environment.
4. Failed inference never becomes Normal in derived conditions.
5. Failed inference never produces misleading Routine triage.
6. 'Real CNN Inference Active' banner only appears when appropriate.
7. Historical records remain unchanged.
8. Model version stays v3.0 (Candidate 2 remains staged, not deployed).
"""

import os
import datetime
from unittest.mock import patch
from PIL import Image
import numpy as np

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.conf import settings

from core.models import UserProfile, Installation, Panel, Inspection, MaintenanceIssue
from ml_engine.inference import (
    run_cnn_inference,
    load_model_service,
    switch_model_version,
    _MODEL_LOCK,
)
from ml_engine.priority_engine import calculate_maintenance_priority


class RuntimeRepairRegressionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create test users
        cls.customer = User.objects.create_user(username='repair_cust', password='password123')
        UserProfile.objects.filter(user=cls.customer).update(role='customer')

        cls.admin = User.objects.create_superuser(username='repair_admin', password='password123')
        UserProfile.objects.filter(user=cls.admin).update(role='admin')

        # Create test installation & panels
        cls.installation = Installation.objects.create(
            name="Repair Array Alpha",
            owner=cls.customer,
            installation_type="commercial",
            site_address="100 Solar Way",
            install_date=datetime.date(2025, 1, 1),
            status="active"
        )
        cls.panel = Panel.objects.create(
            installation=cls.installation,
            permanent_id="REPAIR-P001",
            serial_number="SN-REPAIR-001",
            grid_row=1,
            grid_col=1,
            user=cls.customer,
            site_location=cls.installation.name,
            status="active",
            install_date=datetime.date(2025, 1, 1)
        )

        # Create an existing historical valid inspection
        cls.historical_insp = Inspection.objects.create(
            panel=cls.panel,
            user=cls.customer,
            predicted_class="Normal",
            confidence_score=94.5,
            degradation_probability=5.0,
            risk_category="Low",
            maintenance_priority_score=10,
            maintenance_priority_level="Routine",
            priority_explanation="Visual condition: Normal. | Cleaned recently.",
            is_mock_prediction=False,
            model_identifier="MobileNetV2 CNN v3.0",
            class_probabilities={"Normal": 94.5, "Dusty": 3.0, "Bird-Dropping": 1.5, "Surface-Damage": 1.0},
            review_status="ai_predicted"
        )

    def setUp(self):
        self.client = Client()

    def test_1_missing_tensorflow_handled_gracefully(self):
        """Verify that when TensorFlow cannot be imported or loaded, inference returns model_unavailable gracefully."""
        with patch('ml_engine.inference.load_model_service') as mock_load:
            mock_load.return_value = (None, None, "ModuleNotFoundError: No module named 'tensorflow'")
            res = run_cnn_inference("dummy_path.jpg")
            
            self.assertEqual(res['status'], 'model_unavailable')
            self.assertEqual(res['predicted_class'], 'AI Model Unavailable')
            self.assertEqual(res['confidence_score'], 0.0)
            self.assertTrue(res['is_uncertain'])
            self.assertTrue(res['needs_manual_review'])
            self.assertIn("No module named 'tensorflow'", res['error_message'])

    def test_2_missing_or_corrupted_model_file_handled_gracefully(self):
        """Verify that a missing or corrupted model artifact returns model_unavailable without unhandled crash."""
        with patch('ml_engine.inference.load_model_service') as mock_load:
            mock_load.return_value = (None, None, "Model artifact file missing at 'non_existent_model.keras'.")
            res = run_cnn_inference("dummy_path.jpg")

            self.assertEqual(res['status'], 'model_unavailable')
            self.assertEqual(res['predicted_class'], 'AI Model Unavailable')
            self.assertEqual(res['confidence_score'], 0.0)
            self.assertIn("missing", res['error_message'].lower())

    def test_3_successful_model_loading_and_prediction(self):
        """Verify successful MobileNetV2 v3.0 model loading and prediction in the compatible environment."""
        model, metadata, err = load_model_service(version='v3')
        self.assertIsNone(err, f"Model failed to load: {err}")
        self.assertIsNotNone(model)
        self.assertIsNotNone(metadata)
        self.assertEqual(metadata.get('class_names'), ['Bird-Dropping', 'Dusty', 'Normal', 'Surface-Damage'])

        # Create a synthetic valid RGB test image in memory
        test_img_path = os.path.join(settings.MEDIA_ROOT, 'test_synthetic_panel.jpg')
        os.makedirs(os.path.dirname(test_img_path), exist_ok=True)
        img = Image.new('RGB', (224, 224), color=(60, 80, 100))
        img.save(test_img_path)

        try:
            res = run_cnn_inference(test_img_path, version='v3')
            self.assertEqual(res['status'], 'success')
            self.assertIn(res['predicted_class'], ['Bird-Dropping', 'Dusty', 'Normal', 'Surface-Damage'])
            self.assertGreater(res['confidence_score'], 0.0)
            self.assertEqual(len(res['class_probabilities']), 4)
            self.assertIn('MobileNetV2 CNN v3.0', res['model_identifier'])
        finally:
            if os.path.exists(test_img_path):
                os.remove(test_img_path)

    def test_4_failed_inference_never_becomes_normal(self):
        """Verify that an inspection with failed inference / model unavailable NEVER produces Normal status in derived condition."""
        failed_insp = Inspection.objects.create(
            panel=self.panel,
            user=self.customer,
            predicted_class="AI Model Unavailable",
            confidence_score=0.0,
            model_identifier="Model Unavailable (TensorFlow / Artifact Offline)",
            review_status="flagged",
            maintenance_priority_level="Unable to Assess"
        )

        cond = self.panel.get_derived_condition(latest=failed_insp)
        self.assertEqual(cond['status'], 'review')
        self.assertEqual(cond['category'], 'Inspection Needs Review')
        self.assertIn('AI Model Unavailable', cond['label'])
        self.assertNotIn('Normal', cond['label'])
        self.assertNotIn('Appears Normal', cond['label'])
        self.assertTrue(cond['action_needed'])

    def test_5_failed_inference_never_produces_misleading_routine_triage(self):
        """Verify that calculate_maintenance_priority never produces Routine or assumes Normal when visual finding is unavailable."""
        res_unavail = calculate_maintenance_priority(self.panel, visual_finding="AI Model Unavailable")
        self.assertEqual(res_unavail['priority_level'], "Unable to Assess")
        self.assertNotEqual(res_unavail['priority_level'], "Routine")
        self.assertNotIn("Normal", res_unavail['summary_advice'])
        self.assertIn("AI Model Unavailable", res_unavail['explanation_text'])

        res_offline = calculate_maintenance_priority(self.panel, visual_finding="Model Unavailable (Missing / Corrupted Artifacts)")
        self.assertEqual(res_offline['priority_level'], "Unable to Assess")
        self.assertNotEqual(res_offline['priority_level'], "Routine")

        res_error = calculate_maintenance_priority(self.panel, visual_finding="Error: inference failed")
        self.assertEqual(res_error['priority_level'], "Unable to Assess")
        self.assertNotEqual(res_error['priority_level'], "Routine")

        # Independent rule check: if washing is 90+ days overdue, it specifies Cleaning Recommended via independent rule
        class OverduePanel:
            days_since_last_cleaning = 120
            fault_count_last_6_months = 0

        res_overdue = calculate_maintenance_priority(OverduePanel(), visual_finding="AI Model Unavailable")
        self.assertEqual(res_overdue['priority_level'], "Cleaning Recommended")
        self.assertIn("Independent Rule", res_overdue['explanation_text'])
        self.assertNotIn("Normal", res_overdue['explanation_text'])

    def test_6_real_cnn_inference_active_banner_only_appears_when_appropriate(self):
        """Verify the 'Real CNN Inference Active' banner only displays on real successful models and never on model unavailable."""
        self.client.login(username='repair_cust', password='password123')

        # 6a. Model unavailable inspection report
        failed_insp = Inspection.objects.create(
            panel=self.panel,
            user=self.customer,
            predicted_class="AI Model Unavailable",
            confidence_score=0.0,
            model_identifier="Model Unavailable (TensorFlow / Artifact Offline)",
            review_status="flagged",
            maintenance_priority_level="Unable to Assess"
        )

        resp_failed = self.client.get(reverse('result_detail', kwargs={'pk': failed_insp.pk}))
        self.assertEqual(resp_failed.status_code, 200)
        self.assertNotContains(resp_failed, "Real CNN Inference Active")
        self.assertContains(resp_failed, "AI Model Unavailable — Inspection Needs Review")
        self.assertContains(resp_failed, "N/A (Inference Offline)")
        self.assertContains(resp_failed, "Unable to Determine Visual Condition")
        self.assertNotContains(resp_failed, "badge-priority-routine")

        # 6b. Successful real model inspection report
        resp_success = self.client.get(reverse('result_detail', kwargs={'pk': self.historical_insp.pk}))
        self.assertEqual(resp_success.status_code, 200)
        self.assertContains(resp_success, "Real CNN Inference Active: MobileNetV2 CNN v3.0")
        self.assertContains(resp_success, "94.5%")
        self.assertNotContains(resp_success, "AI Model Unavailable")

    def test_7_historical_records_remain_unchanged(self):
        """Verify that historical inspection records are preserved and not mutated by repair logic."""
        self.historical_insp.refresh_from_db()
        self.assertEqual(self.historical_insp.predicted_class, "Normal")
        self.assertEqual(self.historical_insp.confidence_score, 94.5)
        self.assertEqual(self.historical_insp.model_identifier, "MobileNetV2 CNN v3.0")
        self.assertEqual(self.historical_insp.maintenance_priority_level, "Routine")

    def test_8_model_version_stays_v3(self):
        """Verify active production model remains MobileNetV2 v3.0 and Candidate 2 remains staged as v3.1."""
        active_ver = getattr(settings, 'SOLARGUARD_MODEL_VERSION', 'v3')
        self.assertEqual(active_ver, 'v3')

        catalog = getattr(settings, 'MODEL_CATALOG', {})
        self.assertIn('v3', catalog)
        self.assertEqual(catalog['v3']['model_file'], 'solarguard_model_v3.keras')
        self.assertEqual(catalog['v3']['version'], '3.0')

        self.assertIn('v3.1', catalog)
        self.assertEqual(catalog['v3.1']['model_file'], 'solarguard_model_v3_1.keras')
        self.assertEqual(catalog['v3.1']['version'], '3.1')
        self.assertIn('Class-Weighted', catalog['v3.1']['description'])
