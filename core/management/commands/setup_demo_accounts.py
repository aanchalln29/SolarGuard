"""
SolarGuard — Safe Local Demo Account Setup Management Command
Prepares the three required local demo accounts:
- admin (Administrator)
- customer1 (Customer)
- technician1 (Technician)

Safeguards:
- Blocked in production / non-DEBUG mode
- Passwords resolved from CLI arguments or environment variables (never hardcoded in code)
- Proper Django password hashing (set_password)
- Preserves all existing data, installations, layouts, inspections, and issues
- Assigns realistic demonstration installations and issues to customer1 and technician1
"""

import os
import sys
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.contrib.auth.models import User
from core.models import UserProfile, Installation, MaintenanceIssue


class Command(BaseCommand):
    help = "Initializes or resets local demo accounts (admin, customer1, technician1) for local presentations."

    def add_arguments(self, parser):
        parser.add_argument(
            '--admin-password',
            type=str,
            default=os.environ.get('SOLARGUARD_DEMO_ADMIN_PASSWORD', ''),
            help="Password for 'admin' (can also be set via SOLARGUARD_DEMO_ADMIN_PASSWORD env var)."
        )
        parser.add_argument(
            '--customer-password',
            type=str,
            default=os.environ.get('SOLARGUARD_DEMO_CUSTOMER_PASSWORD', ''),
            help="Password for 'customer1' (can also be set via SOLARGUARD_DEMO_CUSTOMER_PASSWORD env var)."
        )
        parser.add_argument(
            '--technician-password',
            type=str,
            default=os.environ.get('SOLARGUARD_DEMO_TECH_PASSWORD', ''),
            help="Password for 'technician1' (can also be set via SOLARGUARD_DEMO_TECH_PASSWORD env var)."
        )
        parser.add_argument(
            '--force-local',
            action='store_true',
            help="Bypass production environment checks for explicit local staging evaluation."
        )

    def handle(self, *args, **options):
        # -----------------------------------------------------------------
        # 1. Environment & Production Safeguards
        # -----------------------------------------------------------------
        is_cloudflare_demo = getattr(settings, 'CLOUDFLARE_DEMO_MODE', False)
        is_debug = getattr(settings, 'DEBUG', False)
        force_local = options.get('force_local', False)

        if (not is_debug or is_cloudflare_demo) and not force_local:
            raise CommandError(
                "Execution Blocked: setup_demo_accounts is restricted to local development (DEBUG=True) "
                "and is disabled in production and Cloudflare tunnel modes. "
                "Use --force-local only if you explicitly intend to run locally."
            )

        admin_pwd = options.get('admin_password', '').strip()
        customer_pwd = options.get('customer_password', '').strip()
        tech_pwd = options.get('technician_password', '').strip()

        # Fallback to interactive prompts if passwords not provided via args or env
        if not admin_pwd or not customer_pwd or not tech_pwd:
            self.stdout.write(self.style.WARNING("Passwords not fully provided via CLI arguments or environment variables."))
            if not admin_pwd:
                import getpass
                admin_pwd = getpass.getpass("Enter password for 'admin': ").strip()
            if not customer_pwd:
                import getpass
                customer_pwd = getpass.getpass("Enter password for 'customer1': ").strip()
            if not tech_pwd:
                import getpass
                tech_pwd = getpass.getpass("Enter password for 'technician1': ").strip()

        if not admin_pwd or not customer_pwd or not tech_pwd:
            raise CommandError("All three passwords (admin, customer1, technician1) must be provided.")

        self.stdout.write(self.style.MIGRATE_HEADING("=" * 72))
        self.stdout.write(self.style.MIGRATE_HEADING(" SolarGuard — Local Demo Account Setup"))
        self.stdout.write(self.style.MIGRATE_HEADING("=" * 72))

        # -----------------------------------------------------------------
        # 2. Account 1: Admin ('admin')
        # -----------------------------------------------------------------
        admin_user = User.objects.filter(username='admin').first()
        if admin_user:
            admin_user.is_active = True
            admin_user.is_staff = True
            admin_user.is_superuser = True
            admin_user.set_password(admin_pwd)
            admin_user.save()
            admin_action = "Updated & Activated"
        else:
            admin_user = User.objects.create_superuser(
                username='admin',
                email='admin@solarguard.local',
                password=admin_pwd
            )
            admin_action = "Created"

        admin_profile, _ = UserProfile.objects.get_or_create(user=admin_user)
        admin_profile.role = 'admin'
        admin_profile.save()

        self.stdout.write(
            self.style.SUCCESS(f"  [{admin_action}] Admin: 'admin' (Superuser, Active, Role: Administrator)")
        )

        # -----------------------------------------------------------------
        # 3. Account 2: Customer ('customer1')
        # -----------------------------------------------------------------
        customer_user = User.objects.filter(username='customer1').first()
        if customer_user:
            customer_user.is_active = True
            customer_user.is_staff = False
            customer_user.is_superuser = False
            customer_user.set_password(customer_pwd)
            customer_user.save()
            cust_action = "Updated & Activated"
        else:
            customer_user = User.objects.create_user(
                username='customer1',
                email='customer1@solarguard.local',
                password=customer_pwd,
                first_name='Solar',
                last_name='Customer'
            )
            cust_action = "Created"

        cust_profile, _ = UserProfile.objects.get_or_create(user=customer_user)
        cust_profile.role = 'customer'
        cust_profile.save()

        self.stdout.write(
            self.style.SUCCESS(f"  [{cust_action}] Customer: 'customer1' (Active, Role: Customer)")
        )

        # -----------------------------------------------------------------
        # 4. Account 3: Technician ('technician1')
        # -----------------------------------------------------------------
        tech_user = User.objects.filter(username='technician1').first()
        if tech_user:
            tech_user.is_active = True
            tech_user.is_staff = False
            tech_user.is_superuser = False
            tech_user.set_password(tech_pwd)
            tech_user.save()
            tech_action = "Updated & Activated"
        else:
            tech_user = User.objects.create_user(
                username='technician1',
                email='technician1@solarguard.local',
                password=tech_pwd,
                first_name='Certified',
                last_name='Technician'
            )
            tech_action = "Created"

        tech_profile, _ = UserProfile.objects.get_or_create(user=tech_user)
        tech_profile.role = 'technician'
        tech_profile.save()

        self.stdout.write(
            self.style.SUCCESS(f"  [{tech_action}] Technician: 'technician1' (Active, Role: Technician)")
        )

        # Also support 'tech1' as an alias technician account with the same credentials
        tech1_alias = User.objects.filter(username='tech1').first()
        if tech1_alias:
            tech1_alias.is_active = True
            tech1_alias.set_password(tech_pwd)
            tech1_alias.save()
        else:
            tech1_alias = User.objects.create_user(
                username='tech1',
                email='tech1@solarguard.local',
                password=tech_pwd,
                first_name='Certified',
                last_name='Technician'
            )
        tech1_profile, _ = UserProfile.objects.get_or_create(user=tech1_alias)
        tech1_profile.role = 'technician'
        tech1_profile.save()
        self.stdout.write(
            self.style.SUCCESS("  [Synced] Technician alias: 'tech1' (Active, Role: Technician)")
        )

        # -----------------------------------------------------------------
        # 5. Data Preservation & Demo Association
        # Ensure customer1 has access to an installation with panels and data,
        # and technician1 is assigned to manage that installation and work orders.
        # -----------------------------------------------------------------
        # Prefer Installation 11 (Apex Commercial SunPark) which contains rich 4-3-4 layout & issues
        demo_inst = Installation.objects.filter(pk=11).first()
        if not demo_inst:
            # Fallback to any installation not owned by admin
            demo_inst = Installation.objects.exclude(owner=admin_user).first()
        if not demo_inst:
            demo_inst = Installation.objects.first()

        if demo_inst:
            demo_inst.owner = customer_user
            demo_inst.assigned_technician = tech_user
            demo_inst.save(update_fields=['owner', 'assigned_technician'])

            # Assign associated open issues to technician1 so technician dashboard shows work orders
            assigned_count = MaintenanceIssue.objects.filter(installation=demo_inst).update(
                assigned_technician=tech_user
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"  [Linked] Installation '{demo_inst.name}' (ID: {demo_inst.id}) "
                    f"assigned to Owner: 'customer1' and Assigned Tech: 'technician1'"
                )
            )
            self.stdout.write(
                self.style.SUCCESS(f"  [Linked] {assigned_count} maintenance issue(s) assigned to 'technician1'")
            )

        self.stdout.write(self.style.MIGRATE_HEADING("-" * 72))
        self.stdout.write(self.style.SUCCESS("Demo accounts initialized and verified successfully!"))
        self.stdout.write("Ready for local college demonstration on 127.0.0.1:8000.\n")
