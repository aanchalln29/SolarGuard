from django.db import migrations
from django.utils import timezone


def get_installation_type(site_str):
    s = site_str.lower()
    if 'ground' in s:
        return 'ground_mount'
    elif 'carport' in s:
        return 'carport'
    elif 'warehouse' in s or 'industrial' in s or 'commercial' in s:
        return 'commercial'
    elif 'agri' in s or 'field' in s:
        return 'agrivoltaic'
    return 'rooftop'


def forward_populate_legacy_installations(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    UserProfile = apps.get_model('core', 'UserProfile')
    Installation = apps.get_model('core', 'Installation')
    LayoutRevision = apps.get_model('core', 'LayoutRevision')
    Panel = apps.get_model('core', 'Panel')
    MaintenanceIssue = apps.get_model('core', 'MaintenanceIssue')

    now = timezone.now()

    # 1. Populate UserProfile with safe legacy role mapping
    for user in User.objects.all():
        if user.is_superuser:
            role = 'admin'
        else:
            # operator1 and user2 default to 'customer' to prevent accidental permission elevation
            role = 'customer'
        UserProfile.objects.get_or_create(
            user=user,
            defaults={'role': role}
        )

    # 2. Group existing panels by (user_id, site_location)
    site_groups = {}
    for panel in Panel.objects.all().order_by('id'):
        owner_id = panel.user_id
        site = panel.site_location or "General Solar Array"
        key = (owner_id, site)
        if key not in site_groups:
            site_groups[key] = []
        site_groups[key].append(panel)

    # Clean display name mappings for legacy installations
    name_cleanups = {
        'Rooftop Array Block A (South-Facing)': 'Rooftop Array Block A',
        'Ground Mount Array Zone 2 (Inverter #3)': 'Ground Mount Array Zone 2',
        'Carport Canopy West Section': 'Carport Canopy West Section',
        'Agrivoltaic Experimental Field 4': 'Agrivoltaic Experimental Field 4',
        'Industrial Warehouse Rooftop Sector 5': 'Industrial Warehouse Sector 5',
        'Rooftop Demo Array Alpha': 'Rooftop Demo Array Alpha',
        'Private Array': 'Private Array',
        'North Rooftop Bay 4': 'North Rooftop Bay 4',
        'Home Roof-Array 2': 'Home Roof-Array 2',
    }

    for (owner_id, site_loc), panels in site_groups.items():
        owner = User.objects.get(id=owner_id) if owner_id else User.objects.filter(is_superuser=True).first()
        inst_name = name_cleanups.get(site_loc, site_loc)
        inst_type = get_installation_type(site_loc)

        # Earliest install_date among panels in this group
        earliest_date = None
        for p in panels:
            if p.install_date:
                if earliest_date is None or p.install_date < earliest_date:
                    earliest_date = p.install_date

        installation = Installation.objects.create(
            owner=owner,
            name=inst_name,
            site_address=site_loc,
            installation_type=inst_type,
            install_date=earliest_date,
            status='active'
        )

        active_cells = []
        # Assign installation-scoped permanent ID (e.g. SG-01-P001, SG-01-P002)
        for seq, panel in enumerate(panels, 1):
            perm_id = f"SG-{installation.id:02d}-P{seq:03d}"
            panel.installation = installation
            panel.permanent_id = perm_id
            panel.grid_row = 1
            panel.grid_col = seq
            panel.status = 'active'
            panel.save(update_fields=['installation', 'permanent_id', 'grid_row', 'grid_col', 'status'])

            active_cells.append({
                'row': 1,
                'col': seq,
                'panel_id': perm_id,
                'serial_number': panel.serial_number,
                'status': 'active'
            })

        # Create initial verified layout revision for legacy installation
        LayoutRevision.objects.create(
            installation=installation,
            version_number=1,
            status='verified',
            grid_rows=1,
            grid_cols=len(panels),
            layout_data={
                'rows': 1,
                'cols': len(panels),
                'active_cells': active_cells
            },
            submitted_by=owner,
            submitted_at=now,
            reviewed_by=owner if owner.is_superuser else None,
            reviewed_at=now if owner.is_superuser else None,
            review_notes='Legacy layout automatically verified during safe schema migration.'
        )

    # 3. Associate MaintenanceIssue records with their panel's installation
    for issue in MaintenanceIssue.objects.all():
        if issue.panel and issue.panel.installation:
            issue.installation = issue.panel.installation
            issue.save(update_fields=['installation'])


def reverse_populate_legacy_installations(apps, schema_editor):
    Panel = apps.get_model('core', 'Panel')
    MaintenanceIssue = apps.get_model('core', 'MaintenanceIssue')
    LayoutRevision = apps.get_model('core', 'LayoutRevision')
    Installation = apps.get_model('core', 'Installation')
    UserProfile = apps.get_model('core', 'UserProfile')

    MaintenanceIssue.objects.update(installation=None)
    Panel.objects.update(installation=None, permanent_id='', grid_row=None, grid_col=None)
    LayoutRevision.objects.all().delete()
    Installation.objects.all().delete()
    UserProfile.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_inspection_review_status_inspection_verified_outcome_and_more'),
    ]

    operations = [
        migrations.RunPython(forward_populate_legacy_installations, reverse_populate_legacy_installations),
    ]
