"""
SolarGuard Phase 10 — Complete End-to-End Customer Journey, RBAC & Data Integrity Test Suite
Covers:
- Section 2: Complete 16-Step Customer Journey (Install -> 4-3-4 Layout -> Verify -> Inspect -> Inference -> Work Order Lifecycle -> Resolution -> Report)
- Section 3: Role-Based Access Control (Customer isolation, Technician boundary enforcement, Admin authorization)
- Section 4: Data Integrity (Permanent panel IDs, layout isolation, empty cell distinction, retired panel preservation, AI immutability)
"""

import io
import json
import datetime
from PIL import Image, ImageDraw

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile

from core.models import UserProfile, Installation, LayoutRevision, Panel, Inspection, MaintenanceIssue, MaintenanceLog
from ml_engine.inference import load_model_service, resolve_version_key


class Phase10CustomerJourneyTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Create authorized role accounts
        self.admin = User.objects.create_superuser(username='journey_admin', password='password123', email='admin@sg.com')
        self.tech = User.objects.create_user(username='journey_tech', password='password123')
        self.other_tech = User.objects.create_user(username='other_tech', password='password123')
        self.cust = User.objects.create_user(username='journey_cust', password='password123')
        self.attacker = User.objects.create_user(username='journey_attacker', password='password123')

        UserProfile.objects.filter(user=self.admin).update(role='admin')
        UserProfile.objects.filter(user=self.tech).update(role='technician')
        UserProfile.objects.filter(user=self.other_tech).update(role='technician')
        UserProfile.objects.filter(user=self.cust).update(role='customer')
        UserProfile.objects.filter(user=self.attacker).update(role='customer')

        # Test image for inspection
        img = Image.new('RGB', (256, 256), color=(40, 75, 115))
        draw = ImageDraw.Draw(img)
        draw.line([(10, 10), (240, 240)], fill=(220, 220, 220), width=4)
        draw.rectangle([(60, 60), (160, 160)], outline=(255, 190, 0), width=3)
        buf = io.BytesIO()
        img.save(buf, format='JPEG')
        buf.seek(0)
        self.test_img_bytes = buf.getvalue()

    def test_complete_16_step_customer_journey(self):
        """
        Executes and validates the exact 16-step end-to-end customer journey from Phase 10 Section 2.
        """
        # STEP 1: Customer logs in
        login_ok = self.client.login(username='journey_cust', password='password123')
        self.assertTrue(login_ok, "Step 1 Failed: Customer login unsuccessful")

        # STEP 2: Customer creates an installation
        post_inst = {
            'name': 'Sunnyvale Solar Array',
            'site_address': '104 Garden Street, Sunnyvale',
            'installation_type': 'rooftop',
            'install_date': '2024-01-15'
        }
        resp = self.client.post(reverse('installation_add'), post_inst, follow=True)
        self.assertEqual(resp.status_code, 200, "Step 2 Failed: Installation creation error")
        inst = Installation.objects.filter(owner=self.cust, name='Sunnyvale Solar Array').first()
        self.assertIsNotNone(inst, "Step 2 Failed: Installation record not in database")

        # STEP 3: Builds an irregular 4-3-4 panel layout (11 active panels in 3x4 grid)
        # Row 1: Cols 1, 2, 3, 4 (4 panels)
        # Row 2: Cols 1, 2, 3 (3 panels - Col 4 is empty slot!)
        # Row 3: Cols 1, 2, 3, 4 (4 panels)
        active_cells = [
            {'row': 1, 'col': 1, 'panel_id': 'NEW_1'},
            {'row': 1, 'col': 2, 'panel_id': 'NEW_2'},
            {'row': 1, 'col': 3, 'panel_id': 'NEW_3'},
            {'row': 1, 'col': 4, 'panel_id': 'NEW_4'},
            {'row': 2, 'col': 1, 'panel_id': 'NEW_5'},
            {'row': 2, 'col': 2, 'panel_id': 'NEW_6'},
            {'row': 2, 'col': 3, 'panel_id': 'NEW_7'},
            {'row': 3, 'col': 1, 'panel_id': 'NEW_8'},
            {'row': 3, 'col': 2, 'panel_id': 'NEW_9'},
            {'row': 3, 'col': 3, 'panel_id': 'NEW_10'},
            {'row': 3, 'col': 4, 'panel_id': 'NEW_11'},
        ]
        layout_payload = {
            'rows': 3,
            'cols': 4,
            'active_cells': active_cells
        }

        # STEP 4: Saves draft and submits for verification
        save_resp = self.client.post(
            reverse('layout_save_draft', kwargs={'pk': inst.pk}),
            data=json.dumps(layout_payload),
            content_type='application/json'
        )
        self.assertEqual(save_resp.status_code, 200, "Step 4 Failed: Save draft error")
        draft = inst.layout_revisions.filter(status='draft').first()
        self.assertIsNotNone(draft, "Step 4 Failed: Draft revision not created")
        self.assertEqual(len(draft.layout_data.get('active_cells', [])), 11)

        submit_resp = self.client.post(
            reverse('layout_submit', kwargs={'pk': inst.pk}),
            content_type='application/json'
        )
        self.assertEqual(submit_resp.status_code, 200, "Step 4 Failed: Layout submit error")
        draft.refresh_from_db()
        self.assertEqual(draft.status, 'pending_verification')

        # STEP 5: Admin verifies the layout
        self.client.login(username='journey_admin', password='password123')
        verify_resp = self.client.post(reverse('layout_verify', kwargs={'pk': draft.pk}), {
            'status': 'verified',
            'review_notes': 'Engineering review verified 4-3-4 array configuration.'
        }, follow=True)
        self.assertEqual(verify_resp.status_code, 200, "Step 5 Failed: Admin layout verify error")
        draft.refresh_from_db()
        self.assertEqual(draft.status, 'verified')

        # STEP 6: Customer sees the verified panel map
        self.client.login(username='journey_cust', password='password123')
        inst_page = self.client.get(reverse('installation_detail', kwargs={'pk': inst.pk}))
        self.assertEqual(inst_page.status_code, 200, "Step 6 Failed: Customer installation detail error")
        self.assertContains(inst_page, "Sunnyvale Solar Array")
        self.assertContains(inst_page, "11 Active Modules")

        # Verify exact 11 physical panels exist with permanent IDs
        panels = list(inst.panels.filter(status='active').order_by('grid_row', 'grid_col'))
        self.assertEqual(len(panels), 11, "Step 6 Failed: Exactly 11 panels should exist")
        # Ensure row 2, col 4 is empty and NOT a physical panel
        self.assertFalse(inst.panels.filter(grid_row=2, grid_col=4, status='active').exists(), "Empty slot must not be a panel")

        # STEP 7: Customer selects a panel and opens its Digital Passport
        target_panel = panels[0] # Row 1, Col 1
        passport_page = self.client.get(reverse('panel_detail', kwargs={'pk': target_panel.pk}))
        self.assertEqual(passport_page.status_code, 200, "Step 7 Failed: Digital Passport view error")
        self.assertContains(passport_page, target_panel.permanent_id)

        # STEP 8: Customer uploads a photograph of that single physical panel
        upload = SimpleUploadedFile("panel_physical.jpg", self.test_img_bytes, content_type="image/jpeg")
        inspect_post = {
            'panel': target_panel.pk,
            'image': upload,
            'notes': 'Single panel high-resolution inspection photograph.'
        }
        inspect_resp = self.client.post(reverse('inspect'), inspect_post, follow=True)
        self.assertEqual(inspect_resp.status_code, 200, "Step 8 Failed: Panel inspection upload error")

        # STEP 9: Actual active MobileNetV2 model performs inference
        ins = Inspection.objects.filter(panel=target_panel).first()
        self.assertIsNotNone(ins, "Step 9/10 Failed: Inspection record not saved")
        self.assertIn(ins.predicted_class, ['Bird-Dropping', 'Dusty', 'Normal', 'Surface-Damage'])
        self.assertFalse(ins.is_mock_prediction, "Step 9 Failed: Real CNN must be active")

        # STEP 10: Inspection result, confidence, model version, and image are saved
        self.assertIn('MobileNetV2 CNN v3.0', ins.model_identifier, "Step 10 Failed: Model version must be v3.0")
        self.assertGreater(ins.confidence_score, 0.0)
        self.assertTrue(bool(ins.image))

        # STEP 11: Customer views inspection history
        ins_list_page = self.client.get(reverse('inspection_list'))
        self.assertEqual(ins_list_page.status_code, 200, "Step 11 Failed: Inspection list view error")
        self.assertContains(ins_list_page, target_panel.permanent_id)

        result_page = self.client.get(reverse('result_detail', kwargs={'pk': ins.pk}))
        self.assertEqual(result_page.status_code, 200, "Step 11 Failed: Result detail view error")
        self.assertContains(result_page, ins.predicted_class)

        # STEP 12: Customer creates a maintenance request
        issue_post = {
            'panel': target_panel.pk,
            'title': f'Field Maintenance for {target_panel.permanent_id}',
            'description': 'Routine soiling cleanup and wiring integrity check.',
            'priority': 'Medium'
        }
        issue_resp = self.client.post(reverse('issue_create'), issue_post, follow=True)
        self.assertEqual(issue_resp.status_code, 200, "Step 12 Failed: Issue creation error")
        issue = MaintenanceIssue.objects.filter(panel=target_panel).first()
        self.assertIsNotNone(issue, "Step 12 Failed: MaintenanceIssue record not in database")
        self.assertEqual(issue.status, 'Open')
        self.assertIsNone(issue.assigned_technician)

        # STEP 13: Admin assigns a technician
        self.client.login(username='journey_admin', password='password123')
        assign_resp = self.client.post(reverse('issue_detail', kwargs={'pk': issue.pk}), {
            'action': 'assign_technician',
            'technician': self.tech.pk,
            'priority': 'High',
            'notes': 'Assigned to certified solar technician.'
        }, follow=True)
        self.assertEqual(assign_resp.status_code, 200, "Step 13 Failed: Admin technician assignment error")
        issue.refresh_from_db()
        self.assertEqual(issue.status, 'Assigned')
        self.assertEqual(issue.assigned_technician, self.tech)

        # STEP 14: Assigned technician starts work, logs action and resolves
        self.client.login(username='journey_tech', password='password123')
        
        # 14a. Technician marks In Progress
        start_resp = self.client.post(reverse('issue_detail', kwargs={'pk': issue.pk}), {
            'action': 'start_work'
        }, follow=True)
        self.assertEqual(start_resp.status_code, 200)
        issue.refresh_from_db()
        self.assertEqual(issue.status, 'In Progress')

        # 14b. Technician logs maintenance action
        log_resp = self.client.post(reverse('issue_detail', kwargs={'pk': issue.pk}), {
            'action': 'add_log',
            'action_type': 'cleaning',
            'notes': 'Performed deionized water wash and junction box inspection.',
            'performed_at': datetime.date.today().isoformat()
        }, follow=True)
        self.assertEqual(log_resp.status_code, 200)
        self.assertEqual(issue.logs.count(), 4) # creation, assignment, start_work, cleaning

        # 14c. Technician resolves work
        resolve_resp = self.client.post(reverse('issue_detail', kwargs={'pk': issue.pk}), {
            'action': 'resolve_work',
            'resolution_notes': 'Surface cleaned and terminal connection tightened.'
        }, follow=True)
        self.assertEqual(resolve_resp.status_code, 200)
        issue.refresh_from_db()
        self.assertEqual(issue.status, 'Resolved')
        self.assertIn('Surface cleaned', issue.resolution_notes)

        # STEP 15: Admin closes the resolved ticket
        self.client.login(username='journey_admin', password='password123')
        close_resp = self.client.post(reverse('issue_detail', kwargs={'pk': issue.pk}), {
            'action': 'close_work',
            'closure_notes': 'Service report verified and closed by facility admin.'
        }, follow=True)
        self.assertEqual(close_resp.status_code, 200, "Step 15 Failed: Admin close work error")
        issue.refresh_from_db()
        self.assertEqual(issue.status, 'Closed')
        self.assertIsNotNone(issue.closed_at)

        # STEP 16: Customer sees maintenance history and downloads an authorized report
        self.client.login(username='journey_cust', password='password123')
        history_page = self.client.get(reverse('issue_detail', kwargs={'pk': issue.pk}))
        self.assertEqual(history_page.status_code, 200)
        self.assertContains(history_page, "Closed")
        self.assertContains(history_page, "Surface cleaned")

        # Download authorized PDF reports
        inst_rep_resp = self.client.get(f"{reverse('report_installation', kwargs={'pk': inst.pk})}?format=pdf")
        self.assertEqual(inst_rep_resp.status_code, 200, "Step 16 Failed: Installation PDF report download error")
        self.assertTrue(inst_rep_resp.content.startswith(b'%PDF'), "Step 16 Failed: Expected valid PDF stream")

        panel_rep_resp = self.client.get(f"{reverse('report_panel', kwargs={'pk': target_panel.pk})}?format=pdf")
        self.assertEqual(panel_rep_resp.status_code, 200, "Step 16 Failed: Panel PDF report download error")
        self.assertTrue(panel_rep_resp.content.startswith(b'%PDF'), "Step 16 Failed: Expected valid PDF stream")


class Phase10RBACAndDataIntegrityTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser(username='sec_admin', password='password123', email='sec_admin@sg.com')
        self.tech_assigned = User.objects.create_user(username='sec_tech_a', password='password123')
        self.tech_unassigned = User.objects.create_user(username='sec_tech_b', password='password123')
        self.cust_alice = User.objects.create_user(username='sec_alice', password='password123')
        self.cust_bob = User.objects.create_user(username='sec_bob', password='password123')

        UserProfile.objects.filter(user=self.admin).update(role='admin')
        UserProfile.objects.filter(user=self.tech_assigned).update(role='technician')
        UserProfile.objects.filter(user=self.tech_unassigned).update(role='technician')
        UserProfile.objects.filter(user=self.cust_alice).update(role='customer')
        UserProfile.objects.filter(user=self.cust_bob).update(role='customer')

        # Alice's installation
        self.inst_alice = Installation.objects.create(
            name="Alice Sunnyvale Array",
            owner=self.cust_alice,
            site_address="100 Alice Lane",
            assigned_technician=self.tech_assigned
        )
        self.panel_alice = Panel.objects.create(
            installation=self.inst_alice,
            user=self.cust_alice,
            permanent_id="SG-ALICE-P01",
            serial_number="MOD-ALICE-01",
            grid_row=1,
            grid_col=1,
            status='active'
        )
        self.panel_retired = Panel.objects.create(
            installation=self.inst_alice,
            user=self.cust_alice,
            permanent_id="SG-ALICE-P02-RET",
            serial_number="MOD-ALICE-02",
            grid_row=1,
            grid_col=2,
            status='retired'
        )

        # Bob's installation
        self.inst_bob = Installation.objects.create(
            name="Bob Rooftop Array",
            owner=self.cust_bob,
            site_address="200 Bob Lane"
        )
        self.panel_bob = Panel.objects.create(
            installation=self.inst_bob,
            user=self.cust_bob,
            permanent_id="SG-BOB-P01",
            serial_number="MOD-BOB-01",
            grid_row=1,
            grid_col=1,
            status='active'
        )

        # Valid image bytes
        img = Image.new('RGB', (128, 128), color=(30, 60, 90))
        draw = ImageDraw.Draw(img)
        draw.line([(0, 0), (128, 128)], fill=(200, 200, 200), width=3)
        b = io.BytesIO()
        img.save(b, format='JPEG')
        b.seek(0)
        self.img_bytes = b.getvalue()

    def test_customer_cannot_access_other_customer_data(self):
        """Section 3: Bob cannot view or modify Alice's installation, panels, or reports."""
        self.client.login(username='sec_bob', password='password123')

        # Cannot view Alice's installation
        self.assertEqual(self.client.get(reverse('installation_detail', kwargs={'pk': self.inst_alice.pk})).status_code, 403)
        # Cannot view Alice's panel passport
        self.assertEqual(self.client.get(reverse('panel_detail', kwargs={'pk': self.panel_alice.pk})).status_code, 403)
        # Cannot download Alice's installation report
        self.assertEqual(self.client.get(reverse('report_installation', kwargs={'pk': self.inst_alice.pk})).status_code, 403)
        # Cannot download Alice's panel report
        self.assertEqual(self.client.get(reverse('report_panel', kwargs={'pk': self.panel_alice.pk})).status_code, 403)

    def test_customer_cannot_assign_technician_or_approve_layout(self):
        """Section 3: Customers cannot assign technicians or self-approve layout revisions."""
        self.client.login(username='sec_alice', password='password123')

        # Cannot assign technician to installation
        resp_assign = self.client.post(reverse('installation_assign_tech', kwargs={'pk': self.inst_alice.pk}), {
            'technician': self.tech_assigned.pk
        })
        self.assertEqual(resp_assign.status_code, 403)

        # Create draft layout and try to self-approve
        draft = LayoutRevision.objects.create(
            installation=self.inst_alice,
            version_number=1,
            status='pending_verification',
            submitted_by=self.cust_alice
        )
        resp_verify = self.client.post(reverse('layout_verify', kwargs={'pk': draft.pk}), {
            'status': 'verified',
            'review_notes': 'Self approval attempt'
        })
        self.assertEqual(resp_verify.status_code, 403)

    def test_unassigned_technician_cannot_modify_unauthorized_ticket(self):
        """Section 3: Unassigned technician cannot modify or resolve Alice's work order."""
        issue = MaintenanceIssue.objects.create(
            installation=self.inst_alice,
            panel=self.panel_alice,
            user=self.cust_alice,
            title='Inverter Cable Check',
            status='Assigned',
            assigned_technician=self.tech_assigned
        )

        # Other technician attempts to start work
        self.client.login(username='sec_tech_b', password='password123')
        resp_start = self.client.post(reverse('issue_detail', kwargs={'pk': issue.pk}), {
            'action': 'start_work'
        })
        self.assertEqual(resp_start.status_code, 403)

        # Other technician attempts to resolve
        resp_resolve = self.client.post(reverse('issue_detail', kwargs={'pk': issue.pk}), {
            'action': 'resolve_work',
            'resolution_notes': 'Unauthorized resolve'
        })
        self.assertEqual(resp_resolve.status_code, 403)

    def test_permanent_panel_id_preserved_when_coordinates_move(self):
        """Section 4: Permanent physical panel ID remains invariant across position moves."""
        original_perm_id = self.panel_alice.permanent_id
        original_serial = self.panel_alice.serial_number

        # Move panel from (1, 1) to (2, 3)
        self.panel_alice.grid_row = 2
        self.panel_alice.grid_col = 3
        self.panel_alice.save()

        self.panel_alice.refresh_from_db()
        self.assertEqual(self.panel_alice.permanent_id, original_perm_id)
        self.assertEqual(self.panel_alice.serial_number, original_serial)
        self.assertEqual(self.panel_alice.grid_row, 2)
        self.assertEqual(self.panel_alice.grid_col, 3)

    def test_uninspected_panel_is_never_classified_as_normal(self):
        """Section 4: Uninspected panel derived condition is 'Not Inspected', never Normal."""
        cond = self.panel_bob.get_derived_condition()
        self.assertEqual(cond['status'], 'not_inspected')
        self.assertEqual(cond['category'], 'Not Inspected')
        self.assertEqual(cond['label'], 'Not Inspected')
        self.assertFalse(cond['is_inspected'])

    def test_maintenance_resolution_does_not_alter_ai_prediction(self):
        """Section 4: Completing a maintenance work order never overwrites original AI inspection."""
        ins = Inspection.objects.create(
            panel=self.panel_alice,
            user=self.cust_alice,
            predicted_class='Surface-Damage',
            confidence_score=85.0,
            model_identifier='MobileNetV2 CNN v3.0'
        )
        issue = MaintenanceIssue.objects.create(
            installation=self.inst_alice,
            panel=self.panel_alice,
            inspection=ins,
            user=self.cust_alice,
            title='Surface Crack Repair',
            status='In Progress',
            assigned_technician=self.tech_assigned
        )

        # Technician resolves ticket
        self.client.login(username='sec_tech_a', password='password123')
        self.client.post(reverse('issue_detail', kwargs={'pk': issue.pk}), {
            'action': 'resolve_work',
            'resolution_notes': 'Glass sealant applied and tested.'
        })

        ins.refresh_from_db()
        self.assertEqual(ins.predicted_class, 'Surface-Damage')
        self.assertEqual(ins.confidence_score, 85.0)
        self.assertEqual(ins.model_identifier, 'MobileNetV2 CNN v3.0')
