"""
SolarGuard — Safe Idempotent Demo Data Seeding Command
SEPM Project SolarGuard (Phase 10 Demo Readiness)

Creates a realistic, showcase-ready demo environment for client, evaluator,
and stakeholder presentations without destroying or altering existing user records.

Features:
- Idempotent: Checks existence before creating; safe to run multiple times.
- Non-destructive: Never deletes or resets existing installations, panels, or users.
- Role-complete: Prepares Customer, Certified Technician, and Facility Administrator accounts.
- Realistic scenario: 4-3-4 irregular array (11 panels) with verified layout, historical
  inspections across classes, and maintenance work orders across all lifecycle states.
"""

import datetime
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from core.models import (
    UserProfile,
    Installation,
    Panel,
    Inspection,
    MaintenanceIssue,
    MaintenanceLog,
    LayoutRevision,
)


class Command(BaseCommand):
    help = "Seeds idempotent demo data for SolarGuard evaluation without modifying existing data."

    def add_arguments(self, parser):
        parser.add_argument(
            '--password',
            type=str,
            default='SolarGuard2026!',
            help="Default password for newly created demo accounts (default: SolarGuard2026!)"
        )
        parser.add_argument(
            '--force-password-reset',
            action='store_true',
            help="Reset passwords of existing demo users to the specified demo password."
        )

    def handle(self, *args, **options):
        demo_pwd = options['password']
        reset_pwd = options['force_password_reset']

        self.stdout.write(self.style.MIGRATE_HEADING("=" * 72))
        self.stdout.write(self.style.MIGRATE_HEADING(" SolarGuard Phase 10 — Idempotent Demo Data Seeding"))
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 72))

        # -----------------------------------------------------------------
        # 1. Demo User Accounts
        # -----------------------------------------------------------------
        accounts = [
            {
                'username': 'demo_customer',
                'email': 'customer@solarguard.demo',
                'role': 'customer',
                'first_name': 'Eleanor',
                'last_name': 'Vance',
                'is_staff': False,
                'is_superuser': False,
            },
            {
                'username': 'demo_tech',
                'email': 'technician@solarguard.demo',
                'role': 'technician',
                'first_name': 'Marcus',
                'last_name': 'Holloway',
                'is_staff': False,
                'is_superuser': False,
            },
            {
                'username': 'demo_admin',
                'email': 'admin@solarguard.demo',
                'role': 'admin',
                'first_name': 'Sarah',
                'last_name': 'Chen',
                'is_staff': True,
                'is_superuser': True,
            },
        ]

        created_users = {}
        for acc in accounts:
            user, created = User.objects.get_or_create(
                username=acc['username'],
                defaults={
                    'email': acc['email'],
                    'first_name': acc['first_name'],
                    'last_name': acc['last_name'],
                    'is_staff': acc['is_staff'],
                    'is_superuser': acc['is_superuser'],
                }
            )
            if created or reset_pwd:
                user.set_password(demo_pwd)
                user.save()
                pwd_status = "(password set)"
            else:
                pwd_status = "(existing password retained)"

            profile, _ = UserProfile.objects.get_or_create(user=user)
            if profile.role != acc['role']:
                profile.role = acc['role']
                profile.save()

            created_users[acc['username']] = user
            state_str = "Created" if created else "Verified"
            self.stdout.write(f"  [{state_str}] User: {user.username:15} | Role: {acc['role']:10} {pwd_status}")

        cust = created_users['demo_customer']
        tech = created_users['demo_tech']
        admin = created_users['demo_admin']

        # -----------------------------------------------------------------
        # 2. Demo Installation (Apex Commercial Solar Park)
        # -----------------------------------------------------------------
        inst_name = "Apex Commercial SunPark — Unit 4"
        installation, inst_created = Installation.objects.get_or_create(
            name=inst_name,
            owner=cust,
            defaults={
                'installation_type': 'commercial',
                'site_address': '100 Solar Way, Silicon Valley Campus, CA 94086',
                'install_date': datetime.date(2025, 4, 15),
                'assigned_technician': tech,
                'status': 'active',
            }
        )
        if not inst_created and installation.assigned_technician != tech:
            installation.assigned_technician = tech
            installation.save()

        inst_status = "Created" if inst_created else "Verified"
        self.stdout.write(f"  [{inst_status}] Installation: '{installation.name}' (ID: #{installation.id})")

        # -----------------------------------------------------------------
        # 3. Verified Layout Revision & 11 Physical Panels (4-3-4 Array)
        # -----------------------------------------------------------------
        # Irregular 4-3-4 structure:
        # Row 1: 4 panels (cols 1, 2, 3, 4)
        # Row 2: 3 panels (cols 1, 2, 3) -> col 4 is EMPTY SLOT
        # Row 3: 4 panels (cols 1, 2, 3, 4)
        # Total = 11 modules
        layout_cells = [
            {'row': 1, 'col': 1, 'panel_id': 'APEX-P001'},
            {'row': 1, 'col': 2, 'panel_id': 'APEX-P002'},
            {'row': 1, 'col': 3, 'panel_id': 'APEX-P003'},
            {'row': 1, 'col': 4, 'panel_id': 'APEX-P004'},
            {'row': 2, 'col': 1, 'panel_id': 'APEX-P005'},
            {'row': 2, 'col': 2, 'panel_id': 'APEX-P006'},
            {'row': 2, 'col': 3, 'panel_id': 'APEX-P007'},
            # Row 2, Col 4 is purposefully empty
            {'row': 3, 'col': 1, 'panel_id': 'APEX-P008'},
            {'row': 3, 'col': 2, 'panel_id': 'APEX-P009'},
            {'row': 3, 'col': 3, 'panel_id': 'APEX-P010'},
            {'row': 3, 'col': 4, 'panel_id': 'APEX-P011'},
        ]

        revision, rev_created = LayoutRevision.objects.get_or_create(
            installation=installation,
            version_number=1,
            defaults={
                'status': 'verified',
                'grid_rows': 3,
                'grid_cols': 4,
                'submitted_by': cust,
                'reviewed_by': admin,
                'reviewed_at': timezone.now(),
                'review_notes': 'Demo initial layout verified with 4-3-4 irregular array and unobstructed inverter access corridor.',
                'layout_data': {
                    'grid_rows': 3,
                    'grid_cols': 4,
                    'active_cells': layout_cells,
                }
            }
        )
        rev_status = "Created" if rev_created else "Verified"
        self.stdout.write(f"  [{rev_status}] Layout Revision: Rev #{revision.version_number} (Status: {revision.status})")

        # Create/verify 11 physical panels
        panel_records = {}
        for cell in layout_cells:
            r = cell['row']
            c = cell['col']
            pid = cell['panel_id']
            serial = f"SN-{pid}-2026"
            panel, p_created = Panel.objects.get_or_create(
                serial_number=serial,
                defaults={
                    'installation': installation,
                    'permanent_id': pid,
                    'grid_row': r,
                    'grid_col': c,
                    'user': cust,
                    'site_location': installation.name,
                    'status': 'active',
                    'install_date': datetime.date(2025, 4, 15),
                    'panel_specs': {
                        'manufacturer': 'SunPower Maxeon',
                        'model_number': 'SPR-MAX3-400',
                        'wattage': 400.0,
                    }
                }
            )
            # Ensure installation and coordinates are aligned
            if panel.installation != installation or panel.grid_row != r or panel.grid_col != c or panel.permanent_id != pid:
                panel.installation = installation
                panel.grid_row = r
                panel.grid_col = c
                panel.permanent_id = pid
                panel.save()
            panel_records[pid] = panel

        self.stdout.write(f"  [Verified] Panels: {len(panel_records)} physical modules mapped (Row 2, Col 4 correctly unoccupied)")

        # -----------------------------------------------------------------
        # 4. Realistic Inspections with Diverse Classifications
        # -----------------------------------------------------------------
        v3_id_str = "MobileNetV2 CNN v3.0"

        # P001: Verified Normal
        p1 = panel_records['APEX-P001']
        insp1, i1_created = Inspection.objects.get_or_create(
            panel=p1,
            notes='Quarterly drone RGB survey — optimal irradiance',
            defaults={
                'user': cust,
                'predicted_class': 'Normal',
                'confidence_score': 96.42,
                'degradation_probability': 3.5,
                'risk_category': 'Low',
                'maintenance_priority_score': 10,
                'maintenance_priority_level': 'Low',
                'is_mock_prediction': False,
                'model_identifier': v3_id_str,
                'class_probabilities': {'Normal': 96.42, 'Dusty': 2.10, 'Bird-Dropping': 0.90, 'Physical-Damage': 0.58},
                'review_status': 'technician_verified',
                'reviewed_by': tech,
                'reviewed_at': timezone.now() - datetime.timedelta(days=12),
                'verified_outcome': 'Normal',
                'review_notes': 'Verified pristine anti-reflective coating.',
            }
        )

        # P002: Verified Dusty
        p2 = panel_records['APEX-P002']
        insp2, i2_created = Inspection.objects.get_or_create(
            panel=p2,
            notes='Heavy agricultural airborne dust accumulation',
            defaults={
                'user': cust,
                'predicted_class': 'Dusty',
                'confidence_score': 91.85,
                'degradation_probability': 18.2,
                'risk_category': 'Medium',
                'maintenance_priority_score': 45,
                'maintenance_priority_level': 'Medium',
                'is_mock_prediction': False,
                'model_identifier': v3_id_str,
                'class_probabilities': {'Dusty': 91.85, 'Normal': 4.10, 'Bird-Dropping': 2.50, 'Physical-Damage': 1.55},
                'review_status': 'technician_verified',
                'reviewed_by': tech,
                'reviewed_at': timezone.now() - datetime.timedelta(days=5),
                'verified_outcome': 'Dusty',
                'review_notes': 'Confirmed moderate particulate soiling. Scheduled for automated pressure wash.',
            }
        )

        # P003: Verified Bird-Dropping (Resolved History)
        p3 = panel_records['APEX-P003']
        insp3, i3_created = Inspection.objects.get_or_create(
            panel=p3,
            notes='Local avian fouling hotspot near rooftop parapet',
            defaults={
                'user': cust,
                'predicted_class': 'Bird-Dropping',
                'confidence_score': 88.30,
                'degradation_probability': 32.0,
                'risk_category': 'Medium',
                'maintenance_priority_score': 60,
                'maintenance_priority_level': 'Medium',
                'is_mock_prediction': False,
                'model_identifier': v3_id_str,
                'class_probabilities': {'Bird-Dropping': 88.30, 'Dusty': 6.50, 'Normal': 3.20, 'Physical-Damage': 2.00},
                'review_status': 'technician_verified',
                'reviewed_by': tech,
                'reviewed_at': timezone.now() - datetime.timedelta(days=20),
                'verified_outcome': 'Bird-Dropping',
                'review_notes': 'Fouling confirmed. Hotspot risk mitigation required.',
            }
        )

        # P004: Physical Damage (Awaiting Review)
        p4 = panel_records['APEX-P004']
        insp4, i4_created = Inspection.objects.get_or_create(
            panel=p4,
            notes='Suspected surface fracture from storm event',
            defaults={
                'user': cust,
                'predicted_class': 'Physical-Damage',
                'confidence_score': 87.15,
                'degradation_probability': 68.0,
                'risk_category': 'High',
                'maintenance_priority_score': 85,
                'maintenance_priority_level': 'High',
                'is_mock_prediction': False,
                'model_identifier': v3_id_str,
                'class_probabilities': {'Physical-Damage': 87.15, 'Bird-Dropping': 5.20, 'Dusty': 4.10, 'Normal': 3.55},
                'review_status': 'ai_predicted',
                'reviewed_by': None,
                'verified_outcome': '',
                'review_notes': '',
            }
        )

        self.stdout.write(f"  [Verified] Inspections: 4 realistic inspections recorded across all primary classes.")

        # -----------------------------------------------------------------
        # 5. Work Orders Across Full Lifecycle States
        # -----------------------------------------------------------------
        # Ticket 1: Closed Ticket (Panel P003 Bird-Dropping)
        issue1, is1_created = MaintenanceIssue.objects.get_or_create(
            panel=p3,
            title='Avian Fouling Decontamination & Verification',
            defaults={
                'installation': installation,
                'user': cust,
                'inspection': insp3,
                'priority': 'Medium',
                'status': 'Closed',
                'description': 'Heavy localized fouling causing hotspot mismatch. Requires specialized deionized detergent cleaning.',
                'assigned_technician': tech,
                'resolution_notes': 'Targeted soft-bristle scrub with DI water completed. Full optical transmittance restored.',
                'closed_at': timezone.now() - datetime.timedelta(days=18),
            }
        )
        if is1_created:
            MaintenanceLog.objects.create(
                panel=p3, issue=issue1, user=cust, action_type='creation',
                notes=f"Work order #{issue1.id} initiated by customer Eleanor Vance."
            )
            MaintenanceLog.objects.create(
                panel=p3, issue=issue1, user=admin, action_type='assignment',
                previous_status='Open', new_status='Assigned', technician=tech,
                notes=f"Assigned to certified technician Marcus Holloway."
            )
            MaintenanceLog.objects.create(
                panel=p3, issue=issue1, user=tech, action_type='status_change',
                previous_status='Assigned', new_status='In Progress', technician=tech,
                notes="Technician arrived on site with DI cleaning rig."
            )
            MaintenanceLog.objects.create(
                panel=p3, issue=issue1, user=tech, action_type='cleaning',
                notes="Completed neutral pH detergent wash and rinse.",
                performed_at=datetime.date.today() - datetime.timedelta(days=19)
            )
            MaintenanceLog.objects.create(
                panel=p3, issue=issue1, user=tech, action_type='resolution',
                previous_status='In Progress', new_status='Resolved', technician=tech,
                notes=issue1.resolution_notes
            )
            MaintenanceLog.objects.create(
                panel=p3, issue=issue1, user=admin, action_type='closure',
                previous_status='Resolved', new_status='Closed',
                notes="Post-maintenance inspection verified clean surface. Ticket closed."
            )

        # Ticket 2: In Progress Ticket (Panel P002 Heavy Soiling)
        issue2, is2_created = MaintenanceIssue.objects.get_or_create(
            panel=p2,
            title='Array Section 1 Dust Wash & Inverter Check',
            defaults={
                'installation': installation,
                'user': cust,
                'inspection': insp2,
                'priority': 'Low',
                'status': 'In Progress',
                'description': 'Uniform particulate soiling across panel glass. Clean according to IEC-61215 guidelines.',
                'assigned_technician': tech,
            }
        )
        if is2_created:
            MaintenanceLog.objects.create(
                panel=p2, issue=issue2, user=cust, action_type='creation',
                notes=f"Work order #{issue2.id} created."
            )
            MaintenanceLog.objects.create(
                panel=p2, issue=issue2, user=admin, action_type='assignment',
                previous_status='Open', new_status='Assigned', technician=tech,
                notes=f"Assigned to {tech.username}."
            )
            MaintenanceLog.objects.create(
                panel=p2, issue=issue2, user=tech, action_type='status_change',
                previous_status='Assigned', new_status='In Progress', technician=tech,
                notes="Technician initiated wash schedule."
            )

        # Ticket 3: Assigned Ticket (Panel P004 Micro-crack)
        issue3, is3_created = MaintenanceIssue.objects.get_or_create(
            panel=p4,
            title='Hail Impact Fracture Evaluation & Thermography',
            defaults={
                'installation': installation,
                'user': cust,
                'inspection': insp4,
                'priority': 'High',
                'status': 'Assigned',
                'description': 'AI model flagged potential surface damage. Requires electroluminescence / thermal drone validation.',
                'assigned_technician': tech,
            }
        )
        if is3_created:
            MaintenanceLog.objects.create(
                panel=p4, issue=issue3, user=cust, action_type='creation',
                notes=f"Work order #{issue3.id} submitted for suspected crack."
            )
            MaintenanceLog.objects.create(
                panel=p4, issue=issue3, user=admin, action_type='assignment',
                previous_status='Open', new_status='Assigned', technician=tech,
                notes=f"Prioritized high by administrator Sarah Chen."
            )

        # Ticket 4: Open Ticket (Unassigned Demo for Admin Assignment)
        p5 = panel_records['APEX-P005']
        issue4, is4_created = MaintenanceIssue.objects.get_or_create(
            panel=p5,
            title='Inverter Cable Terminal Inspection',
            defaults={
                'installation': installation,
                'user': cust,
                'priority': 'High',
                'status': 'Open',
                'description': 'MC4 connector thermal discoloration flagged during visual inspection. Awaiting technician assignment.',
                'assigned_technician': None,
            }
        )
        if is4_created:
            MaintenanceLog.objects.create(
                panel=p5, issue=issue4, user=cust, action_type='creation',
                notes=f"Emergency work order #{issue4.id} created by customer. Unassigned."
            )

        self.stdout.write(f"  [Verified] Work Orders: 4 lifecycle tickets ready (Open, Assigned, In Progress, Closed).")

        # -----------------------------------------------------------------
        # 6. Summary Presentation
        # -----------------------------------------------------------------
        self.stdout.write(self.style.SUCCESS("\n" + "=" * 72))
        self.stdout.write(self.style.SUCCESS(" SolarGuard Demo Environment Successfully Prepared!"))
        self.stdout.write(self.style.SUCCESS("=" * 72))
        self.stdout.write(f"""
  DEMO CREDENTIALS:
  --------------------------------------------------------------------------
  Role                 Username          Password          Portal Access
  --------------------------------------------------------------------------
  Customer             demo_customer     {demo_pwd:<17} /
  NABCEP Technician    demo_tech         {demo_pwd:<17} /
  Facility Admin       demo_admin        {demo_pwd:<17} / & /admin/
  --------------------------------------------------------------------------

  SHOWCASE HIGHLIGHTS:
  - Array: Apex Commercial SunPark (ID: #{installation.id})
  - 11 Physical Modules (SunPower SPR-MAX3-400) in 4-3-4 layout
  - Unoccupied Cell: Row 2, Col 4 correctly displayed as empty slot
  - Inspections across Normal, Dusty, Bird-Dropping, and Physical Damage
  - Work Order Lifecycle: Open (#4), Assigned (#3), In Progress (#2), Closed (#1)
  - PDF & Print Reports ready at /reports/
        """)
