import os
import json
import datetime
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image, ImageDraw
import io
from django.utils import timezone

from core.models import UserProfile, Installation, LayoutRevision, Panel, Inspection, MaintenanceIssue, MaintenanceLog
from ml_engine.predictor import predict_fault, predict_degradation


class SolarGuardEndToEndTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.other_user = User.objects.create_user(username='otheruser', password='password123')
        
        today = datetime.date.today()
        self.panel = Panel.objects.create(
            user=self.user,
            serial_number='TEST-PANEL-01',
            site_location='Test Array Zone 1',
            install_date=today - datetime.timedelta(days=365 * 3),
            last_cleaned_date=today - datetime.timedelta(days=45),
            avg_temp_exposure=36.0,
            dust_index_avg=0.5
        )

        # Create a textured test image in-memory (with lines and shapes so quality filter passes)
        img = Image.new('RGB', (128, 128), color=(30, 60, 100))
        draw = ImageDraw.Draw(img)
        draw.line([(10, 10), (120, 120)], fill=(200, 200, 200), width=3)
        draw.rectangle([(30, 30), (80, 80)], outline=(180, 180, 50), width=2)
        
        img_io = io.BytesIO()
        img.save(img_io, format='JPEG')
        img_io.seek(0)
        self.test_image = SimpleUploadedFile("test_panel.jpg", img_io.getvalue(), content_type="image/jpeg")

    def test_ml_predictor_inference(self):
        """Test that dual model predictor executes without error and returns valid structure."""
        img_path = "test_img.jpg"
        img = Image.new('RGB', (128, 128), color=(50, 80, 120))
        draw = ImageDraw.Draw(img)
        draw.line([(0, 0), (128, 128)], fill=(255, 255, 255), width=2)
        img.save(img_path)

        try:
            fault_res = predict_fault(img_path)
            self.assertIn('predicted_class', fault_res)
            self.assertIn('confidence_score', fault_res)
            self.assertIn(fault_res['predicted_class'], [
                'Normal', 'Dusty', 'Bird-Dropping', 'Surface-Damage', 'Cracked',
                'Electrical-Damage', 'Snow-Covered', 'Unable to assess / Retake photo'
            ])
            self.assertFalse(fault_res.get('is_mock', True)) # Real CNN is active by default
            if fault_res.get('status') == 'success':
                self.assertIn('class_probabilities', fault_res)
                self.assertIn('Bird-Dropping', fault_res['class_probabilities'])
                self.assertIn('Dusty', fault_res['class_probabilities'])
                self.assertIn('Normal', fault_res['class_probabilities'])
                self.assertIn('Surface-Damage', fault_res['class_probabilities'])

            deg_res = predict_degradation(self.panel, visual_finding=fault_res['predicted_class'])
            self.assertIn('risk_category', deg_res)
            self.assertIn('priority_score', deg_res)
            self.assertIn('priority_level', deg_res)
            self.assertIn('explanation_text', deg_res)
            self.assertIn(deg_res['priority_level'], ['Routine', 'Cleaning Recommended', 'Manual Inspection Recommended', 'Unable to Assess'])
        finally:
            if os.path.exists(img_path):
                os.remove(img_path)

    def test_login_and_dashboard_view(self):
        """Test login view and dashboard render."""
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302) # Redirects to login when unauthenticated

        # Log in
        logged_in = self.client.login(username='testuser', password='password123')
        self.assertTrue(logged_in)

        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "My Solar Systems")
        self.assertContains(response, "Add your first solar installation")

    def test_panel_creation_flow(self):
        """Test direct user-facing Add Panel form with and without optional dates."""
        self.client.login(username='testuser', password='password123')

        # 1. Panel with optional dates
        post_data = {
            'serial_number': 'NEW-PANEL-99',
            'site_location': 'Rooftop West Array',
            'install_date': '2023-05-10',
            'last_cleaned_date': '2024-01-15',
        }

        response = self.client.post(reverse('panel_add'), post_data, follow=True)
        self.assertEqual(response.status_code, 200)

        # Verify panel is created in DB and associated with user
        new_panel = Panel.objects.filter(serial_number='NEW-PANEL-99').first()
        self.assertIsNotNone(new_panel)
        self.assertEqual(new_panel.user, self.user)
        self.assertEqual(new_panel.site_location, 'Rooftop West Array')

        # 2. Panel with unknown / blank dates (no fabricated defaults)
        post_data_blank = {
            'serial_number': 'NEW-PANEL-BLANK-DATES',
            'site_location': 'East Wing Carport',
            'install_date': '',
            'last_cleaned_date': '',
        }
        response = self.client.post(reverse('panel_add'), post_data_blank, follow=True)
        self.assertEqual(response.status_code, 200)

        blank_panel = Panel.objects.filter(serial_number='NEW-PANEL-BLANK-DATES').first()
        self.assertIsNotNone(blank_panel)
        self.assertIsNone(blank_panel.install_date)
        self.assertIsNone(blank_panel.last_cleaned_date)
        self.assertIsNone(blank_panel.panel_age_months)
        self.assertIsNone(blank_panel.days_since_last_cleaning)

    def test_inspection_upload_and_result_flow(self):
        """Test uploading an inspection image and verifying real CNN result generation."""
        self.client.login(username='testuser', password='password123')

        post_data = {
            'panel': self.panel.id,
            'image': self.test_image,
            'notes': 'Unit test inspection run'
        }

        response = self.client.post(reverse('inspect'), post_data, follow=True)
        self.assertEqual(response.status_code, 200)

        # Verify inspection record created
        self.assertEqual(Inspection.objects.count(), 1)
        ins = Inspection.objects.first()
        self.assertEqual(ins.panel, self.panel)
        self.assertIn(ins.predicted_class, ['Normal', 'Dusty', 'Bird-Dropping', 'Surface-Damage', 'Cracked', 'Unable to assess / Retake photo'])
        self.assertIn(ins.maintenance_priority_level, ['Routine', 'Cleaning Recommended', 'Manual Inspection Recommended', 'Unable to Assess'])
        self.assertFalse(ins.is_mock_prediction) # Real MobileNetV2 CNN is active!
        self.assertIn('MobileNetV2', ins.model_identifier)

        # Verify result view renders the details
        res_url = reverse('result_detail', kwargs={'pk': ins.id})
        response = self.client.get(res_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f"Inspection Report: {self.panel.serial_number}")
        self.assertContains(response, ins.predicted_class)
        self.assertContains(response, "Real CNN Inference Active")
        self.assertContains(response, "Operational Maintenance Triage")
        self.assertContains(response, "Decision Rule Rationale")

    def test_unreadable_image_handling(self):
        """Test that invalid/corrupt image is caught by form validation and ML service returns Unable to assess."""
        # 1. Direct ML service test with corrupt bytes
        unreadable_res = predict_fault(io.BytesIO(b"not an image payload"))
        self.assertEqual(unreadable_res['status'], 'unreadable')
        self.assertEqual(unreadable_res['predicted_class'], 'Unable to assess / Retake photo')
        self.assertEqual(unreadable_res['confidence_score'], 0.0)

        # 2. Form/view level upload validation catches corrupt file with user-friendly error
        corrupt_file = SimpleUploadedFile("corrupt.jpg", b"corrupted bytes", content_type="image/jpeg")
        self.client.login(username='testuser', password='password123')
        response = self.client.post(reverse('inspect'), {'panel': self.panel.id, 'image': corrupt_file})
        form = response.context['form']
        self.assertTrue(form.errors)
        self.assertIn('image', form.errors)
        self.assertTrue(any('corrupt' in err.lower() or 'not an image' in err.lower() for err in form.errors['image']))

    def test_maintenance_issue_workflow(self):
        """Test creating an issue, updating status, and recording action logs."""
        self.client.login(username='testuser', password='password123')

        # 1. Create issue
        issue_data = {
            'panel': self.panel.id,
            'title': 'Dust and Soiling Clean Needed',
            'description': 'Panel covered with uniform dust layer.',
            'status': 'Open',
            'priority': 'Medium'
        }
        response = self.client.post(reverse('issue_create'), issue_data, follow=True)
        self.assertEqual(response.status_code, 200)

        issue = MaintenanceIssue.objects.filter(title='Dust and Soiling Clean Needed').first()
        self.assertIsNotNone(issue)
        self.assertEqual(issue.status, 'Open')

        # 2. Verify customer cannot arbitrarily resolve ticket without technician authorization
        issue_url = reverse('issue_detail', kwargs={'pk': issue.id})
        cust_attempt = self.client.post(issue_url, {'action': 'update_status', 'status': 'Resolved'})
        self.assertEqual(cust_attempt.status_code, 403)

        # 3. Assign technician and log in as technician to perform work
        tech_user = User.objects.create_user(username='field_tech', password='password123')
        tech_user.profile.role = 'technician'
        tech_user.profile.save()
        issue.assigned_technician = tech_user
        issue.save()

        self.client.login(username='field_tech', password='password123')

        # 4. Technician updates status to In Progress
        response = self.client.post(issue_url, {'action': 'update_status', 'status': 'In Progress'}, follow=True)
        self.assertEqual(response.status_code, 200)
        issue.refresh_from_db()
        self.assertEqual(issue.status, 'In Progress')

        # 5. Technician adds Maintenance Action Log (Cleaning)
        today = datetime.date.today().isoformat()
        log_data = {
            'action': 'add_log',
            'action_type': 'cleaning',
            'performed_at': today,
            'notes': 'Washed with demineralized water and micro-fiber cloth.'
        }
        response = self.client.post(issue_url, log_data, follow=True)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(issue.action_logs.filter(action_type='cleaning').count(), 1)
        self.panel.refresh_from_db()
        self.assertEqual(self.panel.last_cleaned_date.isoformat(), today)

        # 6. Technician marks ticket Resolved
        response = self.client.post(issue_url, {'action': 'update_status', 'status': 'Resolved'}, follow=True)
        issue.refresh_from_db()
        self.assertEqual(issue.status, 'Resolved')
        self.assertIsNotNone(issue.resolved_at)

    def test_user_ownership_isolation(self):
        """Test that users cannot access records owned by other users."""
        # Panel owned by other user
        other_panel = Panel.objects.create(
            user=self.other_user,
            serial_number='OTHER-PANEL-01',
            site_location='Private Site B',
            install_date=datetime.date.today(),
            last_cleaned_date=datetime.date.today()
        )
        other_inspection = Inspection.objects.create(
            user=self.other_user,
            panel=other_panel,
            image=self.test_image,
            predicted_class='Normal',
            confidence_score=90.0,
            maintenance_priority_score=10,
            maintenance_priority_level='Low'
        )

        # Log in as testuser (not other_user, not superuser)
        self.client.login(username='testuser', password='password123')

        # Attempt to access other user's inspection result
        res_url = reverse('result_detail', kwargs={'pk': other_inspection.id})
        response = self.client.get(res_url)
        self.assertEqual(response.status_code, 403) # Blocked with HTTP 403 Forbidden!


class SolarGuardPhase2SchemaTests(TestCase):
    """
    Targeted tests for Phase 2 Architecture:
    - Installation ownership
    - Stable panel permanent IDs independent of grid position
    - Irregular 4-3-4 layout data representation
    - Draft versus active verified layout isolation
    - Historical record preservation upon panel status change
    - Database deletion protection (PROTECT)
    - UserProfile role creation and non-elevation
    """
    def setUp(self):
        self.customer = User.objects.create_user(username='solar_customer', password='password123')
        self.technician = User.objects.create_user(username='solar_tech', password='password123')
        self.technician.profile.role = 'technician'
        self.technician.profile.save()

        self.installation = Installation.objects.create(
            owner=self.customer,
            name="Meadow Ridge Solar Array",
            site_address="124 Solar Way, Sector 4",
            installation_type="rooftop",
            assigned_technician=self.technician,
            status="active"
        )

    def test_user_profile_role_creation_and_non_elevation(self):
        """Verify new users default to customer and superusers default to admin."""
        self.assertEqual(self.customer.profile.role, 'customer')
        self.assertEqual(self.technician.profile.role, 'technician')

        superuser = User.objects.create_superuser(username='super_admin', password='password123')
        self.assertEqual(superuser.profile.role, 'admin')

    def test_installation_ownership_and_protective_deletion(self):
        """Verify Installation relationships and models.PROTECT prevents accidental cascading deletion."""
        from django.db.models import ProtectedError

        panel = Panel.objects.create(
            installation=self.installation,
            permanent_id="SG-01-P001",
            serial_number="MOD-ALPHA-001",
            grid_row=1,
            grid_col=1,
            status="active"
        )

        # Deleting installation should raise ProtectedError because panel exists
        with self.assertRaises(ProtectedError):
            self.installation.delete()

        # Deleting owner should also raise ProtectedError
        with self.assertRaises(ProtectedError):
            self.customer.delete()

        # Owner property on panel works correctly
        self.assertEqual(panel.owner, self.customer)

    def test_stable_permanent_panel_id_independent_of_grid_movement(self):
        """Moving a panel to a new grid cell must never alter its permanent ID or break inspection links."""
        panel = Panel.objects.create(
            installation=self.installation,
            permanent_id="SG-01-P005",
            serial_number="MOD-BETA-005",
            grid_row=1,
            grid_col=2,
            status="active"
        )

        # Create inspection linked to panel
        img = Image.new('RGB', (64, 64), color=(40, 70, 110))
        img_io = io.BytesIO()
        img.save(img_io, format='JPEG')
        img_io.seek(0)
        uploaded = SimpleUploadedFile("panel_img.jpg", img_io.getvalue(), content_type="image/jpeg")

        inspection = Inspection.objects.create(
            panel=panel,
            user=self.customer,
            image=uploaded,
            predicted_class="Dusty",
            confidence_score=88.5,
            maintenance_priority_level="Cleaning Recommended"
        )

        # Move panel from (1, 2) to (3, 4)
        panel.grid_row = 3
        panel.grid_col = 4
        panel.save(update_fields=['grid_row', 'grid_col'])
        panel.refresh_from_db()

        # Permanent ID is unchanged
        self.assertEqual(panel.permanent_id, "SG-01-P005")
        self.assertEqual(panel.serial_number, "MOD-BETA-005")
        self.assertEqual(panel.grid_row, 3)
        self.assertEqual(panel.grid_col, 4)

        # Historical inspection remains intact and linked to same panel
        self.assertEqual(panel.inspections.count(), 1)
        self.assertEqual(inspection.panel_id, panel.id)

    def test_irregular_layout_4_3_4_configuration(self):
        """Verify representation of irregular solar arrays (e.g. 4-3-4 panels across 3 rows)."""
        # Row 1: 4 panels, Row 2: 3 panels, Row 3: 4 panels -> Total 11 panels
        layout_data = {
            "rows": 3,
            "cols": 4,
            "active_cells": [
                # Row 1 (4 panels)
                {"row": 1, "col": 1, "panel_id": "SG-01-P001", "status": "active"},
                {"row": 1, "col": 2, "panel_id": "SG-01-P002", "status": "active"},
                {"row": 1, "col": 3, "panel_id": "SG-01-P003", "status": "active"},
                {"row": 1, "col": 4, "panel_id": "SG-01-P004", "status": "active"},
                # Row 2 (3 panels - col 4 is empty slot, not a physical panel)
                {"row": 2, "col": 1, "panel_id": "SG-01-P005", "status": "active"},
                {"row": 2, "col": 2, "panel_id": "SG-01-P006", "status": "active"},
                {"row": 2, "col": 3, "panel_id": "SG-01-P007", "status": "active"},
                # Row 3 (4 panels)
                {"row": 3, "col": 1, "panel_id": "SG-01-P008", "status": "active"},
                {"row": 3, "col": 2, "panel_id": "SG-01-P009", "status": "active"},
                {"row": 3, "col": 3, "panel_id": "SG-01-P010", "status": "active"},
                {"row": 3, "col": 4, "panel_id": "SG-01-P011", "status": "active"},
            ]
        }

        revision = LayoutRevision.objects.create(
            installation=self.installation,
            version_number=1,
            status="verified",
            grid_rows=3,
            grid_cols=4,
            layout_data=layout_data,
            submitted_by=self.customer,
            reviewed_by=self.technician,
            review_notes="Irregular 4-3-4 rooftop configuration approved after site inspection."
        )

        self.assertEqual(revision.status, "verified")
        self.assertEqual(len(revision.layout_data['active_cells']), 11)
        row_2_panels = [c for c in revision.layout_data['active_cells'] if c['row'] == 2]
        self.assertEqual(len(row_2_panels), 3)

    def test_draft_versus_active_verified_layout_isolation(self):
        """Editing an existing verified layout creates a new draft revision without mutating the active verified layout."""
        verified_v1 = LayoutRevision.objects.create(
            installation=self.installation,
            version_number=1,
            status="verified",
            grid_rows=2,
            grid_cols=2,
            layout_data={"rows": 2, "cols": 2, "active_cells": [{"row": 1, "col": 1, "panel_id": "SG-01-P001"}]}
        )

        # Customer begins editing -> creates Draft v2
        draft_v2 = LayoutRevision.objects.create(
            installation=self.installation,
            version_number=2,
            status="draft",
            grid_rows=3,
            grid_cols=3,
            layout_data={"rows": 3, "cols": 3, "active_cells": [{"row": 1, "col": 1, "panel_id": "SG-01-P001"}, {"row": 2, "col": 1, "panel_id": "SG-01-P002"}]},
            submitted_by=self.customer
        )

        # The active verified layout for the installation remains v1
        self.assertEqual(self.installation.verified_layout.id, verified_v1.id)
        self.assertEqual(self.installation.verified_layout.version_number, 1)

        # The pending/draft layout is recognized as v2
        self.assertEqual(self.installation.pending_or_draft_layout.id, draft_v2.id)
        self.assertEqual(self.installation.pending_or_draft_layout.version_number, 2)

    def test_historical_records_preserved_on_panel_status_change(self):
        """When a panel is decommissioned or retired, its identity and inspection history must be preserved."""
        panel = Panel.objects.create(
            installation=self.installation,
            permanent_id="SG-01-P099",
            serial_number="MOD-RETIRE-099",
            grid_row=1,
            grid_col=1,
            status="active"
        )

        img = Image.new('RGB', (64, 64), color=(50, 50, 50))
        img_io = io.BytesIO()
        img.save(img_io, format='JPEG')
        img_io.seek(0)
        uploaded = SimpleUploadedFile("retire_test.jpg", img_io.getvalue(), content_type="image/jpeg")

        Inspection.objects.create(
            panel=panel,
            user=self.customer,
            image=uploaded,
            predicted_class="Surface-Damage",
            confidence_score=92.0,
            maintenance_priority_level="Manual Inspection Recommended"
        )

        # Physical panel is damaged and retired/replaced
        panel.status = "retired"
        panel.grid_row = None
        panel.grid_col = None
        panel.save()

        panel.refresh_from_db()
        self.assertEqual(panel.status, "retired")
        self.assertIsNone(panel.grid_row)
        self.assertIsNone(panel.grid_col)
        # All historical inspections remain intact
        self.assertEqual(panel.inspections.count(), 1)
        self.assertEqual(panel.inspections.first().predicted_class, "Surface-Damage")


class SolarGuardPhase3PermissionTests(TestCase):
    """
    Targeted tests for Phase 3 RBAC, Object-Level Authorization, and Security:
    - Customer data isolation (installations, panels, images)
    - URL manipulation defense (cross-customer ID access blocked with 403)
    - Technician assigned installation scoping
    - Technician layout verification restriction (cannot verify unassigned layouts)
    - Customer layout approval prevention (cannot approve own layouts)
    - Non-admin technician assignment prevention (admin only)
    - Secure inspection image authorization
    - Customer work order status tampering prevention
    """
    def setUp(self):
        self.client = Client()

        # Users: Customer A, Customer B, Technician 1, Technician 2, Administrator
        self.cust_a = User.objects.create_user(username='customer_alpha', password='password123')
        self.cust_b = User.objects.create_user(username='customer_beta', password='password123')

        self.tech_1 = User.objects.create_user(username='technician_one', password='password123')
        self.tech_1.profile.role = 'technician'
        self.tech_1.profile.save()

        self.tech_2 = User.objects.create_user(username='technician_two', password='password123')
        self.tech_2.profile.role = 'technician'
        self.tech_2.profile.save()

        self.admin = User.objects.create_superuser(username='super_admin_p3', password='password123')

        # Installation A (Owned by Customer A, Assigned to Tech 1)
        self.inst_a = Installation.objects.create(
            owner=self.cust_a,
            name="Alpha Rooftop System",
            site_address="100 Alpha St",
            installation_type="rooftop",
            assigned_technician=self.tech_1,
            status="active"
        )
        self.panel_a = Panel.objects.create(
            installation=self.inst_a,
            permanent_id="SG-A01-P001",
            serial_number="MOD-A-001",
            grid_row=1,
            grid_col=1,
            user=self.cust_a,
            status="active"
        )
        self.rev_a = LayoutRevision.objects.create(
            installation=self.inst_a,
            version_number=1,
            status="pending_verification",
            grid_rows=1,
            grid_cols=1,
            submitted_by=self.cust_a
        )

        # Installation B (Owned by Customer B, Assigned to Tech 2)
        self.inst_b = Installation.objects.create(
            owner=self.cust_b,
            name="Beta Ground Mount System",
            site_address="200 Beta Blvd",
            installation_type="ground_mount",
            assigned_technician=self.tech_2,
            status="active"
        )
        self.panel_b = Panel.objects.create(
            installation=self.inst_b,
            permanent_id="SG-B01-P001",
            serial_number="MOD-B-001",
            grid_row=1,
            grid_col=1,
            user=self.cust_b,
            status="active"
        )
        self.rev_b = LayoutRevision.objects.create(
            installation=self.inst_b,
            version_number=1,
            status="pending_verification",
            grid_rows=1,
            grid_cols=1,
            submitted_by=self.cust_b
        )

        # Inspection on Panel B (Owned by Customer B)
        img = Image.new('RGB', (64, 64), color=(60, 60, 60))
        img_io = io.BytesIO()
        img.save(img_io, format='JPEG')
        img_io.seek(0)
        uploaded = SimpleUploadedFile("beta_panel.jpg", img_io.getvalue(), content_type="image/jpeg")

        self.insp_b = Inspection.objects.create(
            panel=self.panel_b,
            user=self.cust_b,
            image=uploaded,
            predicted_class="Normal",
            confidence_score=95.0,
            maintenance_priority_level="Routine"
        )

        # Maintenance Issue on Panel A
        self.issue_a = MaintenanceIssue.objects.create(
            installation=self.inst_a,
            panel=self.panel_a,
            user=self.cust_a,
            assigned_technician=self.tech_1,
            title="Clean Surface Soiling",
            status="Open",
            priority="Medium"
        )

    def test_customer_data_isolation_and_url_tampering_blocked(self):
        """Customer A cannot view Customer B's installation or panels via URL tampering."""
        self.client.login(username='customer_alpha', password='password123')

        # 1. Customer A visits installations list -> sees Alpha, does NOT see Beta
        response = self.client.get(reverse('installation_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alpha Rooftop System")
        self.assertNotContains(response, "Beta Ground Mount System")

        # 2. Customer A attempts to access Customer B's installation via ID in URL -> 403 Forbidden!
        tamper_url = reverse('installation_detail', kwargs={'pk': self.inst_b.id})
        response = self.client.get(tamper_url)
        self.assertEqual(response.status_code, 403)

        # 3. Customer A attempts to view Customer B's inspection report via ID in URL -> 403 Forbidden!
        tamper_insp = reverse('result_detail', kwargs={'pk': self.insp_b.id})
        response = self.client.get(tamper_insp)
        self.assertEqual(response.status_code, 403)

        # 4. Customer A attempts to download Customer B's secure inspection image -> 403 Forbidden!
        tamper_img = reverse('secure_inspection_image', kwargs={'pk': self.insp_b.id})
        response = self.client.get(tamper_img)
        self.assertEqual(response.status_code, 403)

    def test_customer_cannot_inspect_other_customer_panel(self):
        """Customer A cannot post an inspection on Customer B's panel."""
        self.client.login(username='customer_alpha', password='password123')

        img = Image.new('RGB', (64, 64), color=(30, 40, 50))
        img_io = io.BytesIO()
        img.save(img_io, format='JPEG')
        img_io.seek(0)
        test_img = SimpleUploadedFile("unauthorized_inspect.jpg", img_io.getvalue(), content_type="image/jpeg")

        # Attempt to inspect Panel B
        post_data = {
            'panel': self.panel_b.id,
            'image': test_img,
            'notes': 'Hacker attempt'
        }
        response = self.client.post(reverse('inspect'), post_data)
        # Form validation rejects it because panel is not in accessible queryset, or view returns 403
        self.assertTrue(response.status_code in [200, 403])
        if response.status_code == 200:
            form = response.context['form']
            self.assertTrue(form.errors)
            self.assertIn('panel', form.errors)

    def test_technician_sees_only_assigned_installations(self):
        """Technician 1 can only access Installation A (assigned), not Installation B (unassigned)."""
        self.client.login(username='technician_one', password='password123')

        # Sees Installation A
        response = self.client.get(reverse('installation_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alpha Rooftop System")
        self.assertNotContains(response, "Beta Ground Mount System")

        # Accessing Installation A succeeds
        resp_a = self.client.get(reverse('installation_detail', kwargs={'pk': self.inst_a.id}))
        self.assertEqual(resp_a.status_code, 200)

        # Attempting to access unassigned Installation B -> 403 Forbidden!
        resp_b = self.client.get(reverse('installation_detail', kwargs={'pk': self.inst_b.id}))
        self.assertEqual(resp_b.status_code, 403)

    def test_technician_cannot_verify_unrelated_layouts(self):
        """Technician 1 cannot verify layout revisions for unassigned Installation B."""
        self.client.login(username='technician_one', password='password123')

        verify_b_url = reverse('layout_verify', kwargs={'pk': self.rev_b.id})
        response = self.client.get(verify_b_url)
        self.assertEqual(response.status_code, 403) # Blocked!

        # Attempt POST verification on unassigned layout B
        post_data = {'status': 'verified', 'review_notes': 'Malicious verification'}
        resp_post = self.client.post(verify_b_url, post_data)
        self.assertEqual(resp_post.status_code, 403) # Blocked!

        # Verification on assigned layout A succeeds
        verify_a_url = reverse('layout_verify', kwargs={'pk': self.rev_a.id})
        resp_a = self.client.post(verify_a_url, {'status': 'verified', 'review_notes': 'On-site verified OK.'}, follow=True)
        self.assertEqual(resp_a.status_code, 200)
        self.rev_a.refresh_from_db()
        self.assertEqual(self.rev_a.status, 'verified')
        self.assertEqual(self.rev_a.reviewed_by, self.tech_1)

    def test_customer_cannot_approve_own_layout(self):
        """Customers cannot self-approve or verify their own layout revisions."""
        self.client.login(username='customer_alpha', password='password123')

        verify_url = reverse('layout_verify', kwargs={'pk': self.rev_a.id})
        response = self.client.get(verify_url)
        self.assertEqual(response.status_code, 403) # Blocked!

        resp_post = self.client.post(verify_url, {'status': 'verified', 'review_notes': 'I approve myself'})
        self.assertEqual(resp_post.status_code, 403) # Blocked!
        self.rev_a.refresh_from_db()
        self.assertNotEqual(self.rev_a.status, 'verified')

    def test_admin_controlled_technician_assignment(self):
        """Only administrators can assign technicians; unauthorized users are blocked with 403."""
        assign_url = reverse('installation_assign_tech', kwargs={'pk': self.inst_a.id})

        # 1. Customer attempts technician assignment -> 403 Forbidden!
        self.client.login(username='customer_alpha', password='password123')
        resp_cust = self.client.post(assign_url, {'technician': self.tech_2.id})
        self.assertEqual(resp_cust.status_code, 403)

        # 2. Technician attempts technician assignment -> 403 Forbidden!
        self.client.login(username='technician_one', password='password123')
        resp_tech = self.client.post(assign_url, {'technician': self.tech_2.id})
        self.assertEqual(resp_tech.status_code, 403)

        # 3. Administrator assigns Tech 2 -> Succeeds!
        self.client.login(username='super_admin_p3', password='password123')
        resp_admin = self.client.post(assign_url, {'technician': self.tech_2.id}, follow=True)
        self.assertEqual(resp_admin.status_code, 200)

        self.inst_a.refresh_from_db()
        self.assertEqual(self.inst_a.assigned_technician, self.tech_2)

    def test_customer_cannot_modify_technician_work_order_status(self):
        """Customers cannot arbitrarily flip technician work order statuses to Resolved."""
        self.client.login(username='customer_alpha', password='password123')

        issue_url = reverse('issue_detail', kwargs={'pk': self.issue_a.id})
        # Customer attempts to resolve ticket
        resp = self.client.post(issue_url, {'action': 'update_status', 'status': 'Resolved'})
        self.assertEqual(resp.status_code, 403) # Blocked!
        self.issue_a.refresh_from_db()
        self.assertEqual(self.issue_a.status, 'Open') # Unchanged!

        # Assigned technician can update status
        self.client.login(username='technician_one', password='password123')
        resp_tech = self.client.post(issue_url, {'action': 'update_status', 'status': 'In Progress'}, follow=True)
        self.assertEqual(resp_tech.status_code, 200)
        self.issue_a.refresh_from_db()
        self.assertEqual(self.issue_a.status, 'In Progress')


class SolarGuardPhase4LayoutBuilderTests(TestCase):
    """
    Automated Unit & Integration Tests for Phase 4: Custom 2D Layout Builder
    Covers:
    - Rectangular layout generation
    - Irregular 4-3-4 layout (11 panels)
    - Add/remove panel slots (empty slot != database record)
    - Moving a panel preserving immutable permanent ID
    - Stable permanent ID generation (SG-01-P006)
    - Draft saving without altering live panel coordinates
    - Draft cancellation preserving active layout
    - Submission to pending_verification
    - Changes Requested resubmission
    - Technician approval applying live coordinates and retiring removed modules
    - Customer approval rejection (403)
    - Unauthorized installation access (403)
    - Historical inspection preservation after layout change
    - Server-side validation (duplicate coordinates, out-of-bounds, foreign installation isolation)
    - Legacy imported layout behavior
    """
    def setUp(self):
        self.client = Client()

        # Users
        self.customer_user = User.objects.create_user(username='customer_bob', password='password123')
        self.customer_user.profile.role = 'customer'
        self.customer_user.profile.save()

        self.other_customer = User.objects.create_user(username='customer_charlie', password='password123')
        self.other_customer.profile.role = 'customer'
        self.other_customer.profile.save()

        self.technician_user = User.objects.create_user(username='tech_dan', password='password123')
        self.technician_user.profile.role = 'technician'
        self.technician_user.profile.is_certified_technician = True
        self.technician_user.profile.save()

        self.unassigned_tech = User.objects.create_user(username='tech_eve', password='password123')
        self.unassigned_tech.profile.role = 'technician'
        self.unassigned_tech.profile.is_certified_technician = True
        self.unassigned_tech.profile.save()

        self.admin_user = User.objects.create_superuser(username='admin_frank', password='password123')
        self.admin_user.profile.role = 'admin'
        self.admin_user.profile.save()

        # Solar Installation
        self.installation = Installation.objects.create(
            name="Bob's Solar Array",
            owner=self.customer_user,
            site_address="456 Solar Way, Denver, CO",
            installation_type="rooftop",
            assigned_technician=self.technician_user,
            status="active"
        )

        # Existing physical panels (10 panels)
        self.panels = []
        for i in range(1, 11):
            pid = f"SG-{self.installation.id:02d}-P{i:03d}"
            p = Panel.objects.create(
                installation=self.installation,
                user=self.customer_user,
                permanent_id=pid,
                serial_number=f"OEM-BOB-{i:03d}",
                site_location=self.installation.site_address,
                grid_row=(i - 1) // 4 + 1,
                grid_col=(i - 1) % 4 + 1,
                status='active'
            )
            self.panels.append(p)

        # Initial Verified Layout Revision v1
        initial_active_cells = [
            {'row': p.grid_row, 'col': p.grid_col, 'panel_id': p.permanent_id, 'serial_number': p.serial_number, 'status': 'active'}
            for p in self.panels
        ]
        self.verified_rev_v1 = LayoutRevision.objects.create(
            installation=self.installation,
            version_number=1,
            status='verified',
            grid_rows=3,
            grid_cols=4,
            layout_data={'rows': 3, 'cols': 4, 'active_cells': initial_active_cells},
            submitted_by=self.customer_user,
            reviewed_by=self.technician_user,
            review_notes="Initial v1 verified by certified technician."
        )

        # Create an inspection on Panel 10 (which will later be removed to test preservation)
        self.inspection_p10 = Inspection.objects.create(
            panel=self.panels[9], # P010
            user=self.customer_user,
            predicted_class="Normal",
            confidence_score=0.95,
            notes="Historical inspection on P010 before layout modification."
        )

    def test_rectangular_layout_generation(self):
        """Generates a rectangular layout and validates dimensions and active cells."""
        self.client.login(username='customer_bob', password='password123')
        gen_url = reverse('layout_generate_rectangular', kwargs={'pk': self.installation.id})

        resp = self.client.post(gen_url, json.dumps({'rows': 3, 'cols': 4}), content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(len(data['layout_data']['active_cells']), 12) # 3x4 = 12 panels
        self.assertEqual(data['layout_data']['rows'], 3)
        self.assertEqual(data['layout_data']['cols'], 4)

    def test_irregular_434_layout_creation_and_empty_slot_no_db_record(self):
        """Homeowner creates an irregular 4-3-4 layout (11 panels) with an empty slot at (Row 2, Col 4)."""
        self.client.login(username='customer_bob', password='password123')
        save_url = reverse('layout_save_draft', kwargs={'pk': self.installation.id})

        # 4 in Row 1, 3 in Row 2, 4 in Row 3 (11 total)
        active_cells_434 = []
        # Row 1: 4 panels
        for c in range(1, 5):
            active_cells_434.append({'row': 1, 'col': c, 'panel_id': f"SG-{self.installation.id:02d}-P{c:03d}", 'serial_number': f"OEM-{c:03d}", 'status': 'active'})
        # Row 2: 3 panels (Col 4 is intentionally omitted / empty slot)
        for c in range(1, 4):
            idx = 4 + c
            active_cells_434.append({'row': 2, 'col': c, 'panel_id': f"SG-{self.installation.id:02d}-P{idx:03d}", 'serial_number': f"OEM-{idx:03d}", 'status': 'active'})
        # Row 3: 4 panels
        for c in range(1, 5):
            idx = 7 + c
            active_cells_434.append({'row': 3, 'col': c, 'panel_id': f"SG-{self.installation.id:02d}-P{idx:03d}", 'serial_number': f"OEM-{idx:03d}", 'status': 'active'})

        self.assertEqual(len(active_cells_434), 11)

        payload = {'rows': 3, 'cols': 4, 'active_cells': active_cells_434}
        resp = self.client.post(save_url, json.dumps(payload), content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['success'])

        # Verify: Empty slot at (Row 2, Col 4) does NOT create any physical panel in database!
        self.assertEqual(self.installation.panels.count(), 10)

        # Active verified layout v1 is untouched
        self.installation.refresh_from_db()
        self.assertEqual(self.installation.active_layout.version_number, 1)
        self.assertEqual(self.installation.active_layout.status, 'verified')

    def test_moving_panel_preserves_immutable_permanent_id(self):
        """Moving panel to another available position preserves its permanent ID."""
        self.client.login(username='customer_bob', password='password123')
        save_url = reverse('layout_save_draft', kwargs={'pk': self.installation.id})

        # Panel P002 originally at (Row 1, Col 2), moved to (Row 2, Col 4)
        active_cells = [
            {'row': 1, 'col': 1, 'panel_id': f"SG-{self.installation.id:02d}-P001", 'serial_number': 'OEM-001', 'status': 'active'},
            {'row': 2, 'col': 4, 'panel_id': f"SG-{self.installation.id:02d}-P002", 'serial_number': 'OEM-002', 'status': 'active'}, # MOVED!
        ]
        resp = self.client.post(save_url, json.dumps({'rows': 3, 'cols': 4, 'active_cells': active_cells}), content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        draft = self.installation.layout_revisions.filter(status='draft').first()
        moved_cell = [c for c in draft.layout_data['active_cells'] if c['panel_id'] == f"SG-{self.installation.id:02d}-P002"][0]
        self.assertEqual(moved_cell['row'], 2)
        self.assertEqual(moved_cell['col'], 4)
        self.assertEqual(moved_cell['panel_id'], f"SG-{self.installation.id:02d}-P002") # Permanent ID UNCHANGED!

    def test_new_panel_id_generation_is_stable_and_sequential(self):
        """New panels receive unique, sequential, collision-safe IDs."""
        from core.layout_service import generate_next_panel_id
        next_id = generate_next_panel_id(self.installation)
        self.assertEqual(next_id, f"SG-{self.installation.id:02d}-P011")

    def test_draft_saving_does_not_mutate_live_coordinates(self):
        """Saving a draft does not alter live coordinates of existing physical panels."""
        self.client.login(username='customer_bob', password='password123')
        save_url = reverse('layout_save_draft', kwargs={'pk': self.installation.id})

        # Put P001 at (3, 3) in draft
        active_cells = [{'row': 3, 'col': 3, 'panel_id': f"SG-{self.installation.id:02d}-P001", 'serial_number': 'OEM-001', 'status': 'active'}]
        resp = self.client.post(save_url, json.dumps({'rows': 3, 'cols': 4, 'active_cells': active_cells}), content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        # Check physical panel in DB: still at (1, 1)!
        p1 = Panel.objects.get(permanent_id=f"SG-{self.installation.id:02d}-P001")
        self.assertEqual(p1.grid_row, 1)
        self.assertEqual(p1.grid_col, 1)

    def test_draft_cancellation_preserves_active_layout(self):
        """Cancelling draft editing discards draft and preserves active verified layout."""
        self.client.login(username='customer_bob', password='password123')
        save_url = reverse('layout_save_draft', kwargs={'pk': self.installation.id})
        self.client.post(save_url, json.dumps({'rows': 3, 'cols': 4, 'active_cells': [{'row': 1, 'col': 1, 'panel_id': f"SG-{self.installation.id:02d}-P001", 'serial_number': 'OEM-001', 'status': 'active'}]}), content_type='application/json')
        
        self.assertTrue(self.installation.layout_revisions.filter(version_number=2).exists())

        cancel_url = reverse('layout_cancel', kwargs={'pk': self.installation.id})
        resp = self.client.post(cancel_url, follow=True)
        self.assertEqual(resp.status_code, 200)

        # Draft v2 discarded
        self.assertFalse(self.installation.layout_revisions.filter(version_number=2).exists())
        # Active verified layout v1 intact
        self.assertEqual(self.installation.active_layout.version_number, 1)
        self.assertEqual(self.installation.active_layout.status, 'verified')

    def test_pending_verification_submission_flow(self):
        """Submitting draft moves it to pending_verification."""
        self.client.login(username='customer_bob', password='password123')
        submit_url = reverse('layout_submit', kwargs={'pk': self.installation.id})

        active_cells = [{'row': 1, 'col': 1, 'panel_id': f"SG-{self.installation.id:02d}-P001", 'serial_number': 'OEM-001', 'status': 'active'}]
        resp = self.client.post(submit_url, json.dumps({'rows': 3, 'cols': 4, 'active_cells': active_cells}), content_type='application/json')
        self.assertEqual(resp.status_code, 200)

        draft = self.installation.layout_revisions.filter(status='pending_verification').first()
        self.assertIsNotNone(draft)
        self.assertEqual(draft.status, 'pending_verification')

    def test_changes_requested_and_resubmission(self):
        """Technician requests changes, customer edits and resubmits."""
        # 1. Customer submits draft
        self.client.login(username='customer_bob', password='password123')
        submit_url = reverse('layout_submit', kwargs={'pk': self.installation.id})
        active_cells = [{'row': 1, 'col': 1, 'panel_id': f"SG-{self.installation.id:02d}-P001", 'serial_number': 'OEM-001', 'status': 'active'}]
        self.client.post(submit_url, json.dumps({'rows': 3, 'cols': 4, 'active_cells': active_cells}), content_type='application/json')

        draft = self.installation.layout_revisions.filter(status='pending_verification').first()

        # 2. Technician requests changes
        self.client.login(username='tech_dan', password='password123')
        verify_url = reverse('layout_verify', kwargs={'pk': draft.id})
        resp = self.client.post(verify_url, {'status': 'changes_requested', 'review_notes': 'Please align modules closer to the south edge.'}, follow=True)
        self.assertEqual(resp.status_code, 200)

        draft.refresh_from_db()
        self.assertEqual(draft.status, 'changes_requested')

        # 3. Customer edits and resubmits
        self.client.login(username='customer_bob', password='password123')
        resp_resubmit = self.client.post(submit_url, json.dumps({'rows': 3, 'cols': 4, 'active_cells': active_cells}), content_type='application/json')
        self.assertEqual(resp_resubmit.status_code, 200)

        draft.refresh_from_db()
        self.assertEqual(draft.status, 'pending_verification')

    def test_technician_approval_atomic_application_and_safe_module_removal(self):
        """
        Technician approves layout:
        - Atomic update: live panel coordinates updated
        - New physical panel created
        - Removed panel P010 retired (status='retired'), NEVER deleted
        - Historical inspection on P010 preserved
        - New revision becomes verified; old revision superseded
        """
        from core.layout_service import get_or_create_draft_revision, save_draft_layout, submit_draft_for_verification
        draft, _ = get_or_create_draft_revision(self.installation, self.customer_user)

        active_cells = []
        for i in range(1, 10): # P001 to P009
            active_cells.append({
                'row': (i - 1) // 3 + 1,
                'col': (i - 1) % 3 + 1,
                'panel_id': f"SG-{self.installation.id:02d}-P{i:03d}",
                'serial_number': f"OEM-BOB-{i:03d}",
                'status': 'active'
            })
        # P010 is OMITTED (removed from proposed layout)
        # Add brand new panel P011
        active_cells.append({
            'row': 3,
            'col': 4,
            'panel_id': f"SG-{self.installation.id:02d}-P011",
            'serial_number': f"OEM-BOB-011",
            'status': 'active'
        })

        save_draft_layout(draft, 3, 4, active_cells, self.customer_user)
        submit_draft_for_verification(draft, self.customer_user)
        draft.refresh_from_db()
        self.assertEqual(draft.status, 'pending_verification')

        # Assigned technician approves layout
        self.client.login(username='tech_dan', password='password123')
        verify_url = reverse('layout_verify', kwargs={'pk': draft.id})
        resp = self.client.post(verify_url, {'status': 'verified', 'review_notes': 'On-site geometry verified.'}, follow=True)
        self.assertEqual(resp.status_code, 200)

        # 1. New revision is verified
        draft.refresh_from_db()
        self.assertEqual(draft.status, 'verified')
        self.installation.refresh_from_db()
        self.assertEqual(self.installation.active_layout.id, draft.id)

        # 2. Previous revision is superseded
        self.verified_rev_v1.refresh_from_db()
        self.assertEqual(self.verified_rev_v1.status, 'superseded')

        # 3. New panel P011 was created in DB
        new_panel = Panel.objects.filter(permanent_id=f"SG-{self.installation.id:02d}-P011").first()
        self.assertIsNotNone(new_panel)
        self.assertEqual(new_panel.grid_row, 3)
        self.assertEqual(new_panel.grid_col, 4)
        self.assertEqual(new_panel.status, 'active')

        # 4. Removed panel P010 is RETIRED, NOT DELETED!
        p10 = Panel.objects.filter(permanent_id=f"SG-{self.installation.id:02d}-P010").first()
        self.assertIsNotNone(p10)
        self.assertEqual(p10.status, 'retired')
        self.assertIsNone(p10.grid_row)
        self.assertIsNone(p10.grid_col)

        # 5. Historical inspection on P010 is completely PRESERVED!
        self.inspection_p10.refresh_from_db()
        self.assertEqual(self.inspection_p10.panel, p10)
        self.assertEqual(self.inspection_p10.predicted_class, 'Normal')

    def test_customer_cannot_verify_own_layout(self):
        """Customers attempting to approve their own layouts receive 403 Forbidden."""
        self.client.login(username='customer_bob', password='password123')
        verify_url = reverse('layout_verify', kwargs={'pk': self.verified_rev_v1.id})

        resp_get = self.client.get(verify_url)
        self.assertEqual(resp_get.status_code, 403)

        resp_post = self.client.post(verify_url, {'status': 'verified', 'review_notes': 'Customer approving own layout'})
        self.assertEqual(resp_post.status_code, 403)

    def test_unauthorized_installation_access_blocked(self):
        """Unauthorized customers and unassigned technicians cannot view or edit layouts."""
        # Other customer blocked
        self.client.login(username='customer_charlie', password='password123')
        builder_url = reverse('layout_builder', kwargs={'pk': self.installation.id})
        resp = self.client.get(builder_url)
        self.assertEqual(resp.status_code, 403)

        save_url = reverse('layout_save_draft', kwargs={'pk': self.installation.id})
        resp_save = self.client.post(save_url, json.dumps({'rows': 3, 'cols': 4, 'active_cells': []}), content_type='application/json')
        self.assertEqual(resp_save.status_code, 403)

        # Unassigned technician blocked
        self.client.login(username='tech_eve', password='password123')
        resp_tech = self.client.get(builder_url)
        self.assertEqual(resp_tech.status_code, 403)

    def test_validation_rejects_duplicate_and_out_of_bounds_coordinates(self):
        """Server-side validation rejects duplicate cell positions and out of bounds coordinates."""
        from core.layout_service import validate_layout_data

        # 1. Duplicate position (two panels at 1, 1)
        dup_cells = [
            {'row': 1, 'col': 1, 'panel_id': 'SG-01-P001'},
            {'row': 1, 'col': 1, 'panel_id': 'SG-01-P002'}
        ]
        valid, err = validate_layout_data(self.installation, 3, 4, dup_cells)
        self.assertFalse(valid)
        self.assertIn("occupied more than once", err)

        # 2. Out of bounds (Row 5 in a 3-row grid)
        oob_cells = [{'row': 5, 'col': 1, 'panel_id': 'SG-01-P001'}]
        valid, err = validate_layout_data(self.installation, 3, 4, oob_cells)
        self.assertFalse(valid)
        self.assertIn("outside the grid bounds", err)

        # 3. Duplicate panel ID
        dup_pid = [
            {'row': 1, 'col': 1, 'panel_id': 'SG-01-P001'},
            {'row': 1, 'col': 2, 'panel_id': 'SG-01-P001'}
        ]
        valid, err = validate_layout_data(self.installation, 3, 4, dup_pid)
        self.assertFalse(valid)
        self.assertIn("appears multiple times", err)

    def test_validation_rejects_foreign_installation_panels(self):
        """Server-side validation rejects panel identities belonging to another installation."""
        from core.layout_service import validate_layout_data

        other_inst = Installation.objects.create(name="Other Array", owner=self.other_customer, site_address="789 Lane")
        Panel.objects.create(
            installation=other_inst,
            permanent_id="SG-99-P001",
            serial_number="FOREIGN-OEM-1",
            site_location=other_inst.site_address,
            user=self.other_customer
        )

        foreign_cells = [{'row': 1, 'col': 1, 'panel_id': 'SG-99-P001'}]
        valid, err = validate_layout_data(self.installation, 3, 4, foreign_cells)
        self.assertFalse(valid)
        self.assertIn("belongs to another installation", err)

    def test_legacy_imported_layout_behavior(self):
        """Legacy imported layout revision remains marked as imported until certified."""
        legacy_inst = Installation.objects.create(name="Legacy Array", owner=self.customer_user, site_address="101 Old Rd")
        legacy_rev = LayoutRevision.objects.create(
            installation=legacy_inst,
            version_number=1,
            status='imported',
            grid_rows=2,
            grid_cols=3,
            layout_data={'rows': 2, 'cols': 3, 'active_cells': []}
        )

        self.assertFalse(legacy_inst.is_layout_verified)
        self.assertEqual(legacy_inst.active_layout.status, 'imported')


class SolarGuardPhase5PassportInspectionTests(TestCase):
    """
    Phase 5 Test Suite:
    - Panel Digital Passport access and security
    - Cross-customer authorization denial
    - Individual panel selection in inspection flow
    - Tampered panel_id rejection
    - Secure image upload and corrupted image rejection
    - AI MobileNetV2 inference and condition derivation
    - Retired panel inspection restrictions
    - Technician verification workflow and audit preservation
    - Customer verification prohibition
    - Maintenance issue creation linked to panel
    - Secure inspection image protection
    """
    def setUp(self):
        self.client = Client()

        # Users and roles
        self.alice = User.objects.create_user(username='alice_owner', password='password123')
        self.alice.profile.role = 'customer'
        self.alice.profile.save()

        self.bob = User.objects.create_user(username='bob_stranger', password='password123')
        self.bob.profile.role = 'customer'
        self.bob.profile.save()

        self.ted = User.objects.create_user(username='ted_assigned_tech', password='password123')
        self.ted.profile.role = 'technician'
        self.ted.profile.is_certified_technician = True
        self.ted.profile.save()

        self.eve = User.objects.create_user(username='eve_unassigned_tech', password='password123')
        self.eve.profile.role = 'technician'
        self.eve.profile.is_certified_technician = True
        self.eve.profile.save()

        self.dan = User.objects.create_superuser(username='dan_admin', password='password123', email='dan@sg.test')
        self.dan.profile.role = 'admin'
        self.dan.profile.save()

        # Installation A owned by Alice, assigned to Ted
        self.inst_a = Installation.objects.create(
            name="Alice Sunnyvale Array",
            owner=self.alice,
            assigned_technician=self.ted,
            site_address="100 Solar Way, Sunnyvale",
            install_date=datetime.date(2023, 1, 15)
        )

        # Active panel A1
        self.panel_a1 = Panel.objects.create(
            installation=self.inst_a,
            user=self.alice,
            permanent_id="SG-01-P001",
            serial_number="REC-ALPHA-01",
            site_location=self.inst_a.site_address,
            grid_row=1,
            grid_col=1,
            status='active',
            install_date=datetime.date(2023, 1, 15),
            last_cleaned_date=datetime.date(2024, 1, 10)
        )

        # Retired panel A2
        self.panel_a2 = Panel.objects.create(
            installation=self.inst_a,
            user=self.alice,
            permanent_id="SG-01-P002",
            serial_number="REC-ALPHA-02",
            site_location=self.inst_a.site_address,
            grid_row=1,
            grid_col=2,
            status='retired',
            install_date=datetime.date(2023, 1, 15)
        )

        # Installation B owned by Bob
        self.inst_b = Installation.objects.create(
            name="Bob Mountain View Array",
            owner=self.bob,
            site_address="200 Ridge Rd, Mountain View",
            install_date=datetime.date(2023, 5, 20)
        )

        self.panel_b1 = Panel.objects.create(
            installation=self.inst_b,
            user=self.bob,
            permanent_id="SG-02-P001",
            serial_number="REC-BETA-01",
            site_location=self.inst_b.site_address,
            grid_row=1,
            grid_col=1,
            status='active'
        )

    def create_valid_test_image(self):
        """Creates an in-memory valid RGB JPEG image."""
        img = Image.new('RGB', (224, 224), color=(40, 70, 110))
        draw = ImageDraw.Draw(img)
        draw.line([(20, 20), (200, 200)], fill=(220, 220, 220), width=4)
        draw.rectangle([(50, 50), (150, 150)], outline=(190, 190, 60), width=3)
        img_io = io.BytesIO()
        img.save(img_io, format='JPEG')
        img_io.seek(0)
        return SimpleUploadedFile("panel_scan.jpg", img_io.getvalue(), content_type="image/jpeg")

    def test_authorized_panel_passport_access(self):
        """Owner customer, assigned technician, and administrator can access Panel Digital Passport."""
        passport_url = reverse('panel_detail', kwargs={'pk': self.panel_a1.id})

        # 1. Alice (owner)
        self.client.login(username='alice_owner', password='password123')
        resp = self.client.get(passport_url)
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, 'core/panel_detail.html')
        self.assertEqual(resp.context['panel'], self.panel_a1)
        self.assertTrue(resp.context['can_inspect'])
        self.assertContains(resp, "SG-01-P001")
        self.assertContains(resp, "Alice Sunnyvale Array")

        # 2. Ted (assigned technician)
        self.client.login(username='ted_assigned_tech', password='password123')
        resp_tech = self.client.get(passport_url)
        self.assertEqual(resp_tech.status_code, 200)

        # 3. Dan (administrator)
        self.client.login(username='dan_admin', password='password123')
        resp_admin = self.client.get(passport_url)
        self.assertEqual(resp_admin.status_code, 200)

    def test_cross_customer_panel_passport_denial(self):
        """Unrelated customer and unassigned technician receive 403 Forbidden on foreign panel passport."""
        passport_url = reverse('panel_detail', kwargs={'pk': self.panel_a1.id})

        # Bob (other customer)
        self.client.login(username='bob_stranger', password='password123')
        resp_bob = self.client.get(passport_url)
        self.assertEqual(resp_bob.status_code, 403)

        # Eve (unassigned technician)
        self.client.login(username='eve_unassigned_tech', password='password123')
        resp_eve = self.client.get(passport_url)
        self.assertEqual(resp_eve.status_code, 403)

        # Anonymous user redirects to login
        self.client.logout()
        resp_anon = self.client.get(passport_url)
        self.assertEqual(resp_anon.status_code, 302)

    def test_correct_selected_panel_in_inspection_form(self):
        """Passing ?panel_id=<id> pre-populates target panel safely for authorized user."""
        self.client.login(username='alice_owner', password='password123')
        inspect_url = f"{reverse('inspect')}?panel_id={self.panel_a1.id}"
        resp = self.client.get(inspect_url)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['selected_panel'], self.panel_a1)
        self.assertContains(resp, "SG-01-P001")
        self.assertContains(resp, "Target Solar Panel Selected")

    def test_tampered_panel_id_rejection(self):
        """Attempting to pre-select or inspect another customer's panel via GET or POST is rejected."""
        self.client.login(username='alice_owner', password='password123')

        # 1. GET with foreign panel_id does not pre-select Bob's panel
        inspect_url = f"{reverse('inspect')}?panel_id={self.panel_b1.id}"
        resp_get = self.client.get(inspect_url)
        self.assertEqual(resp_get.status_code, 200)
        self.assertIsNone(resp_get.context['selected_panel'])

        # 2. POST with tampered foreign panel is rejected
        test_img = self.create_valid_test_image()
        resp_post = self.client.post(reverse('inspect'), {
            'panel': self.panel_b1.id,
            'image': test_img,
            'notes': 'Tampered inspection submission'
        })
        # Form validation rejects invalid choice or view blocks with 403
        self.assertFalse(Inspection.objects.filter(panel=self.panel_b1, user=self.alice).exists())

    def test_inspection_saved_against_correct_panel_and_inference(self):
        """Valid image upload saves inspection record against exact physical panel with AI prediction."""
        self.client.login(username='alice_owner', password='password123')
        test_img = self.create_valid_test_image()

        resp = self.client.post(reverse('inspect'), {
            'panel': self.panel_a1.id,
            'image': test_img,
            'notes': 'Routine drone scan'
        }, follow=True)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.panel_a1.inspections.count(), 1)

        inspection = self.panel_a1.inspections.first()
        self.assertEqual(inspection.panel, self.panel_a1)
        self.assertEqual(inspection.user, self.alice)
        self.assertIn(inspection.predicted_class, ['Bird-Dropping', 'Dusty', 'Normal', 'Surface-Damage'])
        self.assertGreaterEqual(inspection.confidence_score, 0.0)
        self.assertIsInstance(inspection.class_probabilities, dict)

    def test_invalid_or_corrupted_image_rejection(self):
        """Uploading corrupted bytes or non-image file is rejected by Pillow validation."""
        self.client.login(username='alice_owner', password='password123')
        corrupted_file = SimpleUploadedFile("broken.jpg", b"NOT_A_VALID_IMAGE_DATA_HEADER", content_type="image/jpeg")

        resp = self.client.post(reverse('inspect'), {
            'panel': self.panel_a1.id,
            'image': corrupted_file,
            'notes': 'Broken file test'
        })

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.panel_a1.inspections.count(), 0)
        resp_text = resp.content.decode('utf-8')
        self.assertTrue(
            "corrupted image" in resp_text or "corrupt or not a readable photograph" in resp_text,
            "Expected friendly corrupted image validation message in response"
        )

    def test_not_inspected_default_state(self):
        """Panel with no inspection history defaults to Not Inspected."""
        derived = self.panel_a1.get_derived_condition()
        self.assertEqual(derived['label'], 'Not Inspected')
        self.assertEqual(derived['status'], 'not_inspected')
        self.assertFalse(derived['is_inspected'])

        self.client.login(username='alice_owner', password='password123')
        resp = self.client.get(reverse('panel_detail', kwargs={'pk': self.panel_a1.id}))
        self.assertContains(resp, "Not Yet Inspected")

    def test_latest_inspection_status_derivation(self):
        """Condition status derivation conforms to SolarGuard Phase 5 classification rules."""
        test_img = self.create_valid_test_image()

        # 1. Normal -> Appears Normal
        insp1 = Inspection.objects.create(
            panel=self.panel_a1,
            user=self.alice,
            image=test_img,
            predicted_class='Normal',
            confidence_score=92.5
        )
        self.assertEqual(self.panel_a1.get_derived_condition()['label'], 'Appears Normal')

        # 2. Dusty -> Cleaning May Be Needed
        insp2 = Inspection.objects.create(
            panel=self.panel_a1,
            user=self.alice,
            image=test_img,
            predicted_class='Dusty',
            confidence_score=88.0
        )
        self.assertEqual(self.panel_a1.get_derived_condition()['label'], 'Cleaning May Be Needed')

        # 3. Surface-Damage -> Possible Surface Damage — Technician Review Recommended
        insp3 = Inspection.objects.create(
            panel=self.panel_a1,
            user=self.alice,
            image=test_img,
            predicted_class='Surface-Damage',
            confidence_score=85.0
        )
        self.assertEqual(self.panel_a1.get_derived_condition()['label'], 'Possible Surface Damage — Technician Review Recommended')

        # 4. Low Confidence (< 50%) -> Needs Review
        insp4 = Inspection.objects.create(
            panel=self.panel_a1,
            user=self.alice,
            image=test_img,
            predicted_class='Normal',
            confidence_score=42.0
        )
        self.assertEqual(self.panel_a1.get_derived_condition()['label'], 'Needs Review')

    def test_historical_inspection_preservation(self):
        """Adding multiple inspections preserves chronological history without destruction."""
        test_img = self.create_valid_test_image()
        insp1 = Inspection.objects.create(
            panel=self.panel_a1, user=self.alice, image=test_img,
            predicted_class='Normal', confidence_score=90.0
        )
        insp2 = Inspection.objects.create(
            panel=self.panel_a1, user=self.alice, image=test_img,
            predicted_class='Dusty', confidence_score=85.0
        )

        self.assertEqual(self.panel_a1.inspections.count(), 2)
        history = list(self.panel_a1.inspections.order_by('-inspected_at'))
        self.assertEqual(history[0], insp2)
        self.assertEqual(history[1], insp1)

    def test_technician_review_permission_and_audit_trail(self):
        """Assigned technician can verify inspection finding, recording reviewer and timestamp."""
        test_img = self.create_valid_test_image()
        insp = Inspection.objects.create(
            panel=self.panel_a1, user=self.alice, image=test_img,
            predicted_class='Dusty', confidence_score=80.0
        )

        self.client.login(username='ted_assigned_tech', password='password123')
        result_url = reverse('result_detail', kwargs={'pk': insp.id})
        resp = self.client.post(result_url, {
            'action': 'verify_finding',
            'verified_finding': 'Dusty',
            'review_notes': 'Confirmed moderate dust layer on module cells.'
        }, follow=True)

        self.assertEqual(resp.status_code, 200)
        insp.refresh_from_db()
        self.assertEqual(insp.review_status, 'technician_verified')
        self.assertEqual(insp.verified_outcome, 'Dusty')
        self.assertEqual(insp.reviewed_by, self.ted)
        self.assertIsNotNone(insp.reviewed_at)
        self.assertEqual(insp.review_notes, 'Confirmed moderate dust layer on module cells.')

    def test_customer_cannot_verify_ai_findings(self):
        """Customers receive 403 Forbidden if attempting to verify their own AI findings."""
        test_img = self.create_valid_test_image()
        insp = Inspection.objects.create(
            panel=self.panel_a1, user=self.alice, image=test_img,
            predicted_class='Dusty', confidence_score=80.0
        )

        self.client.login(username='alice_owner', password='password123')
        result_url = reverse('result_detail', kwargs={'pk': insp.id})
        resp = self.client.post(result_url, {
            'action': 'verify_finding',
            'verified_finding': 'Normal',
            'review_notes': 'Customer self-certifying'
        })

        self.assertEqual(resp.status_code, 403)
        insp.refresh_from_db()
        self.assertEqual(insp.review_status, 'ai_predicted')
        self.assertIsNone(insp.reviewed_by)

    def test_ai_prediction_remains_unchanged_after_technician_review(self):
        """Technician verification preserves original AI prediction in database."""
        test_img = self.create_valid_test_image()
        insp = Inspection.objects.create(
            panel=self.panel_a1, user=self.alice, image=test_img,
            predicted_class='Surface-Damage', confidence_score=75.0
        )

        self.client.login(username='ted_assigned_tech', password='password123')
        result_url = reverse('result_detail', kwargs={'pk': insp.id})
        self.client.post(result_url, {
            'action': 'verify_finding',
            'verified_finding': 'Normal',
            'review_notes': 'False positive: shadow caused anomaly.'
        })

        insp.refresh_from_db()
        self.assertEqual(insp.predicted_class, 'Surface-Damage')  # Original AI prediction preserved
        self.assertEqual(insp.verified_outcome, 'Normal')         # Verified finding recorded
        self.assertEqual(insp.review_status, 'technician_verified')

    def test_retired_panel_inspection_restrictions(self):
        """Retired panels cannot be inspected via form or direct POST."""
        from core.permissions import can_inspect_panel
        self.assertFalse(can_inspect_panel(self.alice, self.panel_a2))

        self.client.login(username='alice_owner', password='password123')

        # GET query param for retired panel produces warning and does not pre-select
        inspect_url = f"{reverse('inspect')}?panel_id={self.panel_a2.id}"
        resp_get = self.client.get(inspect_url)
        self.assertEqual(resp_get.status_code, 200)
        self.assertIsNone(resp_get.context['selected_panel'])

        # POST directly targeting retired panel is blocked
        test_img = self.create_valid_test_image()
        resp_post = self.client.post(reverse('inspect'), {
            'panel': self.panel_a2.id,
            'image': test_img,
            'notes': 'Trying to inspect retired module'
        })
        self.assertFalse(Inspection.objects.filter(panel=self.panel_a2).exists())

    def test_maintenance_request_linked_to_correct_panel(self):
        """Maintenance ticket created from panel passport is linked to exact panel and not auto-assigned."""
        self.client.login(username='alice_owner', password='password123')

        issue_create_url = f"{reverse('issue_create')}?panel_id={self.panel_a1.id}"
        resp_get = self.client.get(issue_create_url)
        self.assertEqual(resp_get.status_code, 200)

        resp_post = self.client.post(reverse('issue_create'), {
            'panel': self.panel_a1.id,
            'title': 'Dust Wash Order',
            'description': 'Heavy particulate accumulation.',
            'status': 'Open',
            'priority': 'Medium'
        }, follow=True)

        self.assertEqual(resp_post.status_code, 200)
        issue = MaintenanceIssue.objects.get(title='Dust Wash Order')
        self.assertEqual(issue.panel, self.panel_a1)
        self.assertEqual(issue.installation, self.inst_a)
        self.assertIsNone(issue.assigned_technician)  # Not automatically assigned

    def test_secure_inspection_image_access(self):
        """Protected media endpoint enforces authorization on inspection photos."""
        test_img = self.create_valid_test_image()
        insp = Inspection.objects.create(
            panel=self.panel_a1, user=self.alice, image=test_img,
            predicted_class='Normal', confidence_score=90.0
        )
        img_url = reverse('secure_inspection_image', kwargs={'pk': insp.id})

        # Alice (owner) allowed
        self.client.login(username='alice_owner', password='password123')
        resp_alice = self.client.get(img_url)
        self.assertEqual(resp_alice.status_code, 200)

        # Ted (assigned technician) allowed
        self.client.login(username='ted_assigned_tech', password='password123')
        resp_ted = self.client.get(img_url)
        self.assertEqual(resp_ted.status_code, 200)

        # Bob (other customer) denied
        self.client.login(username='bob_stranger', password='password123')
        resp_bob = self.client.get(img_url)
        self.assertEqual(resp_bob.status_code, 403)

        # Eve (unassigned technician) denied
        self.client.login(username='eve_unassigned_tech', password='password123')
        resp_eve = self.client.get(img_url)
        self.assertEqual(resp_eve.status_code, 403)


class SolarGuardPhase7MaintenanceTests(TestCase):
    """
    Phase 7 Test Suite:
    - Customer creates own maintenance request (with optional photo)
    - Customer cannot create issue for another owner's panel (403 Forbidden or validation rejection)
    - Customer cannot assign technician (assigned_technician remains None)
    - Admin assigns valid certified technician (Open -> Assigned, logged)
    - Admin cannot assign a customer as technician (form validation rejection)
    - Technician sees only assigned work orders (issue_list filtering and object-level permissions)
    - Technician cannot self-assign unassigned jobs (403 Forbidden)
    - Technician starts assigned task (Assigned -> In Progress)
    - Technician records maintenance notes and field actions (cleaning updates panel.last_cleaned_date)
    - Technician resolves task with notes (In Progress -> Resolved, resolved_at set)
    - Resolution without required notes rejected (minimum 10 chars enforced)
    - Invalid status transitions rejected (e.g., Open directly to Resolved, or customer resolving)
    - Reassignment logged in audit trail
    - Historical maintenance logs preserved and admin closure (Resolved -> Closed, closed_at set)
    - Duplicate submission warning & confirmation override
    - Panel Digital Passport shows linked maintenance history and resolution notes
    - Resolution does not overwrite AI inspection result or auto-mark normal
    - Role dashboards display correct maintenance counts (customer open issues, tech assigned tasks, admin unassigned & active counts)
    """

    def setUp(self):
        self.client = Client()

        # Users and roles
        self.alice = User.objects.create_user(username='alice_cust', password='password123')
        self.alice.profile.role = 'customer'
        self.alice.profile.save()

        self.bob = User.objects.create_user(username='bob_cust', password='password123')
        self.bob.profile.role = 'customer'
        self.bob.profile.save()

        self.ted = User.objects.create_user(username='ted_tech', password='password123')
        self.ted.profile.role = 'technician'
        self.ted.profile.is_certified_technician = True
        self.ted.profile.save()

        self.eve = User.objects.create_user(username='eve_tech', password='password123')
        self.eve.profile.role = 'technician'
        self.eve.profile.is_certified_technician = True
        self.eve.profile.save()

        self.dan = User.objects.create_superuser(username='dan_admin', password='password123', email='dan@sg.test')
        self.dan.profile.role = 'admin'
        self.dan.profile.save()

        # Installations
        self.inst_a = Installation.objects.create(
            name="Alice Sunnyvale Array",
            owner=self.alice,
            site_address="100 Solar Way, Sunnyvale",
            install_date=datetime.date(2023, 1, 15)
        )

        self.inst_b = Installation.objects.create(
            name="Bob Mountain View Array",
            owner=self.bob,
            site_address="200 Sun Blvd, Mountain View",
            install_date=datetime.date(2023, 2, 20)
        )

        # Panels
        self.panel_a1 = Panel.objects.create(
            installation=self.inst_a,
            user=self.alice,
            permanent_id="SG-A-01",
            serial_number="PANEL-A-01",
            site_location=self.inst_a.site_address,
            grid_row=1,
            grid_col=1,
            status='active',
            install_date=datetime.date(2023, 1, 15),
            last_cleaned_date=datetime.date(2024, 1, 1)
        )

        self.panel_b1 = Panel.objects.create(
            installation=self.inst_b,
            user=self.bob,
            permanent_id="SG-B-01",
            serial_number="PANEL-B-01",
            site_location=self.inst_b.site_address,
            grid_row=1,
            grid_col=1,
            status='active',
            install_date=datetime.date(2023, 2, 20)
        )

    def create_valid_test_image(self):
        """Creates an in-memory valid RGB JPEG image."""
        img = Image.new('RGB', (224, 224), color=(40, 70, 110))
        draw = ImageDraw.Draw(img)
        draw.line([(20, 20), (200, 200)], fill=(220, 220, 220), width=4)
        draw.rectangle([(50, 50), (150, 150)], outline=(190, 190, 60), width=3)
        img_io = io.BytesIO()
        img.save(img_io, format='JPEG')
        img_io.seek(0)
        return SimpleUploadedFile("maintenance_photo.jpg", img_io.getvalue(), content_type="image/jpeg")

    def test_customer_creates_own_maintenance_request(self):
        """Customer creates a maintenance request with optional photo for their own panel."""
        self.client.login(username='alice_cust', password='password123')
        photo = self.create_valid_test_image()
        response = self.client.post(reverse('issue_create'), {
            'panel': self.panel_a1.id,
            'title': 'Loose mounting bracket',
            'description': 'The bracket on the top-left appears loose after wind storm.',
            'priority': 'Medium',
            'supporting_photo': photo
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        issue = MaintenanceIssue.objects.get(title='Loose mounting bracket')
        self.assertEqual(issue.status, 'Open')
        self.assertEqual(issue.panel, self.panel_a1)
        self.assertEqual(issue.installation, self.inst_a)
        self.assertEqual(issue.user, self.alice)
        self.assertIsNone(issue.assigned_technician)
        self.assertTrue(bool(issue.supporting_photo))

        # Check creation log
        log = issue.logs.filter(action_type='status_change', new_status='Open').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.user, self.alice)

    def test_customer_cannot_create_issue_for_another_owners_panel(self):
        """Customer cannot create an issue for a panel belonging to another customer."""
        self.client.login(username='alice_cust', password='password123')
        response = self.client.post(reverse('issue_create'), {
            'panel': self.panel_b1.id,
            'title': 'Tampering with Bob Panel',
            'description': 'Malicious ticket attempt',
            'priority': 'Low'
        })
        self.assertIn(response.status_code, [403, 200])
        self.assertFalse(MaintenanceIssue.objects.filter(panel=self.panel_b1).exists())

    def test_customer_cannot_assign_technician(self):
        """Customer cannot set assigned_technician on issue creation."""
        self.client.login(username='alice_cust', password='password123')
        response = self.client.post(reverse('issue_create'), {
            'panel': self.panel_a1.id,
            'title': 'Attempt Self-Assignment of Tech',
            'description': 'Customer tries to bypass admin dispatching.',
            'priority': 'High',
            'assigned_technician': self.ted.id
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        issue = MaintenanceIssue.objects.get(title='Attempt Self-Assignment of Tech')
        self.assertIsNone(issue.assigned_technician)

    def test_admin_assigns_valid_technician(self):
        """Admin assigns a certified technician to an open maintenance request."""
        issue = MaintenanceIssue.objects.create(
            panel=self.panel_a1, installation=self.inst_a, user=self.alice,
            title='Inverter Warning', description='Inverter red led blinking.',
            status='Open', priority='Low'
        )
        self.client.login(username='dan_admin', password='password123')
        response = self.client.post(reverse('issue_detail', kwargs={'pk': issue.id}), {
            'action': 'assign_technician',
            'technician': self.ted.id,
            'priority': 'High',
            'notes': 'High priority dispatch. Inspect on arrival.'
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        issue.refresh_from_db()
        self.assertEqual(issue.status, 'Assigned')
        self.assertEqual(issue.assigned_technician, self.ted)
        self.assertEqual(issue.priority, 'High')

        # Verify audit log
        log = issue.logs.filter(action_type='assignment').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.technician, self.ted)
        self.assertEqual(log.previous_status, 'Open')
        self.assertEqual(log.new_status, 'Assigned')
        self.assertIn('High priority dispatch', log.notes)

    def test_admin_cannot_assign_customer_as_technician(self):
        """Admin cannot assign a customer user as a technician."""
        issue = MaintenanceIssue.objects.create(
            panel=self.panel_a1, installation=self.inst_a, user=self.alice,
            title='Panel Glass Cleaning', description='Dust wash needed.',
            status='Open', priority='Low'
        )
        self.client.login(username='dan_admin', password='password123')
        response = self.client.post(reverse('issue_detail', kwargs={'pk': issue.id}), {
            'action': 'assign_technician',
            'technician': self.bob.id,  # Bob is a customer
            'priority': 'Medium'
        }, follow=True)

        issue.refresh_from_db()
        self.assertIsNone(issue.assigned_technician)
        self.assertEqual(issue.status, 'Open')

    def test_technician_sees_only_assigned_work_orders(self):
        """Technician only sees work orders assigned to them, not other technicians' or unassigned ones."""
        issue_ted = MaintenanceIssue.objects.create(
            panel=self.panel_a1, installation=self.inst_a, user=self.alice,
            title='Ted Task 1', description='Assigned to Ted',
            status='Assigned', assigned_technician=self.ted
        )
        issue_eve = MaintenanceIssue.objects.create(
            panel=self.panel_b1, installation=self.inst_b, user=self.bob,
            title='Eve Task 2', description='Assigned to Eve',
            status='Assigned', assigned_technician=self.eve
        )
        issue_unassigned = MaintenanceIssue.objects.create(
            panel=self.panel_a1, installation=self.inst_a, user=self.alice,
            title='Unassigned Task 3', description='Nobody assigned yet',
            status='Open', assigned_technician=None
        )

        self.client.login(username='ted_tech', password='password123')

        # List view
        resp_list = self.client.get(reverse('issue_list'))
        self.assertEqual(resp_list.status_code, 200)
        self.assertContains(resp_list, 'Ted Task 1')
        self.assertNotContains(resp_list, 'Eve Task 2')
        self.assertNotContains(resp_list, 'Unassigned Task 3')

        # Detail view access
        self.assertEqual(self.client.get(reverse('issue_detail', kwargs={'pk': issue_ted.id})).status_code, 200)
        self.assertEqual(self.client.get(reverse('issue_detail', kwargs={'pk': issue_eve.id})).status_code, 403)
        self.assertEqual(self.client.get(reverse('issue_detail', kwargs={'pk': issue_unassigned.id})).status_code, 403)

    def test_technician_cannot_self_assign_unassigned_job(self):
        """Technician cannot assign themselves to an unassigned work order."""
        issue = MaintenanceIssue.objects.create(
            panel=self.panel_a1, installation=self.inst_a, user=self.alice,
            title='Open Job', description='Needs assignment',
            status='Open', assigned_technician=None
        )
        self.client.login(username='ted_tech', password='password123')
        resp = self.client.post(reverse('issue_detail', kwargs={'pk': issue.id}), {
            'action': 'assign_technician',
            'technician': self.ted.id
        })
        self.assertEqual(resp.status_code, 403)
        issue.refresh_from_db()
        self.assertIsNone(issue.assigned_technician)

    def test_technician_starts_assigned_task(self):
        """Assigned technician starts work, transitioning status from Assigned to In Progress."""
        issue = MaintenanceIssue.objects.create(
            panel=self.panel_a1, installation=self.inst_a, user=self.alice,
            title='Module Inspection', description='Inspect micro-cracks',
            status='Assigned', assigned_technician=self.ted
        )
        self.client.login(username='ted_tech', password='password123')
        resp = self.client.post(reverse('issue_detail', kwargs={'pk': issue.id}), {
            'action': 'start_work'
        }, follow=True)
        self.assertEqual(resp.status_code, 200)
        issue.refresh_from_db()
        self.assertEqual(issue.status, 'In Progress')

        log = issue.logs.filter(action_type='status_change', new_status='In Progress').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.user, self.ted)
        self.assertEqual(log.previous_status, 'Assigned')

    def test_technician_records_maintenance_notes_and_actions(self):
        """Technician logs field actions; cleaning action updates panel.last_cleaned_date."""
        issue = MaintenanceIssue.objects.create(
            panel=self.panel_a1, installation=self.inst_a, user=self.alice,
            title='Array Cleaning Order', description='Wash soiling',
            status='In Progress', assigned_technician=self.ted
        )
        self.client.login(username='ted_tech', password='password123')
        today = datetime.date.today()
        resp = self.client.post(reverse('issue_detail', kwargs={'pk': issue.id}), {
            'action': 'add_log',
            'action_type': 'cleaning',
            'performed_at': today.strftime('%Y-%m-%d'),
            'notes': 'Performed soft-sponge water wash on module surface.'
        }, follow=True)
        self.assertEqual(resp.status_code, 200)

        # Check log
        log = issue.logs.filter(action_type='cleaning').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.user, self.ted)

        # Check panel last_cleaned_date updated
        self.panel_a1.refresh_from_db()
        self.assertEqual(self.panel_a1.last_cleaned_date, today)

    def test_technician_resolves_task_with_notes(self):
        """Technician marks work Resolved with mandatory resolution notes."""
        issue = MaintenanceIssue.objects.create(
            panel=self.panel_a1, installation=self.inst_a, user=self.alice,
            title='Junction Box Check', description='Inspect bypass diode',
            status='In Progress', assigned_technician=self.ted
        )
        self.client.login(username='ted_tech', password='password123')
        resp = self.client.post(reverse('issue_detail', kwargs={'pk': issue.id}), {
            'action': 'resolve_work',
            'resolution_notes': 'Replaced bypass diode and verified junction box sealant.'
        }, follow=True)
        self.assertEqual(resp.status_code, 200)

        issue.refresh_from_db()
        self.assertEqual(issue.status, 'Resolved')
        self.assertIsNotNone(issue.resolved_at)
        self.assertIn('Replaced bypass diode', issue.resolution_notes)

        # Verify resolution log
        log = issue.logs.filter(action_type='resolution').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.user, self.ted)
        self.assertEqual(log.new_status, 'Resolved')

    def test_resolution_without_required_notes_rejected(self):
        """Attempting to resolve a work order with empty or too-short notes is rejected."""
        issue = MaintenanceIssue.objects.create(
            panel=self.panel_a1, installation=self.inst_a, user=self.alice,
            title='Inverter Reset', description='Restart inverter',
            status='In Progress', assigned_technician=self.ted
        )
        self.client.login(username='ted_tech', password='password123')
        resp = self.client.post(reverse('issue_detail', kwargs={'pk': issue.id}), {
            'action': 'resolve_work',
            'resolution_notes': 'done'  # Too short (< 10 chars)
        }, follow=True)
        self.assertEqual(resp.status_code, 200)

        issue.refresh_from_db()
        self.assertEqual(issue.status, 'In Progress')
        self.assertIsNone(issue.resolved_at)

    def test_invalid_status_transitions_rejected(self):
        """Invalid state transitions like jumping from Open to Resolved or customer resolving are rejected."""
        issue = MaintenanceIssue.objects.create(
            panel=self.panel_a1, installation=self.inst_a, user=self.alice,
            title='Open Ticket', description='Cannot jump to resolved',
            status='Open', assigned_technician=None
        )

        # 1. Customer attempts to resolve
        self.client.login(username='alice_cust', password='password123')
        resp = self.client.post(reverse('issue_detail', kwargs={'pk': issue.id}), {
            'action': 'resolve_work',
            'resolution_notes': 'Customer trying to mark done themselves'
        })
        self.assertEqual(resp.status_code, 403)

        # 2. Tech attempts to resolve an Open/unassigned ticket
        self.client.login(username='ted_tech', password='password123')
        resp = self.client.post(reverse('issue_detail', kwargs={'pk': issue.id}), {
            'action': 'resolve_work',
            'resolution_notes': 'Tech trying to resolve unassigned ticket'
        })
        self.assertEqual(resp.status_code, 403)

        issue.refresh_from_db()
        self.assertEqual(issue.status, 'Open')

    def test_reassignment_logged(self):
        """Reassigning technician updates assigned_technician and creates audit log."""
        issue = MaintenanceIssue.objects.create(
            panel=self.panel_a1, installation=self.inst_a, user=self.alice,
            title='Conduit Repair', description='Conduit replacement required',
            status='Assigned', assigned_technician=self.ted
        )
        self.client.login(username='dan_admin', password='password123')
        resp = self.client.post(reverse('issue_detail', kwargs={'pk': issue.id}), {
            'action': 'assign_technician',
            'technician': self.eve.id,
            'priority': 'High',
            'notes': 'Reassigned to Eve due to Ted schedule conflict.'
        }, follow=True)
        self.assertEqual(resp.status_code, 200)

        issue.refresh_from_db()
        self.assertEqual(issue.assigned_technician, self.eve)

        log = issue.logs.filter(action_type='assignment').last()
        self.assertIsNotNone(log)
        self.assertEqual(log.technician, self.eve)
        self.assertIn('Reassigned from ted_tech to eve_tech', log.notes)

    def test_historical_maintenance_logs_preserved_and_admin_closure(self):
        """Full maintenance lifecycle preserves complete audit trail and supports admin closure."""
        issue = MaintenanceIssue.objects.create(
            panel=self.panel_a1, installation=self.inst_a, user=self.alice,
            title='Full Cycle Ticket', description='Lifecycle test',
            status='Resolved', assigned_technician=self.ted,
            resolution_notes='Work completed on-site.'
        )
        MaintenanceLog.objects.create(
            panel=self.panel_a1, issue=issue, user=self.dan,
            action_type='assignment', previous_status='Open', new_status='Assigned',
            technician=self.ted, notes='Initial assignment.'
        )
        MaintenanceLog.objects.create(
            panel=self.panel_a1, issue=issue, user=self.ted,
            action_type='resolution', previous_status='In Progress', new_status='Resolved',
            notes='Resolved by Ted.'
        )

        # Admin Dan closes the work order
        self.client.login(username='dan_admin', password='password123')
        resp = self.client.post(reverse('issue_detail', kwargs={'pk': issue.id}), {
            'action': 'close_work',
            'closure_notes': 'Audited and approved for closure.'
        }, follow=True)
        self.assertEqual(resp.status_code, 200)

        issue.refresh_from_db()
        self.assertEqual(issue.status, 'Closed')
        self.assertIsNotNone(issue.closed_at)

        # Verify all logs remain intact
        logs = issue.logs.order_by('id')
        self.assertEqual(logs.count(), 3)
        self.assertEqual(logs.last().action_type, 'closure')
        self.assertEqual(logs.last().new_status, 'Closed')

    def test_duplicate_submission_prevention(self):
        """Duplicate request for panel with active work order warns user unless confirmed."""
        MaintenanceIssue.objects.create(
            panel=self.panel_a1, installation=self.inst_a, user=self.alice,
            title='Existing Active Issue', description='Under active review',
            status='In Progress', assigned_technician=self.ted
        )
        self.client.login(username='alice_cust', password='password123')

        # 1. Without confirm_duplicate -> rejected with warning, count unchanged
        resp = self.client.post(reverse('issue_create'), {
            'panel': self.panel_a1.id,
            'title': 'Duplicate Accidental Submit',
            'description': 'Same issue again',
            'priority': 'Medium'
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'already has an active work order')
        self.assertEqual(self.panel_a1.issues.count(), 1)

        # 2. With confirm_duplicate=True -> allowed
        resp_confirmed = self.client.post(reverse('issue_create'), {
            'panel': self.panel_a1.id,
            'title': 'Confirmed Distinct Issue',
            'description': 'Second issue confirmed',
            'priority': 'Low',
            'confirm_duplicate': 'on'
        }, follow=True)
        self.assertEqual(resp_confirmed.status_code, 200)
        self.assertEqual(self.panel_a1.issues.count(), 2)

    def test_panel_passport_shows_linked_maintenance_history(self):
        """Panel Digital Passport displays linked maintenance issues, technician, and resolution notes."""
        issue = MaintenanceIssue.objects.create(
            panel=self.panel_a1, installation=self.inst_a, user=self.alice,
            title='Cracked Glass Seal', description='Seal replaced',
            status='Resolved', assigned_technician=self.ted,
            resolution_notes='Seal replaced with weatherproof silicone.'
        )
        self.client.login(username='alice_cust', password='password123')
        resp = self.client.get(reverse('panel_detail', kwargs={'pk': self.panel_a1.id}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Cracked Glass Seal')
        self.assertContains(resp, 'Resolved')
        self.assertContains(resp, 'ted_tech')
        self.assertContains(resp, 'Seal replaced with weatherproof silicone')

    def test_resolution_does_not_overwrite_ai_inspection_result(self):
        """Resolving a maintenance issue does not alter the AI inspection finding or auto-mark normal."""
        insp_img = self.create_valid_test_image()
        insp = Inspection.objects.create(
            panel=self.panel_a1, user=self.alice, image=insp_img,
            predicted_class='Bird-Dropping', confidence_score=88.5,
            maintenance_priority_level='Cleaning Recommended'
        )
        issue = MaintenanceIssue.objects.create(
            panel=self.panel_a1, installation=self.inst_a, user=self.alice,
            inspection=insp, title='Dropping Cleanup', description='Dropping wash needed',
            status='In Progress', assigned_technician=self.ted
        )

        # Resolve work order
        self.client.login(username='ted_tech', password='password123')
        resp = self.client.post(reverse('issue_detail', kwargs={'pk': issue.id}), {
            'action': 'resolve_work',
            'resolution_notes': 'Droppings cleaned off thoroughly.'
        }, follow=True)
        self.assertEqual(resp.status_code, 200)

        # Verify AI prediction is completely untouched
        insp.refresh_from_db()
        self.assertEqual(insp.predicted_class, 'Bird-Dropping')
        self.assertEqual(insp.confidence_score, 88.5)

        # Verify panel condition does NOT become 'normal' without a new inspection
        cond = self.panel_a1.get_derived_condition()
        self.assertEqual(cond['status'], 'bird')
        self.assertNotEqual(cond['label'], 'Appears Normal')

    def test_role_dashboards_display_correct_maintenance_counts(self):
        """Role dashboards display accurate, role-scoped maintenance counts."""
        # Issue 1: Open, unassigned, owned by Alice
        MaintenanceIssue.objects.create(
            panel=self.panel_a1, installation=self.inst_a, user=self.alice,
            title='Alice Open Job', description='Open ticket',
            status='Open', assigned_technician=None
        )
        # Issue 2: In Progress, assigned to Ted
        MaintenanceIssue.objects.create(
            panel=self.panel_a1, installation=self.inst_a, user=self.alice,
            title='Ted In-Progress Job', description='Assigned to Ted',
            status='In Progress', assigned_technician=self.ted
        )

        # 1. Customer Alice Dashboard
        self.client.login(username='alice_cust', password='password123')
        resp_cust = self.client.get(reverse('dashboard'))
        self.assertEqual(resp_cust.status_code, 200)
        self.assertEqual(resp_cust.context['open_issues_count'], 2)

        # 2. Technician Ted Dashboard
        self.client.login(username='ted_tech', password='password123')
        resp_tech = self.client.get(reverse('dashboard'))
        self.assertEqual(resp_tech.status_code, 200)
        self.assertEqual(resp_tech.context['assigned_tasks_count'], 1)

        # 3. Admin Dan Dashboard
        self.client.login(username='dan_admin', password='password123')
        resp_admin = self.client.get(reverse('dashboard'))
        self.assertEqual(resp_admin.status_code, 200)
        self.assertEqual(resp_admin.context['unassigned_issues_count'], 1)
        self.assertEqual(resp_admin.context['active_work_orders_count'], 1)


class SolarGuardPhase8ReportingTests(TestCase):
    """
    Phase 8 Test Suite:
    - Inspection history filters (installation, panel, condition, review status, date range)
    - Inspection history pagination
    - Cross-customer inspection history isolation
    - Retired panel history preservation
    - Individual panel inspection report accuracy & disclaimers
    - Installation condition summary report accuracy (active vs retired counts)
    - Maintenance history audit report accuracy
    - Report access authorization & cross-tenant denial (403 Forbidden)
    - Native PDF downloads for all 3 report types
    - Object-level security for maintenance supporting photographs (secure_maintenance_photo)
    - Empty report handling without crashes
    - Technician review audit distinction from raw AI prediction
    - Correct latest-condition calculations unaffected by maintenance resolutions
    """

    def setUp(self):
        self.client = Client()

        # Users and roles
        self.alice = User.objects.create_user(username='alice_rep', password='password123')
        self.alice.profile.role = 'customer'
        self.alice.profile.save()

        self.bob = User.objects.create_user(username='bob_rep', password='password123')
        self.bob.profile.role = 'customer'
        self.bob.profile.save()

        self.ted = User.objects.create_user(username='ted_rep_tech', password='password123')
        self.ted.profile.role = 'technician'
        self.ted.profile.is_certified_technician = True
        self.ted.profile.save()

        self.eve = User.objects.create_user(username='eve_rep_tech', password='password123')
        self.eve.profile.role = 'technician'
        self.eve.profile.is_certified_technician = True
        self.eve.profile.save()

        self.dan = User.objects.create_superuser(username='dan_rep_admin', password='password123', email='dan@sg.test')
        self.dan.profile.role = 'admin'
        self.dan.profile.save()

        # Installations
        self.inst_a = Installation.objects.create(
            name="Alice Sunnyvale Array",
            owner=self.alice,
            assigned_technician=self.ted,
            site_address="100 Solar Way, Sunnyvale",
            install_date=datetime.date(2023, 1, 15)
        )

        self.inst_b = Installation.objects.create(
            name="Bob Mountain View Array",
            owner=self.bob,
            assigned_technician=self.eve,
            site_address="200 Sun Blvd, Mountain View",
            install_date=datetime.date(2023, 2, 20)
        )

        # Panels: A1 (active), A2 (retired), B1 (active)
        self.panel_a1 = Panel.objects.create(
            installation=self.inst_a,
            user=self.alice,
            permanent_id="SG-08-A01",
            serial_number="PANEL-A01-SN",
            site_location=self.inst_a.site_address,
            grid_row=1,
            grid_col=1,
            status='active',
            install_date=datetime.date(2023, 1, 15),
            last_cleaned_date=datetime.date(2024, 1, 1)
        )

        self.panel_a2 = Panel.objects.create(
            installation=self.inst_a,
            user=self.alice,
            permanent_id="SG-08-A02",
            serial_number="PANEL-A02-RETIRED",
            site_location=self.inst_a.site_address,
            grid_row=1,
            grid_col=2,
            status='retired',
            install_date=datetime.date(2023, 1, 15)
        )

        self.panel_b1 = Panel.objects.create(
            installation=self.inst_b,
            user=self.bob,
            permanent_id="SG-08-B01",
            serial_number="PANEL-B01-SN",
            site_location=self.inst_b.site_address,
            grid_row=1,
            grid_col=1,
            status='active',
            install_date=datetime.date(2023, 2, 20)
        )

        # In-memory test images
        self.test_img_1 = self.create_valid_test_image()
        self.test_img_2 = self.create_valid_test_image()
        self.test_img_3 = self.create_valid_test_image()
        self.test_img_4 = self.create_valid_test_image()
        self.photo_1 = self.create_valid_test_image()
        self.photo_2 = self.create_valid_test_image()

        now = timezone.now()

        # Inspections
        # 1. Panel A1: older normal inspection (10 days ago), verified by Ted
        self.insp_a1_old = Inspection.objects.create(
            panel=self.panel_a1,
            user=self.alice,
            image=self.test_img_1,
            predicted_class='Normal',
            confidence_score=94.5,
            review_status='technician_verified',
            verified_outcome='Normal Surface Glass',
            reviewed_by=self.ted,
            reviewed_at=now - datetime.timedelta(days=9),
            inspected_at=now - datetime.timedelta(days=10)
        )

        # 2. Panel A1: recent dusty inspection (2 days ago), unverified AI predicted
        self.insp_a1_new = Inspection.objects.create(
            panel=self.panel_a1,
            user=self.alice,
            image=self.test_img_2,
            predicted_class='Dusty',
            confidence_score=89.2,
            review_status='ai_predicted',
            inspected_at=now - datetime.timedelta(days=2)
        )

        # 3. Panel A2 (retired): cracked inspection (30 days ago), verified fault
        self.insp_a2_retired = Inspection.objects.create(
            panel=self.panel_a2,
            user=self.alice,
            image=self.test_img_3,
            predicted_class='Cracked',
            confidence_score=96.0,
            review_status='technician_verified',
            verified_outcome='Glass Fracture at Busbar',
            reviewed_by=self.ted,
            reviewed_at=now - datetime.timedelta(days=29),
            inspected_at=now - datetime.timedelta(days=30)
        )

        # 4. Panel B1 (Bob): bird-dropping inspection (1 day ago)
        self.insp_b1 = Inspection.objects.create(
            panel=self.panel_b1,
            user=self.bob,
            image=self.test_img_4,
            predicted_class='Bird-Dropping',
            confidence_score=91.0,
            review_status='ai_predicted',
            inspected_at=now - datetime.timedelta(days=1)
        )

        # Maintenance issues
        self.issue_a = MaintenanceIssue.objects.create(
            panel=self.panel_a1,
            installation=self.inst_a,
            user=self.alice,
            assigned_technician=self.ted,
            title='Surface Dust Washing Order',
            description='Particulate accumulation obscuring irradiance.',
            status='Resolved',
            priority='Medium',
            supporting_photo=self.photo_1,
            resolution_notes='Panel surface washed with deionized water. Mounting checked.',
            resolved_at=now - datetime.timedelta(days=1)
        )

        self.issue_b = MaintenanceIssue.objects.create(
            panel=self.panel_b1,
            installation=self.inst_b,
            user=self.bob,
            assigned_technician=None,
            title='Bird Dropping Clean-off',
            description='Opaque organic spot detected.',
            status='Open',
            priority='High',
            supporting_photo=self.photo_2
        )

    def create_valid_test_image(self):
        """Creates an in-memory valid RGB JPEG image."""
        img = Image.new('RGB', (224, 224), color=(40, 70, 110))
        draw = ImageDraw.Draw(img)
        draw.line([(20, 20), (200, 200)], fill=(220, 220, 220), width=4)
        draw.rectangle([(50, 50), (150, 150)], outline=(190, 190, 60), width=3)
        img_io = io.BytesIO()
        img.save(img_io, format='JPEG')
        img_io.seek(0)
        return SimpleUploadedFile("report_test.jpg", img_io.getvalue(), content_type="image/jpeg")

    def test_inspection_history_filters_and_pagination(self):
        """Inspection history supports filtering by installation, panel, condition, review state, and pagination."""
        self.client.login(username='alice_rep', password='password123')

        # 1. Base view: Alice sees only her 3 inspections (panel A1 x2, panel A2 x1)
        resp = self.client.get(reverse('inspection_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['page_obj'].paginator.count, 3)
        self.assertContains(resp, 'SG-08-A01')
        self.assertContains(resp, 'SG-08-A02')
        self.assertNotContains(resp, 'SG-08-B01')

        # 2. Filter by condition='Dusty'
        resp_dusty = self.client.get(f"{reverse('inspection_list')}?condition=Dusty")
        self.assertEqual(resp_dusty.status_code, 200)
        self.assertEqual(resp_dusty.context['page_obj'].paginator.count, 1)
        self.assertEqual(resp_dusty.context['page_obj'].object_list[0].id, self.insp_a1_new.id)

        # 3. Filter by review_status='technician_verified'
        resp_verified = self.client.get(f"{reverse('inspection_list')}?review_status=technician_verified")
        self.assertEqual(resp_verified.status_code, 200)
        self.assertEqual(resp_verified.context['page_obj'].paginator.count, 2)
        self.assertIn(self.insp_a1_old.id, [obj.id for obj in resp_verified.context['page_obj'].object_list])
        self.assertIn(self.insp_a2_retired.id, [obj.id for obj in resp_verified.context['page_obj'].object_list])

        # 4. Filter by target panel
        resp_p2 = self.client.get(f"{reverse('inspection_list')}?panel={self.panel_a2.id}")
        self.assertEqual(resp_p2.status_code, 200)
        self.assertEqual(resp_p2.context['page_obj'].paginator.count, 1)
        self.assertEqual(resp_p2.context['page_obj'].object_list[0].id, self.insp_a2_retired.id)

    def test_cross_customer_history_isolation(self):
        """Customer cannot view another customer's inspections via tampering."""
        self.client.login(username='bob_rep', password='password123')

        # Bob visits inspections list: sees only his 1 inspection
        resp = self.client.get(reverse('inspection_list'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['page_obj'].paginator.count, 1)
        self.assertContains(resp, 'SG-08-B01')
        self.assertNotContains(resp, 'SG-08-A01')

        # Bob tries to tamper filter by Alice's installation ID
        resp_tamper = self.client.get(f"{reverse('inspection_list')}?installation={self.inst_a.id}")
        self.assertEqual(resp_tamper.status_code, 200)
        self.assertEqual(resp_tamper.context['page_obj'].paginator.count, 0)
        self.assertNotContains(resp_tamper, 'SG-08-A01')

    def test_retired_panel_history_preservation(self):
        """Retired panels preserve complete inspection and maintenance history."""
        self.client.login(username='alice_rep', password='password123')

        # Panel A2 is retired
        self.assertEqual(self.panel_a2.status, 'retired')

        # Inspection on retired panel is viewable in inspection list
        resp = self.client.get(f"{reverse('inspection_list')}?panel={self.panel_a2.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'SG-08-A02')
        self.assertContains(resp, 'Retired')
        self.assertContains(resp, 'Cracked')

        # Digital Passport for retired panel renders history cleanly
        resp_passport = self.client.get(reverse('panel_detail', kwargs={'pk': self.panel_a2.id}))
        self.assertEqual(resp_passport.status_code, 200)
        self.assertContains(resp_passport, 'Cracked')
        self.assertContains(resp_passport, 'Retired')

    def test_report_accuracy_and_disclaimer(self):
        """Panel report contains authentic saved data and explicit optical RGB disclaimer."""
        self.client.login(username='alice_rep', password='password123')

        resp = self.client.get(reverse('report_panel', kwargs={'pk': self.panel_a1.id}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'SG-08-A01')
        self.assertContains(resp, 'PANEL-A01-SN')
        self.assertContains(resp, 'Alice Sunnyvale Array')
        self.assertContains(resp, 'Cleaning May Be Needed')
        self.assertContains(resp, 'Surface Dust Washing Order')
        self.assertContains(resp, 'ted_rep_tech')
        self.assertContains(resp, 'Panel surface washed with deionized water')

        # Verify explicit disclaimer is present
        self.assertContains(resp, 'Technical Notice &amp; Optical Classification Limitations')
        self.assertContains(resp, 'cannot verify internal electrical output')

        # Uninspected panel test: create new uninspected panel
        uninspected = Panel.objects.create(
            installation=self.inst_a,
            user=self.alice,
            permanent_id="SG-08-NEW",
            serial_number="NEW-UNINSPECTED-SN",
            status='active'
        )
        resp_uninspected = self.client.get(reverse('report_panel', kwargs={'pk': uninspected.id}))
        self.assertEqual(resp_uninspected.status_code, 200)
        self.assertContains(resp_uninspected, 'Not Inspected')
        self.assertNotContains(resp_uninspected, 'Normal Operational')

    def test_installation_condition_summary_report(self):
        """Installation condition summary report accurately distinguishes active from retired modules."""
        self.client.login(username='alice_rep', password='password123')

        resp = self.client.get(reverse('report_installation', kwargs={'pk': self.inst_a.id}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Alice Sunnyvale Array')
        self.assertEqual(resp.context['breakdown']['total_active'], 1)  # Panel A1
        self.assertEqual(resp.context['breakdown']['total_retired'], 1) # Panel A2
        self.assertEqual(resp.context['breakdown']['cleaning'], 1)       # Panel A1 is Dusty
        self.assertContains(resp, 'Technical Notice &amp; Optical Classification Limitations')

    def test_report_download_authorization(self):
        """Report endpoints enforce strict object-level authorization across customers and technicians."""
        # 1. Alice allowed for own panel & installation
        self.client.login(username='alice_rep', password='password123')
        self.assertEqual(self.client.get(reverse('report_panel', kwargs={'pk': self.panel_a1.id})).status_code, 200)
        self.assertEqual(self.client.get(reverse('report_installation', kwargs={'pk': self.inst_a.id})).status_code, 200)

        # 2. Bob denied for Alice's panel & installation -> 403
        self.client.login(username='bob_rep', password='password123')
        self.assertEqual(self.client.get(reverse('report_panel', kwargs={'pk': self.panel_a1.id})).status_code, 403)
        self.assertEqual(self.client.get(reverse('report_installation', kwargs={'pk': self.inst_a.id})).status_code, 403)

        # 3. Ted (assigned tech) allowed for Installation A
        self.client.login(username='ted_rep_tech', password='password123')
        self.assertEqual(self.client.get(reverse('report_panel', kwargs={'pk': self.panel_a1.id})).status_code, 200)
        self.assertEqual(self.client.get(reverse('report_installation', kwargs={'pk': self.inst_a.id})).status_code, 200)

        # 4. Eve (unassigned tech) denied for Installation A -> 403
        self.client.login(username='eve_rep_tech', password='password123')
        self.assertEqual(self.client.get(reverse('report_panel', kwargs={'pk': self.panel_a1.id})).status_code, 403)
        self.assertEqual(self.client.get(reverse('report_installation', kwargs={'pk': self.inst_a.id})).status_code, 403)

        # 5. Dan (admin) allowed for any
        self.client.login(username='dan_rep_admin', password='password123')
        self.assertEqual(self.client.get(reverse('report_panel', kwargs={'pk': self.panel_a1.id})).status_code, 200)
        self.assertEqual(self.client.get(reverse('report_installation', kwargs={'pk': self.inst_b.id})).status_code, 200)

    def test_pdf_report_downloads(self):
        """Native PDF generation endpoints produce valid PDF streams without error."""
        self.client.login(username='alice_rep', password='password123')

        # 1. Panel PDF
        resp_p = self.client.get(f"{reverse('report_panel', kwargs={'pk': self.panel_a1.id})}?format=pdf")
        self.assertEqual(resp_p.status_code, 200)
        self.assertEqual(resp_p['Content-Type'], 'application/pdf')
        self.assertTrue(resp_p.content.startswith(b'%PDF'))

        # 2. Installation PDF
        resp_i = self.client.get(f"{reverse('report_installation', kwargs={'pk': self.inst_a.id})}?format=pdf")
        self.assertEqual(resp_i.status_code, 200)
        self.assertEqual(resp_i['Content-Type'], 'application/pdf')
        self.assertTrue(resp_i.content.startswith(b'%PDF'))

        # 3. Maintenance PDF
        resp_m = self.client.get(f"{reverse('report_maintenance')}?installation={self.inst_a.id}&format=pdf")
        self.assertEqual(resp_m.status_code, 200)
        self.assertEqual(resp_m['Content-Type'], 'application/pdf')
        self.assertTrue(resp_m.content.startswith(b'%PDF'))

    def test_protected_maintenance_photographs(self):
        """Maintenance supporting photographs are strictly protected by object-level authorization."""
        photo_url = reverse('secure_maintenance_photo', kwargs={'pk': self.issue_a.id})

        # Alice (owner customer) -> 200
        self.client.login(username='alice_rep', password='password123')
        self.assertEqual(self.client.get(photo_url).status_code, 200)

        # Ted (assigned tech) -> 200
        self.client.login(username='ted_rep_tech', password='password123')
        self.assertEqual(self.client.get(photo_url).status_code, 200)

        # Dan (admin) -> 200
        self.client.login(username='dan_rep_admin', password='password123')
        self.assertEqual(self.client.get(photo_url).status_code, 200)

        # Bob (other customer) -> 403 Forbidden!
        self.client.login(username='bob_rep', password='password123')
        self.assertEqual(self.client.get(photo_url).status_code, 403)

        # Eve (unassigned technician) -> 403 Forbidden!
        self.client.login(username='eve_rep_tech', password='password123')
        self.assertEqual(self.client.get(photo_url).status_code, 403)

    def test_empty_report_handling(self):
        """Empty reports render cleanly without 500 errors."""
        empty_inst = Installation.objects.create(
            name="Empty Sunnyvale Array",
            owner=self.alice,
            site_address="300 Empty Way"
        )
        self.client.login(username='alice_rep', password='password123')

        resp = self.client.get(reverse('report_installation', kwargs={'pk': empty_inst.id}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'No panels registered for this installation')

        resp_pdf = self.client.get(f"{reverse('report_installation', kwargs={'pk': empty_inst.id})}?format=pdf")
        self.assertEqual(resp_pdf.status_code, 200)
        self.assertTrue(resp_pdf.content.startswith(b'%PDF'))

    def test_technician_review_audit_accuracy(self):
        """Technician review findings remain distinct from raw AI model classifications."""
        self.client.login(username='alice_rep', password='password123')

        resp = self.client.get(reverse('report_panel', kwargs={'pk': self.panel_a1.id}))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Normal Surface Glass') # Verified finding
        self.assertContains(resp, 'Technician Verified')
        self.assertContains(resp, 'ted_rep_tech')

    def test_maintenance_history_report_accuracy(self):
        """Maintenance history report displays accurate scoped work order metrics."""
        self.client.login(username='alice_rep', password='password123')

        resp = self.client.get(f"{reverse('report_maintenance')}?installation={self.inst_a.id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['stats']['total'], 1)
        self.assertEqual(resp.context['stats']['resolved'], 1)
        self.assertContains(resp, 'Surface Dust Washing Order')
        self.assertContains(resp, 'ted_rep_tech')
        self.assertContains(resp, 'Panel surface washed with deionized water')

    def test_correct_latest_condition_calculations(self):
        """Latest visual condition is determined by most recent inspection, not altered by maintenance."""
        # Panel A1 latest inspection is 'Dusty' (2 days ago), older is 'Normal' (10 days ago)
        cond = self.panel_a1.get_derived_condition()
        self.assertEqual(cond['status'], 'dust')
        self.assertEqual(cond['label'], 'Cleaning May Be Needed')

        # Issue A is marked Resolved, but panel visual condition does NOT become 'normal'
        self.assertEqual(self.issue_a.status, 'Resolved')
        cond_after = self.panel_a1.get_derived_condition()
        self.assertEqual(cond_after['status'], 'dust')
        self.assertEqual(cond_after['label'], 'Cleaning May Be Needed')




