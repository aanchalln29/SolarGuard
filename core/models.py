import datetime
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    """
    Extends standard Django User with explicit SolarGuard roles:
    - customer: Homeowner or solar array owner
    - technician: Certified field engineer
    - admin: Platform / operations administrator
    """
    ROLE_CHOICES = [
        ('customer', 'Customer'),
        ('technician', 'Technician'),
        ('admin', 'Administrator'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='customer', verbose_name="Account Role")
    phone_number = models.CharField(max_length=30, blank=True, default='', verbose_name="Phone Number")
    organization = models.CharField(max_length=150, blank=True, default='', verbose_name="Company / Organization")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"


@receiver(post_save, sender=User)
def create_or_save_user_profile(sender, instance, created, **kwargs):
    if created:
        role = 'admin' if instance.is_superuser else 'customer'
        UserProfile.objects.get_or_create(user=instance, defaults={'role': role})
    else:
        if hasattr(instance, 'profile'):
            instance.profile.save()


class Installation(models.Model):
    """
    First-class entity representing a physical solar site / array installation.
    Owns solar panels, layout revisions, and maintenance issues.
    """
    TYPE_CHOICES = [
        ('rooftop', 'Rooftop Array'),
        ('ground_mount', 'Ground-Mounted Array'),
        ('carport', 'Carport Canopy'),
        ('commercial', 'Commercial / Industrial Array'),
        ('agrivoltaic', 'Agrivoltaic Experimental Array'),
        ('other', 'Other Installation'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active Operations'),
        ('archived', 'Archived'),
        ('decommissioned', 'Decommissioned'),
    ]

    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name='installations', verbose_name="Owner / Customer")
    name = models.CharField(max_length=150, verbose_name="Installation Name")
    site_address = models.CharField(max_length=255, verbose_name="Site Address / Location")
    installation_type = models.CharField(max_length=40, choices=TYPE_CHOICES, default='rooftop', verbose_name="Installation Type")
    install_date = models.DateField(null=True, blank=True, verbose_name="Commissioning Date")
    overview_image = models.ImageField(upload_to='installations/%Y/%m/', null=True, blank=True, verbose_name="Site Overview Photo")
    assigned_technician = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_installations', verbose_name="Assigned Technician")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', verbose_name="Installation Status")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Solar Installation'
        verbose_name_plural = 'Solar Installations'

    def __str__(self):
        return f"{self.name} ({self.owner.username})"

    @property
    def total_panels_count(self):
        return self.panels.filter(status='active').count()

    @property
    def verified_layout(self):
        """Returns physically technician-verified layout revision if approved."""
        return self.layout_revisions.filter(status='verified').order_by('-version_number').first()

    @property
    def active_layout(self):
        """Returns the current operational layout (either technician-verified or legacy imported)."""
        return self.layout_revisions.filter(status__in=['verified', 'imported']).order_by('-version_number').first()

    @property
    def pending_or_draft_layout(self):
        return self.layout_revisions.filter(status__in=['draft', 'pending_verification']).order_by('-version_number').first()

    @property
    def is_layout_verified(self):
        """Returns True if the active layout is physically verified by a qualified technician or admin."""
        return self.layout_revisions.filter(status='verified').exists()


class LayoutRevision(models.Model):
    """
    Versioned solar panel layout revision.
    Separates draft/pending customer edits from the currently active verified layout.
    Supports irregular grids (such as 4-3-4 configurations).
    """
    STATUS_CHOICES = [
        ('imported', 'Legacy Imported (Unverified Layout)'),
        ('draft', 'Draft (Work in Progress)'),
        ('pending_verification', 'Pending Verification'),
        ('verified', 'Verified & Active'),
        ('changes_requested', 'Changes Requested'),
        ('superseded', 'Superseded (Historical)'),
    ]

    installation = models.ForeignKey(Installation, on_delete=models.PROTECT, related_name='layout_revisions', verbose_name="Installation")
    version_number = models.PositiveIntegerField(default=1, verbose_name="Version Number")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='draft', verbose_name="Revision Status")

    # Grid dimensions & irregular structure JSON
    # Irregular layouts (e.g. 4-3-4) are stored as:
    # { "rows": 3, "cols": 4, "active_cells": [{"row": 1, "col": 1, "panel_id": "SG-01-P001"}, ...] }
    grid_rows = models.PositiveIntegerField(default=1, verbose_name="Grid Total Rows")
    grid_cols = models.PositiveIntegerField(default=1, verbose_name="Grid Total Columns")
    layout_data = models.JSONField(default=dict, blank=True, verbose_name="Layout Grid Structure JSON")

    # Workflow & Audit metadata
    submitted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='submitted_layouts', verbose_name="Submitted By")
    submitted_at = models.DateTimeField(null=True, blank=True, verbose_name="Submitted At")
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_layouts', verbose_name="Reviewed By")
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="Reviewed At")
    review_notes = models.TextField(blank=True, default="", verbose_name="Review / Feedback Notes")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-version_number']
        unique_together = [('installation', 'version_number')]
        verbose_name = 'Layout Revision'
        verbose_name_plural = 'Layout Revisions'

    def __str__(self):
        return f"{self.installation.name} - v{self.version_number} [{self.get_status_display()}]"


class Panel(models.Model):
    """
    Physical solar panel module belonging to an Installation.
    Maintains a stable, installation-scoped permanent identifier (e.g. SG-01-P006)
    independent of mutable grid coordinates (grid_row, grid_col).
    Preserves OEM serial numbers and historical records across position moves.
    """
    PANEL_STATUS_CHOICES = [
        ('active', 'Active Module'),
        ('empty_slot', 'Empty Grid Slot'),
        ('retired', 'Retired / Decommissioned'),
    ]

    installation = models.ForeignKey(Installation, on_delete=models.PROTECT, null=True, blank=True, related_name='panels', verbose_name="Parent Installation")
    permanent_id = models.CharField(max_length=60, blank=True, default="", verbose_name="Permanent Panel ID")
    grid_row = models.PositiveIntegerField(null=True, blank=True, verbose_name="Grid Row (1-indexed)")
    grid_col = models.PositiveIntegerField(null=True, blank=True, verbose_name="Grid Column (1-indexed)")
    status = models.CharField(max_length=20, choices=PANEL_STATUS_CHOICES, default='active', verbose_name="Panel Status")
    panel_specs = models.JSONField(default=dict, blank=True, verbose_name="Technical Specs JSON")

    # Backward compatibility: preserve existing user and site_location fields
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='panels', verbose_name="Owner / Account")
    serial_number = models.CharField(max_length=60, unique=True, verbose_name="Panel Serial Number")
    site_location = models.CharField(max_length=150, verbose_name="Site Location / Array Zone")
    install_date = models.DateField(null=True, blank=True, verbose_name="Installation Date (Optional)")
    last_cleaned_date = models.DateField(null=True, blank=True, verbose_name="Last Cleaned Date (Optional)")
    avg_temp_exposure = models.FloatField(default=35.0, verbose_name="Avg Temp Exposure (°C)")
    dust_index_avg = models.FloatField(default=0.35, verbose_name="Avg Dust Index (0.0 to 1.0)")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['serial_number']
        verbose_name = 'Solar Panel'
        verbose_name_plural = 'Solar Panels'

    def __str__(self):
        display_id = self.permanent_id or self.serial_number
        site_str = self.installation.name if self.installation else self.site_location
        return f"{display_id} ({site_str})"

    @property
    def owner(self):
        if self.installation and self.installation.owner:
            return self.installation.owner
        return self.user

    @property
    def panel_age_months(self):
        date_ref = self.install_date or (self.installation.install_date if self.installation else None)
        if not date_ref:
            return None
        today = datetime.date.today()
        months = (today.year - date_ref.year) * 12 + (today.month - date_ref.month)
        return max(0, months)

    @property
    def days_since_last_cleaning(self):
        if not self.last_cleaned_date:
            return None
        today = datetime.date.today()
        delta = (today - self.last_cleaned_date).days
        return max(0, delta)

    @property
    def fault_count_last_6_months(self):
        six_months_ago = timezone.now() - datetime.timedelta(days=180)
        return self.inspections.filter(
            inspected_at__gte=six_months_ago
        ).exclude(predicted_class__iexact='Normal').count()

    @property
    def latest_inspection(self):
        return self.inspections.order_by('-inspected_at').first()

    @property
    def current_risk(self):
        latest = self.latest_inspection
        if latest:
            return latest.risk_category
        return "Unknown"

    @property
    def open_issues_count(self):
        return self.issues.filter(status__in=['Open', 'In Progress']).count()

    def get_derived_condition(self, latest=None):
        """
        Derives the panel's latest known visible condition from its latest valid inspection.
        Follows SolarGuard safety & diagnostic display rules:
        - If never inspected: 'Not Inspected' (neutral slate)
        - If confidence < 50.0% or unreadable/unable: 'Needs Review' (purple/amber)
        - If latest AI prediction is Normal: 'Appears Normal' (emerald)
        - If Dusty or Bird-Dropping: 'Cleaning May Be Needed' (amber)
        - If Surface-Damage or Cracked: 'Possible Surface Damage — Technician Review Recommended' (danger/red)
        - Distinguishes raw AI prediction from technician-verified outcome.
        - Supports prefetched inspection cache to eliminate N+1 queries.
        """
        if latest is None:
            if hasattr(self, '_prefetched_objects_cache') and 'inspections' in self._prefetched_objects_cache:
                insps = self.inspections.all()
                latest = insps[0] if len(insps) > 0 else None
            else:
                latest = self.latest_inspection

        if not latest:
            return {
                'status': 'not_inspected',
                'category': 'Not Inspected',
                'label': 'Not Inspected',
                'status_label': 'Not Inspected',
                'badge_class': 'bg-secondary bg-opacity-75 text-white',
                'text_class': 'text-muted',
                'tile_bg': 'linear-gradient(145deg, #2A333E, #384556)',
                'tile_border': '#4B5A6E',
                'detail': 'No visual inspection has been conducted for this panel yet.',
                'is_inspected': False,
                'is_verified': False,
                'action_needed': False,
                'inspection': None,
            }

        is_verified = (latest.review_status == 'technician_verified')
        finding = (latest.verified_outcome if is_verified and latest.verified_outcome else latest.predicted_class) or ''
        finding_lower = finding.lower()
        conf = latest.confidence_score

        # Check for model unavailable / failed inference
        if ('unavailable' in finding_lower or 'offline' in finding_lower or 
                'failed' in finding_lower or 'error' in finding_lower or 'missing' in finding_lower or
                ('unavailable' in (latest.model_identifier or '').lower())):
            return {
                'status': 'review',
                'category': 'Inspection Needs Review',
                'label': 'AI Model Unavailable — Needs Review',
                'status_label': 'Needs Review',
                'raw_finding': latest.predicted_class,
                'verified_finding': latest.verified_outcome if is_verified else None,
                'confidence': 0.0,
                'badge_class': 'bg-warning text-dark border',
                'text_class': 'text-warning-emphasis',
                'tile_bg': 'linear-gradient(145deg, #3A2E1A, #4E3E22)',
                'tile_border': '#F59E0B',
                'detail': 'AI visual screening was offline or unavailable during inspection. Visual condition could not be verified automatically; manual technician review recommended.',
                'is_inspected': True,
                'is_verified': is_verified,
                'action_needed': True,
                'inspection': latest,
            }

        # Check for inconclusive / low confidence (<60%) / flagged / unreadable
        if ('unable' in finding_lower or 'retake' in finding_lower or
                latest.review_status == 'flagged' or
                (not is_verified and conf < 60.0)):
            return {
                'status': 'review',
                'category': 'Needs Review',
                'label': 'Needs Review',
                'status_label': 'Needs Review',
                'raw_finding': latest.predicted_class,
                'verified_finding': latest.verified_outcome if is_verified else None,
                'confidence': conf,
                'badge_class': 'bg-warning text-dark',
                'text_class': 'text-warning-emphasis',
                'tile_bg': 'linear-gradient(145deg, #2E253B, #3F3353)',
                'tile_border': '#A882DD',
                'detail': 'AI confidence is below 60% or image was flagged for manual review. Technician visual review recommended.',
                'is_inspected': True,
                'is_verified': is_verified,
                'action_needed': True,
                'inspection': latest,
            }

        if 'surface-damage' in finding_lower or 'damage' in finding_lower or 'crack' in finding_lower:
            label = 'Technician Verified: Surface Damage' if is_verified else 'Possible Surface Damage — Technician Review Recommended'
            return {
                'status': 'damage',
                'category': 'Possible Surface Damage',
                'label': label,
                'status_label': label,
                'raw_finding': latest.predicted_class,
                'verified_finding': latest.verified_outcome if is_verified else None,
                'confidence': conf,
                'badge_class': 'bg-danger text-white',
                'text_class': 'text-danger',
                'tile_bg': 'linear-gradient(145deg, #3D1A1A, #572525)',
                'tile_border': '#E63946',
                'detail': 'Visible surface fracture or cell structural anomaly detected. Avoid physical contact; schedule technician service.',
                'is_inspected': True,
                'is_verified': is_verified,
                'action_needed': True,
                'inspection': latest,
            }

        if 'dust' in finding_lower or 'bird' in finding_lower:
            label = 'Technician Verified: Soiling' if is_verified else 'Cleaning May Be Needed'
            return {
                'status': 'dust' if 'dust' in finding_lower else 'bird',
                'category': 'Cleaning May Be Needed',
                'label': label,
                'status_label': label,
                'raw_finding': latest.predicted_class,
                'verified_finding': latest.verified_outcome if is_verified else None,
                'confidence': conf,
                'badge_class': 'bg-warning-subtle text-warning-emphasis border border-warning',
                'text_class': 'text-warning-emphasis',
                'tile_bg': 'linear-gradient(145deg, #3A2F17, #4D3F20)',
                'tile_border': '#D6A545',
                'detail': f"Visual soiling detected ({finding}). Washing recommended to restore solar irradiance absorption.",
                'is_inspected': True,
                'is_verified': is_verified,
                'action_needed': True,
                'inspection': latest,
            }

        # Normal condition requires explicit Normal or Clean finding
        if 'normal' in finding_lower or 'clean' in finding_lower or finding_lower == '':
            label = 'Technician Verified: Normal' if is_verified else 'Appears Normal'
            return {
                'status': 'normal',
                'category': 'Appears Normal',
                'label': label,
                'status_label': label,
                'raw_finding': latest.predicted_class,
                'verified_finding': latest.verified_outcome if is_verified else None,
                'confidence': conf,
                'badge_class': 'bg-emerald text-white',
                'text_class': 'text-emerald',
                'tile_bg': 'linear-gradient(145deg, #16362F, #1F4D42)',
                'tile_border': '#2B6658',
                'detail': 'No visible surface defects detected in the latest photograph. Note: Standard photography does not verify internal electrical health.',
                'is_inspected': True,
                'is_verified': is_verified,
                'action_needed': False,
                'inspection': latest,
            }

        # Catch-all for unrecognized findings: never default to Normal
        return {
            'status': 'review',
            'category': 'Inspection Needs Review',
            'label': 'Inconclusive Finding — Needs Review',
            'status_label': 'Needs Review',
            'raw_finding': latest.predicted_class,
            'verified_finding': latest.verified_outcome if is_verified else None,
            'confidence': conf,
            'badge_class': 'bg-warning text-dark border',
            'text_class': 'text-warning-emphasis',
            'tile_bg': 'linear-gradient(145deg, #2E253B, #3F3353)',
            'tile_border': '#A882DD',
            'detail': 'Inspection finding is inconclusive or unverified. Manual technician review is recommended.',
            'is_inspected': True,
            'is_verified': is_verified,
            'action_needed': True,
            'inspection': latest,
        }


class Inspection(models.Model):
    """
    Visual inspection record for a specific Solar Panel.
    Uses protected deletion to prevent accidental loss of physical inspection evidence.
    """
    RISK_CHOICES = [
        ('Low', 'Low Risk'),
        ('Medium', 'Medium Risk'),
        ('High', 'High Risk'),
    ]

    REVIEW_STATUS_CHOICES = [
        ('ai_predicted', 'AI Predicted (Awaiting Review)'),
        ('technician_verified', 'Technician Verified'),
        ('flagged', 'Flagged for Re-inspection'),
    ]

    panel = models.ForeignKey(Panel, on_delete=models.PROTECT, related_name='inspections')
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='inspections', verbose_name="Inspected By")
    image = models.ImageField(upload_to='inspections/%Y/%m/%d/', verbose_name="Inspection Image")
    predicted_class = models.CharField(max_length=60, verbose_name="Predicted Condition")
    confidence_score = models.FloatField(verbose_name="Confidence Score (%)")
    degradation_probability = models.FloatField(default=0.0, verbose_name="Degradation Probability (%)")
    risk_category = models.CharField(max_length=20, choices=RISK_CHOICES, default='Low', verbose_name="Risk Category")

    # Transparent Rules-Based Maintenance Priority
    maintenance_priority_score = models.IntegerField(default=0, verbose_name="Maintenance Priority Score (0-100)")
    maintenance_priority_level = models.CharField(max_length=20, default="Low", verbose_name="Maintenance Priority Level")
    priority_explanation = models.TextField(blank=True, default="", verbose_name="Priority Score Explanation")

    # Model provenance tracking
    is_mock_prediction = models.BooleanField(default=True, verbose_name="Is Mock / Synthetic Prediction")
    model_identifier = models.CharField(max_length=100, default="Dev Mock (Feature Classifier)", verbose_name="Inference Engine / Model")
    class_probabilities = models.JSONField(default=dict, blank=True, verbose_name="Class Probabilities (%)")

    # Verification workflow & audit trail
    review_status = models.CharField(max_length=30, choices=REVIEW_STATUS_CHOICES, default='ai_predicted', verbose_name="Technician Review Status")
    verified_outcome = models.CharField(max_length=60, blank=True, default="", verbose_name="Technician Verified Finding")
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_inspections', verbose_name="Verified / Reviewed By")
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="Review Timestamp")
    review_notes = models.TextField(blank=True, default="", verbose_name="Technician Review Notes")

    inspected_at = models.DateTimeField(auto_now_add=True, verbose_name="Inspection Timestamp")
    notes = models.TextField(blank=True, null=True, verbose_name="Engineer / Operator Notes")

    @property
    def verified_finding(self):
        return self.verified_outcome


    class Meta:
        ordering = ['-inspected_at']
        verbose_name = 'Inspection Record'
        verbose_name_plural = 'Inspection Records'

    def __str__(self):
        panel_label = self.panel.permanent_id or self.panel.serial_number
        return f"{panel_label} - {self.predicted_class} ({self.maintenance_priority_level}) at {self.inspected_at.strftime('%Y-%m-%d %H:%M')}"


class MaintenanceIssue(models.Model):
    """
    Work order / maintenance ticket for a solar array and panel.
    Full lifecycle: Open -> Assigned -> In Progress -> Resolved -> Closed
    """
    STATUS_CHOICES = [
        ('Open', 'Open'),
        ('Assigned', 'Assigned'),
        ('In Progress', 'In Progress'),
        ('Resolved', 'Resolved'),
        ('Closed', 'Closed'),
        ('Needs Review', 'Needs Review'),
    ]

    PRIORITY_CHOICES = [
        ('Low', 'Low Priority'),
        ('Medium', 'Medium Priority'),
        ('High', 'High Priority'),
    ]

    installation = models.ForeignKey(Installation, on_delete=models.PROTECT, null=True, blank=True, related_name='maintenance_issues', verbose_name="Installation")
    panel = models.ForeignKey(Panel, on_delete=models.PROTECT, related_name='issues', verbose_name="Target Panel")
    inspection = models.ForeignKey(Inspection, on_delete=models.SET_NULL, null=True, blank=True, related_name='issues', verbose_name="Originating Inspection")
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='issues', verbose_name="Created By")
    assigned_technician = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_issues', verbose_name="Assigned Technician")

    title = models.CharField(max_length=200, verbose_name="Issue Title")
    description = models.TextField(blank=True, verbose_name="Issue Description / Action Needed")
    supporting_photo = models.ImageField(upload_to='maintenance/%Y/%m/%d/', blank=True, null=True, verbose_name="Supporting Photograph")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Open', verbose_name="Status")
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='Medium', verbose_name="Priority")
    resolution_notes = models.TextField(blank=True, default="", verbose_name="Resolution Notes")

    # Payment Workflow (Razorpay Test Mode)
    PAYMENT_STATUS_CHOICES = [
        ('unbilled', 'Unbilled'),
        ('pending', 'Payment Pending'),
        ('paid', 'Paid (Test Mode)'),
        ('failed', 'Payment Failed'),
    ]
    service_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Service Charge (INR)")
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='unbilled', verbose_name="Payment Status")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Last Updated")
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name="Resolved At")
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name="Closed At")

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Maintenance Issue'
        verbose_name_plural = 'Maintenance Issues'

    def __str__(self):
        panel_label = self.panel.permanent_id or self.panel.serial_number
        return f"[{self.status}] {self.title} ({panel_label})"

    @property
    def logs(self):
        return self.action_logs.all()

    @property
    def latest_successful_payment(self):
        return self.payments.filter(status='success').first()


class MaintenanceLog(models.Model):
    """
    Historical log of actions performed (e.g. cleaning, repairs, part replacements, assignments, status transitions).
    Maintains an immutable audit trail for each work order.
    """
    ACTION_CHOICES = [
        ('assignment', 'Technician Assigned / Reassigned'),
        ('status_change', 'Status Transition'),
        ('note', 'Field Work Notes'),
        ('cleaning', 'Surface Cleaning & Wash'),
        ('repair', 'Cell / Glass Surface Repair'),
        ('replacement', 'Module / Bypass Diode Replacement'),
        ('inspection', 'Field Routine Inspection'),
        ('resolution', 'Work Order Resolved'),
        ('closure', 'Task Closed / Approved'),
        ('payment', 'Service Fee Payment Verified'),
    ]

    panel = models.ForeignKey(Panel, on_delete=models.PROTECT, related_name='maintenance_logs')
    issue = models.ForeignKey(MaintenanceIssue, on_delete=models.SET_NULL, null=True, blank=True, related_name='action_logs', verbose_name="Linked Maintenance Issue")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='maintenance_logs', verbose_name="Action Taken By")
    action_type = models.CharField(max_length=40, choices=ACTION_CHOICES, verbose_name="Action Type")
    performed_at = models.DateField(default=datetime.date.today, verbose_name="Date Performed")
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True, verbose_name="Logged At")
    notes = models.TextField(blank=True, null=True, verbose_name="Work Notes / Audit Details")

    previous_status = models.CharField(max_length=30, blank=True, default="", verbose_name="Previous Status")
    new_status = models.CharField(max_length=30, blank=True, default="", verbose_name="New Status")
    technician = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='technician_assignment_logs', verbose_name="Assigned Technician")

    class Meta:
        ordering = ['-created_at', '-performed_at']
        verbose_name = 'Maintenance Log'
        verbose_name_plural = 'Maintenance Logs'

    def __str__(self):
        panel_label = self.panel.permanent_id or self.panel.serial_number
        return f"{panel_label} - {self.get_action_type_display()} on {self.performed_at}"


class PaymentTransaction(models.Model):
    """
    Immutable audit record for Razorpay Sandbox / Test Mode payment transactions.
    Preserves transaction ID, signature verification, and PDF receipt details.
    """
    STATUS_CHOICES = [
        ('created', 'Order Created'),
        ('pending', 'Pending Verification'),
        ('success', 'Verified & Settled (Sandbox)'),
        ('failed', 'Verification Failed'),
        ('cancelled', 'Cancelled by User'),
    ]

    issue = models.ForeignKey(MaintenanceIssue, on_delete=models.CASCADE, related_name='payments', verbose_name="Maintenance Issue")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='payment_transactions', verbose_name="Initiated By")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Amount (INR)")
    amount_paise = models.IntegerField(verbose_name="Amount (Paise)")
    currency = models.CharField(max_length=10, default='INR', verbose_name="Currency")

    razorpay_order_id = models.CharField(max_length=100, unique=True, db_index=True, verbose_name="Razorpay Order ID")
    razorpay_payment_id = models.CharField(max_length=100, blank=True, default='', db_index=True, verbose_name="Razorpay Payment ID")
    razorpay_signature = models.CharField(max_length=255, blank=True, default='', verbose_name="Razorpay Signature")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='created', verbose_name="Transaction Status")
    is_sandbox = models.BooleanField(default=True, verbose_name="Is Test Mode / Sandbox")
    receipt_number = models.CharField(max_length=60, unique=True, blank=True, null=True, verbose_name="Receipt Number")

    error_code = models.CharField(max_length=100, blank=True, default='', verbose_name="Error Code")
    error_description = models.TextField(blank=True, default='', verbose_name="Error Description")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created At")
    verified_at = models.DateTimeField(null=True, blank=True, verbose_name="Verified At")

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Payment Transaction'
        verbose_name_plural = 'Payment Transactions'

    def __str__(self):
        return f"Payment #{self.id} [{self.status}] — ₹{self.amount} ({self.razorpay_order_id})"


class Notification(models.Model):
    """
    In-app database-backed notification center model.
    Enforces role-based recipient isolation, unread tracking, and direct record navigation.
    """
    EVENT_TYPE_CHOICES = [
        # Administrator events
        ('new_installation', 'New Installation Submitted'),
        ('layout_review_requested', 'Layout Review Requested'),
        ('new_maintenance_issue', 'New Maintenance Work Order'),
        ('technician_completion', 'Technician Completion Submitted'),

        # Customer events
        ('installation_approved', 'Installation Approved'),
        ('installation_assigned', 'Technician Assigned to Site'),
        ('layout_verified', 'Layout Verified & Active'),
        ('layout_rejected', 'Layout Changes Requested'),
        ('maintenance_assigned', 'Technician Assigned to Ticket'),
        ('maintenance_completed', 'Maintenance Work Resolved'),
        ('maintenance_closed', 'Maintenance Ticket Closed'),

        # Technician events
        ('work_assigned', 'Work Order Assigned'),
        ('work_reassigned', 'Work Order Reassigned'),
        ('work_updated', 'Work Order Updated'),
        ('installation_assigned', 'Assigned to Solar Site'),
    ]

    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications', verbose_name="Recipient")
    event_type = models.CharField(max_length=50, choices=EVENT_TYPE_CHOICES, verbose_name="Event Type")
    title = models.CharField(max_length=200, verbose_name="Notification Title")
    message = models.TextField(verbose_name="Notification Message")
    target_url = models.CharField(max_length=255, blank=True, default='', verbose_name="Target Action URL")
    is_read = models.BooleanField(default=False, db_index=True, verbose_name="Is Read")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Timestamp")

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'

    def __str__(self):
        return f"[{self.recipient.username}] {self.title} ({'Read' if self.is_read else 'Unread'})"

