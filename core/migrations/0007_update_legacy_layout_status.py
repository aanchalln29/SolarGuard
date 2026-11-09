from django.db import migrations


def mark_legacy_layouts_as_imported(apps, schema_editor):
    LayoutRevision = apps.get_model('core', 'LayoutRevision')
    # Update all automatically generated legacy layouts to 'imported' (unverified)
    for rev in LayoutRevision.objects.all():
        if rev.status == 'verified' and 'automatically verified' in (rev.review_notes or '').lower():
            rev.status = 'imported'
            rev.reviewed_by = None
            rev.reviewed_at = None
            rev.review_notes = 'Legacy layout automatically imported from pre-existing system inventory. Pending physical on-site technician layout verification.'
            rev.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_notes'])


def revert_legacy_layouts_to_verified(apps, schema_editor):
    LayoutRevision = apps.get_model('core', 'LayoutRevision')
    for rev in LayoutRevision.objects.all():
        if rev.status == 'imported':
            rev.status = 'verified'
            rev.save(update_fields=['status'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_populate_legacy_installations'),
    ]

    operations = [
        migrations.RunPython(mark_legacy_layouts_as_imported, revert_legacy_layouts_to_verified),
    ]
