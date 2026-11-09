"""
SolarGuard — Role-Based Access Control (RBAC) & Object-Level Permission Services

Enforces strict authorization across Customer, Technician, and Administrator roles:
- Customer: Own installations, panels, inspections, maintenance requests.
- Technician: Explicitly assigned installations, work orders, layout verifications.
- Administrator: Platform-wide management, technician assignments, layout approvals.
"""

from functools import wraps
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.contrib import messages

from .models import Installation, Panel, Inspection, MaintenanceIssue, LayoutRevision, UserProfile


def get_user_role(user) -> str:
    """
    Returns normalized role string: 'admin', 'technician', or 'customer'.
    Superusers and staff default to 'admin'.
    """
    if not user or not user.is_authenticated:
        return 'anonymous'
    if user.is_superuser:
        return 'admin'
    if hasattr(user, 'profile'):
        return (user.profile.role or 'customer').lower()
    # Fallback: check profile table directly
    profile = UserProfile.objects.filter(user=user).first()
    if profile:
        return (profile.role or 'customer').lower()
    return 'customer'


def is_admin(user) -> bool:
    return user.is_authenticated and (user.is_superuser or get_user_role(user) == 'admin')


def is_technician(user) -> bool:
    return user.is_authenticated and (not user.is_superuser) and get_user_role(user) == 'technician'


def is_customer(user) -> bool:
    return user.is_authenticated and (not user.is_superuser) and get_user_role(user) == 'customer'


# ============================================================================
# QuerySet Scoping Helpers (Prevent cross-tenant / unauthorized record leakage)
# ============================================================================

def get_accessible_installations(user):
    """
    Returns QuerySet of installations the user is authorized to access:
    - Admin: All installations
    - Technician: Only installations where assigned_technician == user
    - Customer: Only installations where owner == user
    """
    if not user.is_authenticated:
        return Installation.objects.none()
    if is_admin(user):
        return Installation.objects.all()
    if is_technician(user):
        return Installation.objects.filter(assigned_technician=user)
    return Installation.objects.filter(owner=user)


def get_accessible_panels(user):
    """
    Returns QuerySet of panels the user is authorized to view / inspect:
    - Admin: All panels
    - Technician: Panels at installations assigned to this technician
    - Customer: Panels belonging to customer installations (or user legacy link)
    """
    if not user.is_authenticated:
        return Panel.objects.none()
    if is_admin(user):
        return Panel.objects.all()
    if is_technician(user):
        return Panel.objects.filter(installation__assigned_technician=user)
    return Panel.objects.filter(
        Q(installation__owner=user) | (Q(installation__isnull=True) & Q(user=user))
    )


def get_accessible_inspections(user):
    """
    Returns QuerySet of inspection records the user is authorized to view:
    - Admin: All inspections
    - Technician: Inspections at assigned installations
    - Customer: Inspections for owned installations / panels
    """
    if not user.is_authenticated:
        return Inspection.objects.none()
    if is_admin(user):
        return Inspection.objects.all()
    if is_technician(user):
        return Inspection.objects.filter(panel__installation__assigned_technician=user)
    return Inspection.objects.filter(
        Q(panel__installation__owner=user) | Q(panel__user=user) | Q(user=user)
    )


def get_accessible_maintenance_issues(user):
    """
    Returns QuerySet of work orders / issues the user is authorized to access:
    - Admin: All issues
    - Technician: Issues explicitly assigned to them OR at installations assigned to them
    - Customer: Issues on owned installations / panels
    """
    if not user.is_authenticated:
        return MaintenanceIssue.objects.none()
    if is_admin(user):
        return MaintenanceIssue.objects.all()
    if is_technician(user):
        return MaintenanceIssue.objects.filter(assigned_technician=user)
    return MaintenanceIssue.objects.filter(
        Q(installation__owner=user) | Q(panel__installation__owner=user) | Q(panel__user=user) | Q(user=user)
    )


def get_accessible_layout_revisions(user):
    """
    Returns QuerySet of layout revisions the user is authorized to view:
    - Admin: All revisions
    - Technician: Revisions for assigned installations
    - Customer: Revisions for owned installations
    """
    if not user.is_authenticated:
        return LayoutRevision.objects.none()
    if is_admin(user):
        return LayoutRevision.objects.all()
    if is_technician(user):
        return LayoutRevision.objects.filter(installation__assigned_technician=user)
    return LayoutRevision.objects.filter(installation__owner=user)


# ============================================================================
# Object-Level Permission Verifiers
# ============================================================================

def can_view_installation(user, installation: Installation) -> bool:
    if not user.is_authenticated:
        return False
    if is_admin(user):
        return True
    if is_technician(user):
        return installation.assigned_technician_id == user.id
    return installation.owner_id == user.id


def can_edit_installation(user, installation: Installation) -> bool:
    """Customers can edit their own installations; Admins can edit any."""
    if not user.is_authenticated:
        return False
    if is_admin(user):
        return True
    return installation.owner_id == user.id


def can_view_panel(user, panel: Panel) -> bool:
    if not user.is_authenticated:
        return False
    if is_admin(user):
        return True
    if panel.installation:
        return can_view_installation(user, panel.installation)
    return panel.user_id == user.id


def can_inspect_panel(user, panel: Panel) -> bool:
    """Customers can inspect owned panels; assigned technicians can inspect. Retired panels cannot be inspected."""
    if panel.status == 'retired':
        return False
    return can_view_panel(user, panel)


def can_view_inspection(user, inspection: Inspection) -> bool:
    if not user.is_authenticated:
        return False
    if is_admin(user):
        return True
    if inspection.panel:
        return can_view_panel(user, inspection.panel)
    return inspection.user_id == user.id


def can_verify_inspection(user, inspection: Inspection) -> bool:
    """Only admins or technicians assigned to the panel's installation can verify."""
    if not user.is_authenticated:
        return False
    if is_admin(user):
        return True
    if is_technician(user) and inspection.panel and inspection.panel.installation:
        return inspection.panel.installation.assigned_technician_id == user.id
    return False


def can_view_issue(user, issue: MaintenanceIssue) -> bool:
    if not user.is_authenticated:
        return False
    if is_admin(user):
        return True
    if is_technician(user):
        return issue.assigned_technician_id == user.id
    # Customer
    if issue.installation:
        return issue.installation.owner_id == user.id
    if issue.panel and issue.panel.installation:
        return issue.panel.installation.owner_id == user.id
    return issue.user_id == user.id


def can_update_issue(user, issue: MaintenanceIssue) -> bool:
    """Only assigned technicians or administrators can update issue status or log actions."""
    if not user.is_authenticated:
        return False
    if is_admin(user):
        return True
    if is_technician(user):
        return issue.assigned_technician_id == user.id
    return False


def can_assign_technician(user) -> bool:
    """Only admins can assign or reassign technicians to installations and work orders."""
    return is_admin(user)


def can_verify_layout(user, layout_revision: LayoutRevision) -> bool:
    """
    CRITICAL RULE: Customers CANNOT approve or verify their own layout revisions.
    Only an Admin or the explicitly assigned Technician can verify or request changes.
    """
    if not user.is_authenticated:
        return False
    if is_admin(user):
        return True
    if is_technician(user):
        return layout_revision.installation.assigned_technician_id == user.id
    return False


def can_submit_layout(user, layout_revision: LayoutRevision) -> bool:
    """Owners, assigned technicians, and admins can submit layouts for verification."""
    if not user.is_authenticated:
        return False
    if is_admin(user):
        return True
    if is_technician(user):
        return layout_revision.installation.assigned_technician_id == user.id
    return layout_revision.installation.owner_id == user.id


# ============================================================================
# View Decorators
# ============================================================================

def admin_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not is_admin(request.user):
            messages.error(request, "Access Denied: Administrator privileges are required to perform this action.")
            return HttpResponseForbidden("Access Denied: Administrator privileges required.")
        return view_func(request, *args, **kwargs)
    return _wrapped


def technician_or_admin_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not (is_admin(request.user) or is_technician(request.user)):
            messages.error(request, "Access Denied: Certified technician or administrator credentials required.")
            return HttpResponseForbidden("Access Denied: Technician or Administrator credentials required.")
        return view_func(request, *args, **kwargs)
    return _wrapped
