import json
import os
import datetime
from decimal import Decimal
import mimetypes
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from django.http import HttpResponseForbidden, FileResponse, Http404, JsonResponse, HttpResponse

from .models import (
    Installation, Panel, Inspection, MaintenanceIssue, MaintenanceLog,
    LayoutRevision, UserProfile, PaymentTransaction, Notification
)
from .notification_service import notify_user, notify_admins
from .pdf_reports import (
    generate_panel_report_pdf, generate_installation_report_pdf, generate_maintenance_report_pdf
)
from .payment_service import (
    is_razorpay_configured, get_razorpay_public_key, create_order_for_issue,
    verify_razorpay_payment_signature, record_payment_cancellation
)
from .pdf_receipt import generate_payment_receipt_pdf
from .forms import (
    InstallationForm, TechnicianAssignForm, PanelForm, InspectionForm,
    MaintenanceIssueForm, MaintenanceActionForm, AdminTechnicianAssignForm,
    TechnicianResolutionForm, LayoutReviewForm
)
from .permissions import (
    get_user_role, is_admin, is_technician, is_customer,
    get_accessible_installations, get_accessible_panels, get_accessible_inspections,
    get_accessible_maintenance_issues, get_accessible_layout_revisions,
    can_view_installation, can_edit_installation, can_view_panel, can_inspect_panel,
    can_view_inspection, can_verify_inspection, can_view_issue, can_update_issue,
    can_assign_technician, can_verify_layout, can_submit_layout,
    admin_required, technician_or_admin_required
)
from .layout_service import (
    get_or_create_draft_revision, save_draft_layout, submit_draft_for_verification,
    cancel_draft_revision, apply_approved_layout, generate_rectangular_grid, generate_next_panel_id
)
from ml_engine.predictor import predict_fault, predict_degradation
from ml_engine.inference import evaluate_prediction_uncertainty, run_cnn_inference


def get_user_panels_qs(user):
    """
    Backward-compatible helper linking to RBAC service get_accessible_panels.
    """
    return get_accessible_panels(user)


@login_required
def dashboard_view(request):
    """
    Role-Based Dashboard View for SolarGuard:
    - Customer Dashboard: "My Solar Systems" (simplified, rooftop 2D map, Digital Passport links, real condition triage)
    - Technician Dashboard: "My Assigned Work" (assigned sites, layout verification queue, assigned work orders, AI reviews)
    - Admin Dashboard: "SolarGuard Overview" (system installations, attention triage, layout queue, unassigned tickets)
    All metrics reflect actual database records with zero fabricated percentages or imaginary generation telemetry.
    Uninspected panels are never counted as healthy/normal. Retired panels are excluded from active totals.
    """
    user_role = get_user_role(request.user)
    is_admin_user = is_admin(request.user)
    is_tech_user = is_technician(request.user)
    is_cust_user = is_customer(request.user)
    current_date_str = datetime.date.today().strftime("%b %d, %Y")

    context = {
        'user_role': user_role,
        'is_admin': is_admin_user,
        'is_technician': is_tech_user,
        'is_customer': is_cust_user,
        'current_date_str': current_date_str,
    }

    if is_cust_user:
        # Customer View: "My Solar Systems"
        installations_qs = get_accessible_installations(request.user).prefetch_related('panels', 'layout_revisions')
        total_installations = installations_qs.count()

        # Selection of active installation
        selected_inst_id = request.GET.get('installation_id')
        selected_installation = None
        if selected_inst_id:
            try:
                selected_installation = installations_qs.filter(id=int(selected_inst_id)).first()
            except (ValueError, TypeError):
                selected_installation = None
        if not selected_installation and total_installations > 0:
            selected_installation = installations_qs.first()

        # Active panels across customer's installations (exclude retired)
        active_panels_qs = get_accessible_panels(request.user).filter(status='active').select_related('installation').prefetch_related('inspections')
        total_active_panels = active_panels_qs.count()

        not_inspected_count = 0
        normal_count = 0
        cleaning_count = 0
        damage_count = 0
        review_count = 0
        attention_panels = []

        for p in active_panels_qs:
            cond = p.get_derived_condition()
            st = cond['status']
            if st == 'not_inspected':
                not_inspected_count += 1
            elif st == 'normal':
                normal_count += 1
            elif st in ('dust', 'bird'):
                cleaning_count += 1
                attention_panels.append({'panel': p, 'condition': cond})
            elif st == 'damage':
                damage_count += 1
                attention_panels.append({'panel': p, 'condition': cond})
            elif st == 'review':
                review_count += 1
                attention_panels.append({'panel': p, 'condition': cond})

        attention_count = len(attention_panels)

        # Open maintenance requests for this customer
        open_issues_qs = get_accessible_maintenance_issues(request.user).filter(
            status__in=['Open', 'Assigned', 'In Progress']
        ).select_related('panel', 'installation').order_by('-created_at')
        open_issues_count = open_issues_qs.count()
        recent_open_issues = open_issues_qs[:5]

        # Recent inspections for this customer
        recent_inspections = get_accessible_inspections(request.user).select_related(
            'panel', 'panel__installation'
        ).order_by('-inspected_at')[:5]

        # 2D Rooftop Health Map for selected installation
        grid_matrix = []
        selected_inst_stats = {
            'total': 0,
            'not_inspected': 0,
            'normal': 0,
            'cleaning': 0,
            'damage': 0,
            'review': 0,
        }
        pending_layout = None
        draft_layout = None

        if selected_installation:
            pending_layout = selected_installation.layout_revisions.filter(status='pending_verification').order_by('-version_number').first()
            draft_layout = selected_installation.layout_revisions.filter(status__in=['draft', 'changes_requested']).order_by('-version_number').first()

            inst_panels = list(selected_installation.panels.prefetch_related('inspections'))
            panel_obj_map = {p.permanent_id: p for p in inst_panels if p.permanent_id}
            for p in inst_panels:
                if p.serial_number and p.serial_number not in panel_obj_map:
                    panel_obj_map[p.serial_number] = p

            for p in inst_panels:
                if p.status == 'active':
                    selected_inst_stats['total'] += 1
                    c_st = p.get_derived_condition()['status']
                    if c_st == 'not_inspected':
                        selected_inst_stats['not_inspected'] += 1
                    elif c_st == 'normal':
                        selected_inst_stats['normal'] += 1
                    elif c_st in ('dust', 'bird'):
                        selected_inst_stats['cleaning'] += 1
                    elif c_st == 'damage':
                        selected_inst_stats['damage'] += 1
                    elif c_st == 'review':
                        selected_inst_stats['review'] += 1

            active_layout = selected_installation.active_layout
            if active_layout and active_layout.layout_data and 'active_cells' in active_layout.layout_data:
                rows = active_layout.grid_rows
                cols = active_layout.grid_cols
                cells_map = {(c['row'], c['col']): c for c in active_layout.layout_data.get('active_cells', [])}

                for r in range(1, rows + 1):
                    row_items = []
                    for c in range(1, cols + 1):
                        cell = cells_map.get((r, c))
                        if cell:
                            pid = cell.get('panel_id')
                            panel_obj = panel_obj_map.get(pid)
                            is_retired = False
                            if panel_obj:
                                is_retired = (panel_obj.status == 'retired')
                                derived = panel_obj.get_derived_condition()
                            else:
                                derived = {
                                    'status': 'not_inspected',
                                    'category': 'Not Inspected',
                                    'label': 'Not Inspected',
                                    'badge_class': 'bg-secondary bg-opacity-75 text-white',
                                    'tile_bg': 'linear-gradient(145deg, #2A333E, #384556)',
                                    'tile_border': '#4B5A6E',
                                    'inspection': None
                                }

                            row_items.append({
                                'is_empty': False,
                                'row': r,
                                'col': c,
                                'panel_id': pid,
                                'serial_number': cell.get('serial_number') or pid,
                                'condition': derived['label'],
                                'category': derived.get('category', 'Not Inspected'),
                                'status': derived['status'],
                                'badge_class': derived['badge_class'],
                                'tile_bg': derived.get('tile_bg', 'linear-gradient(145deg, #2A333E, #384556)'),
                                'tile_border': derived.get('tile_border', '#4B5A6E'),
                                'panel_db_id': panel_obj.id if panel_obj else None,
                                'inspection_id': derived['inspection'].id if derived.get('inspection') else None,
                                'is_retired': is_retired,
                            })
                        else:
                            row_items.append({
                                'is_empty': True,
                                'row': r,
                                'col': c,
                            })
                    grid_matrix.append(row_items)

        context.update({
            'total_installations': total_installations,
            'customer_installations': installations_qs,
            'selected_installation': selected_installation,
            'total_panels': total_active_panels,
            'total_active_panels': total_active_panels,
            'not_inspected_count': not_inspected_count,
            'normal_count': normal_count,
            'cleaning_count': cleaning_count,
            'damage_count': damage_count,
            'review_count': review_count,
            'attention_count': attention_count,
            'attention_panels': attention_panels[:6],
            'open_issues_count': open_issues_count,
            'open_issues': recent_open_issues,
            'recent_inspections': recent_inspections,
            'total_inspections': recent_inspections.count(),
            'grid_matrix': grid_matrix,
            'selected_inst_stats': selected_inst_stats,
            'pending_layout': pending_layout,
            'draft_layout': draft_layout,
            'pending_layouts_count': 1 if pending_layout else 0,
        })

    elif is_tech_user:
        # Technician View: "My Assigned Work"
        assigned_installations = get_accessible_installations(request.user).prefetch_related('panels', 'layout_revisions')
        assigned_installations_count = assigned_installations.count()

        # Layouts awaiting verification
        pending_layouts = get_accessible_layout_revisions(request.user).filter(
            status='pending_verification'
        ).select_related('installation', 'installation__owner').order_by('-created_at')
        pending_layouts_count = pending_layouts.count()

        # Assigned maintenance tasks (active)
        assigned_tasks = get_accessible_maintenance_issues(request.user).filter(
            assigned_technician=request.user,
            status__in=['Assigned', 'In Progress']
        ).select_related('panel', 'installation', 'installation__owner').order_by('-created_at')
        assigned_tasks_count = assigned_tasks.count()

        # Unverified AI inspections needing technician review
        unverified_inspections = get_accessible_inspections(request.user).filter(
            review_status='ai_predicted'
        ).select_related('panel', 'panel__installation', 'user').order_by('-inspected_at')
        unverified_inspections_count = unverified_inspections.count()

        # Assigned panels condition triage
        assigned_panels = get_accessible_panels(request.user).filter(status='active').select_related('installation').prefetch_related('inspections')
        attention_panels = []
        for p in assigned_panels:
            cond = p.get_derived_condition()
            if cond['status'] in ('dust', 'bird', 'damage', 'review'):
                attention_panels.append({'panel': p, 'condition': cond})

        context.update({
            'total_installations': assigned_installations_count,
            'assigned_installations_count': assigned_installations_count,
            'assigned_installations': assigned_installations[:8],
            'pending_layouts_count': pending_layouts_count,
            'pending_layouts': pending_layouts[:8],
            'assigned_tasks_count': assigned_tasks_count,
            'assigned_tasks': assigned_tasks[:8],
            'unverified_inspections_count': unverified_inspections_count,
            'unverified_inspections': unverified_inspections[:8],
            'attention_panels': attention_panels[:8],
            'attention_count': len(attention_panels),
            'total_panels': assigned_panels.count(),
            'open_issues_count': assigned_tasks_count,
        })

    else:
        # Admin View: "SolarGuard Overview"
        total_installations = Installation.objects.count()
        all_active_panels = Panel.objects.filter(status='active').select_related('installation').prefetch_related('inspections')
        total_active_panels = all_active_panels.count()

        not_inspected_count = 0
        normal_count = 0
        cleaning_count = 0
        damage_count = 0
        review_count = 0
        attention_panels = []

        for p in all_active_panels:
            cond = p.get_derived_condition()
            st = cond['status']
            if st == 'not_inspected':
                not_inspected_count += 1
            elif st == 'normal':
                normal_count += 1
            elif st in ('dust', 'bird'):
                cleaning_count += 1
                attention_panels.append({'panel': p, 'condition': cond})
            elif st == 'damage':
                damage_count += 1
                attention_panels.append({'panel': p, 'condition': cond})
            elif st == 'review':
                review_count += 1
                attention_panels.append({'panel': p, 'condition': cond})

        attention_count = len(attention_panels)

        # Queues
        layout_queue = LayoutRevision.objects.filter(status='pending_verification').select_related(
            'installation', 'installation__owner'
        ).order_by('-created_at')
        layout_queue_count = layout_queue.count()

        unassigned_issues = MaintenanceIssue.objects.filter(
            assigned_technician__isnull=True,
            status='Open'
        ).select_related('panel', 'installation', 'installation__owner').order_by('-created_at')
        unassigned_issues_count = unassigned_issues.count()

        active_work_orders = MaintenanceIssue.objects.filter(
            status__in=['Assigned', 'In Progress']
        ).select_related('panel', 'installation', 'assigned_technician').order_by('-updated_at')
        active_work_orders_count = active_work_orders.count()

        unallocated_installations = Installation.objects.filter(
            assigned_technician__isnull=True
        ).select_related('owner').order_by('-created_at')
        unallocated_count = unallocated_installations.count()

        # Historical inspection stats (explicitly labeled historical)
        total_historical_inspections = Inspection.objects.count()
        hist_counts = Inspection.objects.values('predicted_class').annotate(count=Count('id')).order_by('-count')
        chart_labels = [item['predicted_class'] for item in hist_counts]
        chart_data = [item['count'] for item in hist_counts]

        context.update({
            'total_installations': total_installations,
            'total_panels': total_active_panels,
            'total_active_panels': total_active_panels,
            'not_inspected_count': not_inspected_count,
            'normal_count': normal_count,
            'cleaning_count': cleaning_count,
            'damage_count': damage_count,
            'review_count': review_count,
            'attention_count': attention_count,
            'attention_panels': attention_panels[:8],
            'layout_queue_count': layout_queue_count,
            'layout_queue': layout_queue[:8],
            'pending_layouts_count': layout_queue_count,
            'unassigned_issues_count': unassigned_issues_count,
            'unassigned_issues': unassigned_issues[:8],
            'active_work_orders_count': active_work_orders_count,
            'active_work_orders': active_work_orders[:8],
            'open_issues_count': unassigned_issues_count + active_work_orders_count,
            'unallocated_count': unallocated_count,
            'unallocated_installations': unallocated_installations[:8],
            'total_historical_inspections': total_historical_inspections,
            'chart_labels_json': json.dumps(chart_labels),
            'chart_data_json': json.dumps(chart_data),
        })

    return render(request, 'core/dashboard.html', context)


# ============================================================================
# Installations Management Views (RBAC Protected)
# ============================================================================

@login_required
def installation_list_view(request):
    """
    List view of solar installations accessible to current user:
    - Customer: Own installations
    - Technician: Assigned installations
    - Admin: All installations
    """
    installations = get_accessible_installations(request.user).prefetch_related('panels', 'layout_revisions')
    return render(request, 'core/installation_list.html', {
        'installations': installations,
        'user_role': get_user_role(request.user),
    })


@login_required
def installation_detail_view(request, pk):
    """
    Detailed installation overview showing site address, verification state,
    active layout, interactive 2D panel health map, and open tickets.
    Enforces object-level permission check.
    """
    installation = get_object_or_404(Installation, pk=pk)
    if not can_view_installation(request.user, installation):
        return HttpResponseForbidden("Access Denied: You do not have permission to view this solar installation.")

    panels = installation.panels.all().order_by('permanent_id')
    revisions = installation.layout_revisions.all().order_by('-version_number')
    active_layout = installation.active_layout
    draft_revision = installation.layout_revisions.filter(status__in=['draft', 'changes_requested']).order_by('-version_number').first()
    pending_revision = installation.layout_revisions.filter(status='pending_verification').order_by('-version_number').first()
    issues = installation.maintenance_issues.all().order_by('-created_at')

    # Build active 2D layout matrix if active layout exists
    grid_matrix = []
    if active_layout and active_layout.layout_data and 'active_cells' in active_layout.layout_data:
        rows = active_layout.grid_rows
        cols = active_layout.grid_cols
        
        # Build map of (row, col) -> cell data
        cells_map = {(c['row'], c['col']): c for c in active_layout.layout_data.get('active_cells', [])}
        
        # Build map of panel permanent_id -> Panel model object
        panel_obj_map = {p.permanent_id: p for p in panels if p.permanent_id}
        for p in panels:
            if p.serial_number and p.serial_number not in panel_obj_map:
                panel_obj_map[p.serial_number] = p

        for r in range(1, rows + 1):
            row_items = []
            for c in range(1, cols + 1):
                cell = cells_map.get((r, c))
                if cell:
                    pid = cell.get('panel_id')
                    panel_obj = panel_obj_map.get(pid)
                    condition = 'Not Inspected'
                    badge_class = 'bg-light text-muted border'
                    inspection_id = None
                    panel_db_id = panel_obj.id if panel_obj else None
                    is_retired = False

                    if panel_obj:
                        derived = panel_obj.get_derived_condition()
                        condition = derived['label']
                        badge_class = derived['badge_class']
                        is_retired = (panel_obj.status == 'retired')
                        if derived['inspection']:
                            inspection_id = derived['inspection'].id

                    row_items.append({
                        'is_empty': False,
                        'row': r,
                        'col': c,
                        'panel_id': pid,
                        'serial_number': cell.get('serial_number') or pid,
                        'condition': condition,
                        'badge_class': badge_class,
                        'panel_db_id': panel_db_id,
                        'inspection_id': inspection_id,
                        'is_retired': is_retired,
                    })
                else:
                    row_items.append({
                        'is_empty': True,
                        'row': r,
                        'col': c,
                    })
            grid_matrix.append(row_items)

    # Admin technician assignment form
    tech_form = None
    if is_admin(request.user):
        tech_form = TechnicianAssignForm(initial={'technician': installation.assigned_technician})

    can_edit = can_edit_installation(request.user, installation)
    can_verify = False
    target_rev_for_verify = pending_revision or (active_layout if active_layout and active_layout.status != 'verified' else None)
    if target_rev_for_verify and can_verify_layout(request.user, target_rev_for_verify):
        can_verify = True

    return render(request, 'core/installation_detail.html', {
        'installation': installation,
        'panels': panels,
        'revisions': revisions,
        'active_layout': active_layout,
        'draft_revision': draft_revision,
        'pending_revision': pending_revision,
        'target_rev_for_verify': target_rev_for_verify,
        'grid_matrix': grid_matrix,
        'issues': issues,
        'tech_form': tech_form,
        'can_assign_tech': can_assign_technician(request.user),
        'can_edit_layout': can_edit,
        'can_verify_layout': can_verify,
        'is_admin_user': is_admin(request.user),
        'is_technician_user': is_technician(request.user),
    })


@login_required
def installation_add_view(request):
    """
    Customer / Admin guided Add Installation view.
    Technicians cannot self-register new installations.
    Guides customer directly to Step 2: Arrange panels upon creation.
    """
    if is_technician(request.user):
        return HttpResponseForbidden("Access Denied: Technicians cannot register new installations. Only customers or administrators may add installations.")

    if request.method == 'POST':
        form = InstallationForm(request.POST, request.FILES)
        if form.is_valid():
            inst = form.save(commit=False)
            inst.owner = request.user
            inst.status = 'active'
            inst.save()

            # Trigger notification for administrators
            notify_admins(
                event_type='new_installation',
                title=f"New Installation: {inst.name}",
                message=f"Customer {request.user.username} submitted new installation '{inst.name}' ({inst.site_address}).",
                target_url=reverse('installation_detail', kwargs={'pk': inst.pk}),
                exclude_user=request.user
            )

            messages.success(request, f"Solar Installation '{inst.name}' created! Step 2: Now arrange your solar panel layout.")
            return redirect(f"{reverse('layout_builder', kwargs={'pk': inst.pk})}?setup=1")
    else:
        form = InstallationForm()

    return render(request, 'core/installation_form.html', {'form': form})


@login_required
@admin_required
def installation_assign_tech_view(request, pk):
    """
    Admin-only action to assign or reassign a certified technician to an installation.
    Validates strictly server-side that the selected user is a Technician.
    """
    installation = get_object_or_404(Installation, pk=pk)

    if request.method == 'POST':
        form = TechnicianAssignForm(request.POST)
        if form.is_valid():
            selected_tech = form.cleaned_data['technician']
            installation.assigned_technician = selected_tech
            installation.save(update_fields=['assigned_technician', 'updated_at'])
            tech_name = selected_tech.username if selected_tech else "Unassigned"

            # Notify Technician
            if selected_tech and selected_tech != request.user:
                notify_user(
                    recipient=selected_tech,
                    event_type='installation_assigned',
                    title=f"Assigned to Solar Site: {installation.name}",
                    message=f"You have been allocated as certified technician for site '{installation.name}'.",
                    target_url=reverse('installation_detail', kwargs={'pk': installation.pk})
                )

            # Notify Customer / Owner
            if installation.owner and installation.owner != request.user:
                notify_user(
                    recipient=installation.owner,
                    event_type='installation_assigned',
                    title=f"Technician Assigned: {installation.name}",
                    message=f"Certified technician {tech_name} has been assigned to your solar site '{installation.name}'.",
                    target_url=reverse('installation_detail', kwargs={'pk': installation.pk})
                )

            messages.success(request, f"Technician assignment updated to '{tech_name}' for {installation.name}.")
            return redirect('installation_detail', pk=installation.pk)
        else:
            messages.error(request, "Failed to update technician assignment: invalid selection.")

    return redirect('installation_detail', pk=installation.pk)


# ============================================================================
# Layout Builder Views (Phase 4 Custom 2D Grid Builder)
# ============================================================================

@login_required
def layout_builder_view(request, pk):
    """
    Interactive 2D solar panel layout builder.
    Supports rectangular and irregular (e.g. 4-3-4) module placement,
    click-to-select, click-to-place, stable immutable panel IDs,
    safe module removal, preview mode, and draft saving.
    """
    installation = get_object_or_404(Installation, pk=pk)
    if not can_view_installation(request.user, installation):
        return HttpResponseForbidden("Access Denied: You do not have permission to view this solar installation.")

    can_edit = can_edit_installation(request.user, installation)
    can_verify = False

    revision_id = request.GET.get('revision')
    revision = None
    if revision_id:
        revision = installation.layout_revisions.filter(id=revision_id).first()

    if not revision:
        if can_edit:
            revision, _ = get_or_create_draft_revision(installation, request.user)
        else:
            revision = installation.layout_revisions.filter(status='pending_verification').order_by('-version_number').first() or installation.active_layout

    if revision:
        can_verify = can_verify_layout(request.user, revision)

    # Physical panels currently registered for this installation
    panels_qs = installation.panels.all().order_by('permanent_id')
    existing_panels = [
        {
            'id': p.id,
            'permanent_id': p.permanent_id or p.serial_number,
            'serial_number': p.serial_number,
            'status': p.status,
            'grid_row': p.grid_row,
            'grid_col': p.grid_col,
            'condition': p.latest_inspection.predicted_class if p.latest_inspection else 'Not Inspected'
        }
        for p in panels_qs
    ]

    layout_data = revision.layout_data if (revision and revision.layout_data) else {
        'rows': revision.grid_rows if revision else 3,
        'cols': revision.grid_cols if revision else 4,
        'active_cells': []
    }

    next_panel_id = generate_next_panel_id(installation)
    is_setup = request.GET.get('setup') == '1'

    return render(request, 'core/layout_builder.html', {
        'installation': installation,
        'revision': revision,
        'active_layout': installation.active_layout,
        'can_edit': can_edit,
        'can_verify': can_verify,
        'is_setup': is_setup,
        'existing_panels_json': json.dumps(existing_panels),
        'initial_layout_json': json.dumps(layout_data),
        'next_panel_id': next_panel_id,
        'is_admin': is_admin(request.user),
        'is_technician': is_technician(request.user),
    })


@login_required
def layout_save_draft_view(request, pk):
    """
    Saves draft layout grid dimensions and placed modules.
    Safe: Does not alter live panel coordinates or active verified layouts.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST method required.'}, status=405)

    installation = get_object_or_404(Installation, pk=pk)
    if not can_edit_installation(request.user, installation):
        return JsonResponse({'success': False, 'error': 'Access Denied: You cannot edit this installation.'}, status=403)

    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body.decode('utf-8'))
        else:
            data = json.loads(request.POST.get('layout_data', '{}'))
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Invalid JSON payload: {str(e)}'}, status=400)

    rows = data.get('rows', 3)
    cols = data.get('cols', 4)
    active_cells = data.get('active_cells', [])

    try:
        rows = int(rows)
        cols = int(cols)
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'error': 'Grid rows and columns must be integers.'}, status=400)

    draft, _ = get_or_create_draft_revision(installation, request.user)
    success, err = save_draft_layout(draft, rows, cols, active_cells, request.user)
    if not success:
        return JsonResponse({'success': False, 'error': err}, status=400)

    return JsonResponse({
        'success': True,
        'message': f"Draft v{draft.version_number} saved successfully ({len(active_cells)} panels placed).",
        'version_number': draft.version_number,
        'panel_count': len(active_cells),
    })


@login_required
def layout_submit_view(request, pk):
    """
    Submits a draft layout revision for technician/admin verification.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST method required.'}, status=405)

    installation = get_object_or_404(Installation, pk=pk)
    draft = installation.layout_revisions.filter(
        status__in=['draft', 'changes_requested']
    ).order_by('-version_number').first()

    if not draft:
        if can_edit_installation(request.user, installation):
            draft, _ = get_or_create_draft_revision(installation, request.user)
        else:
            return JsonResponse({'success': False, 'error': 'No draft layout found to submit.'}, status=404)

    if not can_submit_layout(request.user, draft):
        return JsonResponse({'success': False, 'error': 'Access Denied: You cannot submit this layout.'}, status=403)

    # Optional payload sync before submit
    if request.body:
        try:
            if request.content_type == 'application/json':
                data = json.loads(request.body.decode('utf-8'))
            else:
                data = json.loads(request.POST.get('layout_data', '{}'))
            if data and 'active_cells' in data:
                rows = int(data.get('rows', draft.grid_rows))
                cols = int(data.get('cols', draft.grid_cols))
                save_draft_layout(draft, rows, cols, data['active_cells'], request.user)
        except Exception:
            pass

    success, err = submit_draft_for_verification(draft, request.user)
    if not success:
        if request.content_type == 'application/json' or request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': err}, status=400)
        messages.error(request, f"Submission error: {err}")
        return redirect('layout_builder', pk=pk)

    # Notify Administrators of layout review request
    notify_admins(
        event_type='layout_review_requested',
        title=f"Layout Review: {installation.name} (v{draft.version_number})",
        message=f"Customer {request.user.username} submitted Layout Revision v{draft.version_number} for verification.",
        target_url=reverse('layout_builder', kwargs={'pk': pk}),
        exclude_user=request.user
    )
    if installation.assigned_technician and installation.assigned_technician != request.user:
        notify_user(
            recipient=installation.assigned_technician,
            event_type='layout_review_requested',
            title=f"Layout Review: {installation.name} (v{draft.version_number})",
            message=f"Layout revision v{draft.version_number} for site '{installation.name}' is waiting for verification.",
            target_url=reverse('layout_builder', kwargs={'pk': pk})
        )

    messages.success(request, f"Layout Revision v{draft.version_number} submitted for technician verification!")
    redirect_url = reverse('installation_detail', kwargs={'pk': pk})
    if request.content_type == 'application/json' or request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'redirect_url': redirect_url})
    return redirect(redirect_url)


@login_required
def layout_cancel_view(request, pk):
    """
    Cancels draft editing and discards unverified draft changes.
    The active verified layout remains completely intact.
    """
    if request.method != 'POST':
        return HttpResponseForbidden("POST method required to cancel draft.")

    installation = get_object_or_404(Installation, pk=pk)
    if not can_edit_installation(request.user, installation):
        return HttpResponseForbidden("Permission denied.")

    draft = installation.layout_revisions.filter(
        status__in=['draft', 'changes_requested']
    ).order_by('-version_number').first()

    if draft:
        cancel_draft_revision(draft, request.user)
        messages.info(request, "Draft layout revision discarded. Your active layout remains untouched.")
    else:
        messages.info(request, "No draft layout found to cancel.")

    return redirect('installation_detail', pk=pk)


@login_required
def layout_generate_rectangular_view(request, pk):
    """
    Automatically generates a rectangular panel arrangement for the current draft revision.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST method required.'}, status=405)

    installation = get_object_or_404(Installation, pk=pk)
    if not can_edit_installation(request.user, installation):
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)

    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body.decode('utf-8'))
        else:
            data = request.POST
        rows = int(data.get('rows', 3))
        cols = int(data.get('cols', 4))
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({'success': False, 'error': 'Invalid rows or cols parameters.'}, status=400)

    if rows < 1 or rows > 30 or cols < 1 or cols > 30:
        return JsonResponse({'success': False, 'error': 'Grid rows and columns must be between 1 and 30.'}, status=400)

    draft, _ = get_or_create_draft_revision(installation, request.user)
    updated_draft = generate_rectangular_grid(draft, rows, cols, request.user)

    return JsonResponse({
        'success': True,
        'message': f"Generated {rows}x{cols} rectangular layout ({rows * cols} panels).",
        'layout_data': updated_draft.layout_data,
        'version_number': updated_draft.version_number
    })


@login_required
def layout_verify_view(request, pk):
    """
    Technician / Admin action to verify or request changes on a layout revision.
    Customers attempting to approve their own layouts receive HTTP 403 Forbidden.
    Applies live panel coordinates atomically upon approval.
    """
    revision = get_object_or_404(LayoutRevision.objects.select_related('installation'), pk=pk)

    if not can_verify_layout(request.user, revision):
        return HttpResponseForbidden("Access Denied: Only certified technicians or administrators can verify layout revisions.")

    if request.method == 'POST':
        form = LayoutReviewForm(request.POST)
        if form.is_valid():
            new_status = form.cleaned_data['status']
            notes = form.cleaned_data['review_notes']

            if new_status == 'verified':
                success, err = apply_approved_layout(revision, request.user, notes)
                if not success:
                    messages.error(request, f"Verification failed: {err}")
                    return render(request, 'core/layout_review_form.html', {
                        'revision': revision,
                        'installation': revision.installation,
                        'form': form,
                    })

                # Notify Customer of Layout Approval
                if revision.installation.owner and revision.installation.owner != request.user:
                    notify_user(
                        recipient=revision.installation.owner,
                        event_type='layout_verified',
                        title=f"Layout Approved: {revision.installation.name}",
                        message=f"Layout revision v{revision.version_number} has been verified and applied to your solar array.",
                        target_url=reverse('installation_detail', kwargs={'pk': revision.installation_id})
                    )

                messages.success(request, f"Layout revision v{revision.version_number} verified and applied to live installation array!")
            else:
                revision.status = 'changes_requested'
                revision.reviewed_by = request.user
                revision.reviewed_at = timezone.now()
                revision.review_notes = notes
                revision.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_notes', 'updated_at'])

                # Notify Customer of Layout Changes Requested
                if revision.installation.owner and revision.installation.owner != request.user:
                    notify_user(
                        recipient=revision.installation.owner,
                        event_type='layout_rejected',
                        title=f"Layout Changes Requested: {revision.installation.name}",
                        message=f"Reviewer {request.user.username} requested adjustments on revision v{revision.version_number}: {notes[:100]}",
                        target_url=reverse('layout_builder', kwargs={'pk': revision.installation_id})
                    )

                messages.warning(request, f"Layout revision v{revision.version_number} marked as Changes Requested. Homeowner notified.")

            return redirect('installation_detail', pk=revision.installation_id)
    else:
        form = LayoutReviewForm(initial={'status': 'verified', 'review_notes': revision.review_notes})

    return render(request, 'core/layout_review_form.html', {
        'revision': revision,
        'installation': revision.installation,
        'form': form,
    })


# ============================================================================
# Panels Inventory Views (RBAC Scoped)
# ============================================================================

@login_required
def panel_list_view(request):
    """
    List view of solar panels accessible to current user.
    """
    panels = get_accessible_panels(request.user).select_related('installation').prefetch_related('inspections', 'issues')
    return render(request, 'core/panel_list.html', {
        'panels': panels,
        'user_role': get_user_role(request.user),
    })


@login_required
def panel_add_view(request):
    """
    Add Panel view.
    Validates that the target installation is accessible to the user.
    """
    if is_technician(request.user):
        return HttpResponseForbidden("Access Denied: Technicians cannot register new panels directly.")

    if request.method == 'POST':
        form = PanelForm(request.POST, user=request.user)
        if form.is_valid():
            panel = form.save(commit=False)
            panel.user = request.user
            # Ensure installation ownership if installation is provided
            if panel.installation and not can_view_installation(request.user, panel.installation):
                return HttpResponseForbidden("Access Denied: You cannot add a panel to an installation you do not own.")
            panel.save()
            messages.success(request, f"Solar Panel '{panel.serial_number}' registered successfully!")
            return redirect('panel_list')
    else:
        form = PanelForm(user=request.user)

    return render(request, 'core/panel_form.html', {'form': form})


@login_required
def panel_detail_view(request, pk):
    """
    Panel Digital Passport View (/panels/<pk>/).
    Database-backed detail page showing permanent ID, layout coordinates, active/retired status,
    latest derived condition, latest inspection photograph, inspection history, and linked maintenance issues.
    Enforces object-level access checks (customer owner, assigned technician, or admin).
    No fabricated health metrics, live sensor telemetry, or synthetic power generation curves.
    """
    panel = get_object_or_404(
        Panel.objects.select_related('installation', 'installation__owner', 'installation__assigned_technician'),
        pk=pk
    )

    if not can_view_panel(request.user, panel):
        return HttpResponseForbidden("Access Denied: You do not have permission to view this panel passport.")

    derived_condition = panel.get_derived_condition()
    latest_inspection = derived_condition['inspection']

    inspections_history = panel.inspections.select_related('user', 'reviewed_by').order_by('-inspected_at')
    issues = panel.issues.select_related('user', 'assigned_technician').order_by('-created_at')

    can_inspect = can_inspect_panel(request.user, panel)

    context = {
        'panel': panel,
        'derived_condition': derived_condition,
        'latest_inspection': latest_inspection,
        'inspections_history': inspections_history,
        'issues': issues,
        'can_inspect': can_inspect,
        'user_role': get_user_role(request.user),
    }
    return render(request, 'core/panel_detail.html', context)


# ============================================================================
# Inspection Views (RBAC Scoped)
# ============================================================================

@login_required
def inspect_view(request):
    """
    Image inspection upload view.
    Validates upload, runs visual condition classification and deterministic rules priority engine.
    Strictly verifies object-level permissions on target panel and prevents inspection of retired panels.
    """
    panels_qs = get_accessible_panels(request.user).exclude(status='retired')

    if not panels_qs.exists():
        messages.warning(
            request,
            "No active solar panels found for inspection. Please register an installation and panel first."
        )

    selected_panel = None
    initial_data = {}
    panel_id_param = request.GET.get('panel_id')
    if panel_id_param:
        try:
            candidate_panel = Panel.objects.select_related('installation').get(pk=panel_id_param)
            if can_inspect_panel(request.user, candidate_panel):
                selected_panel = candidate_panel
                initial_data['panel'] = candidate_panel.id
            else:
                if candidate_panel.status == 'retired':
                    messages.warning(
                        request,
                        f"Panel {candidate_panel.permanent_id or candidate_panel.serial_number} is retired and cannot be inspected."
                    )
                else:
                    messages.warning(request, "Selected panel is not accessible.")
        except (Panel.DoesNotExist, ValueError):
            messages.warning(request, "Requested panel does not exist.")

    if request.method == 'POST':
        # Early RBAC & Retired enforcement on raw posted panel ID
        raw_panel_id = request.POST.get('panel')
        if raw_panel_id:
            try:
                raw_panel = Panel.objects.get(pk=raw_panel_id)
                if not can_inspect_panel(request.user, raw_panel):
                    if raw_panel.status == 'retired':
                        return HttpResponseForbidden("Access Denied: Retired solar panels cannot be inspected.")
                    return HttpResponseForbidden("Access Denied: You do not have permission to inspect this panel.")
            except (Panel.DoesNotExist, ValueError):
                pass

        form = InspectionForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            panel = form.cleaned_data.get('panel')

            # Enforce panel inspection permission and active status
            if not can_inspect_panel(request.user, panel):
                if panel.status == 'retired':
                    return HttpResponseForbidden("Access Denied: Retired solar panels cannot be inspected.")
                return HttpResponseForbidden("Access Denied: You do not have permission to inspect this panel.")

            with transaction.atomic():
                inspection = form.save(commit=False)
                inspection.user = request.user
                inspection.predicted_class = "Analyzing..."
                inspection.confidence_score = 0.0
                inspection.degradation_probability = 0.0
                inspection.risk_category = "Low"
                inspection.save()

                # 1. Run Visual Condition Screening
                image_path = inspection.image.path
                fault_res = predict_fault(image_path)
                visual_finding = fault_res['predicted_class']

                # 2. Run Deterministic Rules Priority Engine
                deg_res = predict_degradation(panel, visual_finding=visual_finding)

                # Update record fields
                inspection.predicted_class = visual_finding
                inspection.confidence_score = fault_res['confidence_score']
                inspection.class_probabilities = fault_res.get('class_probabilities', {})
                inspection.degradation_probability = deg_res['degradation_probability']
                inspection.risk_category = deg_res['risk_category']
                inspection.maintenance_priority_score = deg_res.get('priority_score', 0)
                inspection.maintenance_priority_level = deg_res.get('priority_level', 'Unable to Assess')
                inspection.priority_explanation = deg_res.get('explanation_text', '')
                inspection.is_mock_prediction = fault_res.get('is_mock', False)
                inspection.model_identifier = fault_res.get('engine', 'MobileNetV2 CNN')

                # Part E & F: Enforce 60% confidence threshold and offline model review policy
                if (fault_res.get('status') in ('model_unavailable', 'unreadable') or
                    fault_res.get('is_uncertain') or
                    fault_res.get('is_low_confidence') or
                    fault_res.get('confidence_score', 0.0) < 60.0):
                    inspection.review_status = 'flagged'
                else:
                    inspection.review_status = 'ai_predicted'

                # Append engine metadata to notes
                engine_info = f"[Vision: {fault_res['engine']} | Priority: {deg_res['engine']}]"
                if fault_res.get('is_uncertain') or fault_res.get('is_low_confidence'):
                    engine_info += f" [Assessment Notice: {fault_res.get('experimental_note')}]"
                if inspection.notes:
                    inspection.notes = f"{inspection.notes}\n{engine_info}"
                else:
                    inspection.notes = engine_info

                inspection.save()

            if fault_res.get('status') == 'model_unavailable':
                messages.error(request, f"Model Unavailable: {fault_res.get('error_message')}")
            elif fault_res.get('status') == 'unreadable':
                messages.warning(request, f"Photo Quality Alert: {fault_res.get('error_message')}")
            else:
                panel_label = panel.permanent_id or panel.serial_number
                messages.success(request, f"Inspection completed for {panel_label}!")
            return redirect('result_detail', pk=inspection.pk)
        else:
            if not selected_panel and form.data.get('panel'):
                try:
                    p = Panel.objects.get(pk=form.data.get('panel'))
                    if can_inspect_panel(request.user, p):
                        selected_panel = p
                except (Panel.DoesNotExist, ValueError):
                    pass
    else:
        form = InspectionForm(user=request.user, initial=initial_data)

    context = {
        'form': form,
        'panels': panels_qs,
        'selected_panel': selected_panel,
    }
    return render(request, 'core/inspect.html', context)


@login_required
def result_view(request, pk):
    """
    Detailed Inspection Result view.
    Enforces object-level access check.
    Allows certified technicians to record verified findings and audit notes.
    Preserves original AI prediction alongside verified findings.
    """
    inspection = get_object_or_404(Inspection.objects.select_related('panel', 'panel__installation'), pk=pk)

    if not can_view_inspection(request.user, inspection):
        return HttpResponseForbidden("Access Denied: You do not have permission to view this inspection report.")

    panel = inspection.panel
    pred = inspection.predicted_class.lower()
    pri_level = inspection.maintenance_priority_level or inspection.risk_category
    pri_score = inspection.maintenance_priority_score or int(inspection.degradation_probability)

    # Technician verification action
    if request.method == 'POST' and request.POST.get('action') == 'verify_finding':
        if not can_verify_inspection(request.user, inspection):
            return HttpResponseForbidden("Access Denied: Only certified technicians assigned to this array or administrators can verify inspection findings.")
        verified_finding = request.POST.get('verified_finding', '').strip()
        review_notes = request.POST.get('review_notes', '').strip()
        if verified_finding:
            inspection.review_status = 'technician_verified'
            inspection.verified_outcome = verified_finding
            inspection.reviewed_by = request.user
            inspection.reviewed_at = timezone.now()
            inspection.review_notes = review_notes
            inspection.save(update_fields=['review_status', 'verified_outcome', 'reviewed_by', 'reviewed_at', 'review_notes'])
            messages.success(request, f"Technician verification recorded: '{verified_finding}'.")
            return redirect('result_detail', pk=inspection.pk)

    is_unavailable = ('unavailable' in pred or 'offline' in pred or 'failed' in pred or 
                      'error' in pred or 'unavailable' in (inspection.model_identifier or '').lower() or
                      (inspection.confidence_score == 0.0 and not inspection.class_probabilities))

    # If class_probabilities is missing in DB but image exists and model is active, populate live
    if not inspection.class_probabilities and inspection.image and not inspection.is_mock_prediction and not is_unavailable:
        try:
            if os.path.exists(inspection.image.path):
                live_res = run_cnn_inference(inspection.image.path)
                if live_res.get('status') == 'success' and live_res.get('class_probabilities'):
                    inspection.class_probabilities = live_res['class_probabilities']
                    inspection.save(update_fields=['class_probabilities'])
        except Exception:
            pass

    # Transparent rule-based uncertainty evaluation
    uncertainty_info = evaluate_prediction_uncertainty(
        class_probabilities=inspection.class_probabilities,
        predicted_class=inspection.predicted_class,
        confidence_score=inspection.confidence_score,
        is_unavailable=is_unavailable
    )

    recommendations = []
    if uncertainty_info.get('is_uncertain') and not is_unavailable and 'unable' not in pred:
        lead_sc = uncertainty_info.get('top_score', inspection.confidence_score)
        margin_sc = uncertainty_info.get('margin', 0.0)
        second_lead = uncertainty_info.get('second_class', 'alternative conditions')
        recommendations.append({
            'type': 'warning',
            'title': 'Manual Review Recommended (Uncertain Score)',
            'detail': f'Model confidence ({lead_sc}%) is closely contested (margin {margin_sc}% vs {second_lead}) or below the 60% confidence baseline. Softmax scores are uncalibrated model scores. On-site visual inspection is recommended to confirm surface condition.'
        })
    elif (inspection.confidence_score > 0 and inspection.confidence_score < 60.0 and 'unable' not in pred) or inspection.review_status == 'flagged':
        recommendations.append({
            'type': 'warning',
            'title': 'Manual Review Recommended (Uncertain Score)',
            'detail': f'Model confidence ({inspection.confidence_score}%) is below the 60% confidence baseline or prediction was flagged for review. Softmax scores are uncalibrated model scores. On-site visual inspection is recommended to confirm surface condition.'
        })

    if is_unavailable:
        recommendations.append({
            'type': 'warning',
            'title': 'AI Model Unavailable — Manual Review Required',
            'detail': 'The automated CNN model was offline or encountered an artifact error during this inspection. No visual condition could be derived. An uncalibrated 0.0% score must not be interpreted as model certainty. Manual on-site technician review or photo re-inspection is recommended.'
        })
    elif 'unable' in pred or 'retake' in pred:
        recommendations.append({
            'type': 'warning',
            'title': 'Unable to Assess — Photo Retake Recommended',
            'detail': 'The image clarity or lighting was insufficient for reliable analysis. Please capture a clear, well-lit, front-facing photograph of the solar panel.'
        })
    elif 'crack' in pred or 'damage' in pred:
        recommendations.append({
            'type': 'danger',
            'title': 'Visible Surface Fracture / Damage Alert',
            'detail': 'Possible visible cracking or surface fracture detected. Avoid touching or handling damaged electrical equipment. Arrange prompt physical inspection by a qualified solar technician.'
        })
    elif 'bird' in pred:
        recommendations.append({
            'type': 'warning',
            'title': 'Localized Organic Soiling Cleaning Advised',
            'detail': 'Possible bird droppings detected. Localized opaque spots cause cell reverse-bias and hot-spot risks. Schedule safe cleaning using water and soft sponge.'
        })
    elif 'dust' in pred:
        recommendations.append({
            'type': 'info',
            'title': 'Routine Soiling Wash Recommended',
            'detail': 'Possible particulate dust accumulation detected. Schedule routine washing during early morning or evening hours to restore generation performance.'
        })
    elif 'normal' in pred or 'clean' in pred or pred == '':
        recommendations.append({
            'type': 'success',
            'title': 'No Visible Surface Fault Detected',
            'detail': 'No supported visible anomalies detected in this photograph. Standard scheduled maintenance applies. Note: RGB photography cannot verify internal electrical output.'
        })
    else:
        recommendations.append({
            'type': 'warning',
            'title': 'Inconclusive Visual Finding',
            'detail': f"Visual assessment '{inspection.predicted_class}' is inconclusive. Manual review is recommended."
        })

    if pri_level == 'Manual Inspection Recommended' or pri_level == 'High':
        recommendations.append({
            'type': 'danger',
            'title': 'Manual Physical Inspection Recommended',
            'detail': 'Prompt physical review by a qualified solar technician is advised to inspect module glass and cell structure.'
        })
    elif pri_level == 'Cleaning Recommended' or pri_level == 'Medium':
        cleaning_detail = 'Array surface washing is recommended to restore solar irradiance absorption.'
        if panel.days_since_last_cleaning is not None:
            cleaning_detail += f' (Last recorded cleaning was {panel.days_since_last_cleaning} days ago).'
        recommendations.append({
            'type': 'warning',
            'title': 'Surface Cleaning Recommended',
            'detail': cleaning_detail
        })
    elif pri_level == 'Unable to Assess':
        if is_unavailable:
            recommendations.append({
                'type': 'secondary',
                'title': 'Manual Physical Triage Advised',
                'detail': 'Because automated visual screening could not be completed, physical inspection by a technician is recommended to verify module glass and electrical connections.'
            })
        else:
            recommendations.append({
                'type': 'secondary',
                'title': 'Photo Retake Recommended',
                'detail': 'Image quality was inconclusive. Please capture a clear, well-lit photograph facing the panel.'
            })
    elif 'normal' in pred or 'clean' in pred:
        recommendations.append({
            'type': 'success',
            'title': 'Routine Operational Monitoring',
            'detail': 'Panel surface condition is normal. Standard periodic visual inspection schedule applies.'
        })
    else:
        recommendations.append({
            'type': 'secondary',
            'title': 'Inspection Needs Review',
            'detail': 'Maintenance triage could not be automatically confirmed as Routine. Manual technician review is advised.'
        })

    existing_issue = inspection.issues.first()

    context = {
        'inspection': inspection,
        'panel': panel,
        'recommendations': recommendations,
        'existing_issue': existing_issue,
        'priority_level': pri_level,
        'is_model_unavailable': is_unavailable,
        'uncertainty_info': uncertainty_info,
        'can_verify': can_verify_inspection(request.user, inspection),
    }
    return render(request, 'core/result.html', context)


@login_required
def secure_inspection_image_view(request, pk):
    """
    Enforces authorization for image access and downloads.
    Returns HTTP 403 Forbidden if user is unauthorized.
    """
    inspection = get_object_or_404(Inspection.objects.select_related('panel', 'panel__installation'), pk=pk)

    if not can_view_inspection(request.user, inspection):
        return HttpResponseForbidden("Access Denied: You do not have permission to view or download this inspection image.")

    if not inspection.image or not os.path.exists(inspection.image.path):
        raise Http404("Inspection image not found on server.")

    return FileResponse(open(inspection.image.path, 'rb'), content_type='image/jpeg')


# ============================================================================
# Maintenance Issues & Work Orders (RBAC Protected)
# ============================================================================

def record_maintenance_log(issue, user, action_type, notes='', prev_status='', new_status='', technician=None, performed_at=None):
    """
    Creates an immutable audit log entry for maintenance lifecycle tracking.
    """
    return MaintenanceLog.objects.create(
        panel=issue.panel,
        issue=issue,
        user=user,
        action_type=action_type,
        notes=notes,
        previous_status=prev_status or '',
        new_status=new_status or '',
        technician=technician,
        performed_at=performed_at or datetime.date.today(),
    )


@login_required
def issue_list_view(request):
    """
    Maintenance Issue Queue showing issues accessible to current user.
    - Customer: Open and past issues for owned installations / panels.
    - Technician: ONLY issues assigned to this technician.
    - Admin: All system maintenance requests with filtering by status, priority, installation, and technician.
    """
    all_accessible = get_accessible_maintenance_issues(request.user)
    issues_qs = all_accessible.select_related('panel', 'panel__installation', 'installation', 'assigned_technician', 'user')

    status_filter = request.GET.get('status', 'all')
    priority_filter = request.GET.get('priority', 'all')
    installation_filter = request.GET.get('installation', 'all')
    technician_filter = request.GET.get('technician', 'all')

    if status_filter == 'unassigned' and is_admin(request.user):
        issues_qs = issues_qs.filter(assigned_technician__isnull=True, status='Open')
    elif status_filter in ['Open', 'Assigned', 'In Progress', 'Resolved', 'Closed', 'Needs Review']:
        issues_qs = issues_qs.filter(status=status_filter)

    if priority_filter in ['High', 'Medium', 'Low']:
        issues_qs = issues_qs.filter(priority=priority_filter)

    if installation_filter != 'all':
        try:
            issues_qs = issues_qs.filter(installation_id=int(installation_filter))
        except (ValueError, TypeError):
            pass

    if technician_filter != 'all' and is_admin(request.user):
        try:
            issues_qs = issues_qs.filter(assigned_technician_id=int(technician_filter))
        except (ValueError, TypeError):
            pass

    # Aggregated counts for filter tabs
    counts = {
        'all': all_accessible.count(),
        'unassigned': all_accessible.filter(assigned_technician__isnull=True, status='Open').count() if is_admin(request.user) else 0,
        'open': all_accessible.filter(status='Open').count(),
        'assigned': all_accessible.filter(status='Assigned').count(),
        'in_progress': all_accessible.filter(status='In Progress').count(),
        'resolved': all_accessible.filter(status='Resolved').count(),
        'closed': all_accessible.filter(status='Closed').count(),
    }

    # Available filter options for admins
    technicians_list = []
    installations_list = []
    if is_admin(request.user):
        technicians_list = User.objects.filter(profile__role__iexact='technician').order_by('username')
        installations_list = Installation.objects.all().order_by('name')

    return render(request, 'core/issue_list.html', {
        'issues': issues_qs,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'installation_filter': installation_filter,
        'technician_filter': technician_filter,
        'counts': counts,
        'technicians_list': technicians_list,
        'installations_list': installations_list,
        'user_role': get_user_role(request.user),
        'is_admin': is_admin(request.user),
        'is_technician': is_technician(request.user),
        'is_customer': is_customer(request.user),
    })


@login_required
def issue_create_view(request, inspection_id=None):
    """
    Create a new maintenance issue ticket.
    Validates panel ownership and scopes accessible panels.
    Supports pre-population from inspection_id or ?panel_id=<id>.
    Checks for existing open maintenance issues to avoid accidental duplicates.
    Does not automatically assign technicians.
    """
    initial = {}
    linked_inspection = None
    target_panel = None

    if inspection_id:
        linked_inspection = get_object_or_404(Inspection.objects.select_related('panel', 'panel__installation'), pk=inspection_id)
        if not can_view_inspection(request.user, linked_inspection):
            return HttpResponseForbidden("Access Denied: You do not have permission to log an issue for this inspection.")

        target_panel = linked_inspection.panel
        initial['panel'] = target_panel.id
        panel_label = target_panel.permanent_id or target_panel.serial_number

        # Uncertainty triage check on linked inspection
        uncertainty = evaluate_prediction_uncertainty(
            class_probabilities=linked_inspection.class_probabilities,
            predicted_class=linked_inspection.predicted_class,
            confidence_score=linked_inspection.confidence_score
        )

        if uncertainty.get('is_uncertain') or linked_inspection.review_status == 'flagged':
            initial['title'] = f"Verification Needed: Ambiguous {linked_inspection.predicted_class} on {panel_label}"
            margin_txt = f" (Margin: {uncertainty.get('margin', 0.0)}% vs {uncertainty.get('second_class', 'competing category')})" if uncertainty.get('second_class') else ""
            initial['description'] = (
                f"Generated from inspection #{linked_inspection.id} on {linked_inspection.inspected_at.strftime('%Y-%m-%d')}.\n"
                f"Tentative AI Finding: {linked_inspection.predicted_class} (Model Confidence: {linked_inspection.confidence_score}%).\n"
                f"Triage Flag: Uncertain Classification{margin_txt}.\n"
                f"Recommendation: Ambiguous visual condition detected. On-site manual technician review is recommended before committing a definitive fault work order."
            )
            initial['priority'] = 'Medium' if linked_inspection.predicted_class in ('Surface-Damage', 'Bird-Dropping') else 'Low'
        else:
            initial['title'] = f"Maintenance: {linked_inspection.predicted_class} on {panel_label}"
            initial['description'] = f"Generated from inspection on {linked_inspection.inspected_at.strftime('%Y-%m-%d')}.\nVisual finding: {linked_inspection.predicted_class} (Confidence {linked_inspection.confidence_score}%).\nPriority Category: {linked_inspection.maintenance_priority_level}."
            pri_level = linked_inspection.maintenance_priority_level or ''
            if 'manual' in pri_level.lower() or pri_level == 'High':
                initial['priority'] = 'High'
            elif 'cleaning' in pri_level.lower() or pri_level == 'Medium':
                initial['priority'] = 'Medium'
            else:
                initial['priority'] = 'Low'
    elif request.GET.get('panel_id'):
        panel_id_param = request.GET.get('panel_id')
        try:
            cand = Panel.objects.select_related('installation').get(pk=panel_id_param)
            if can_view_panel(request.user, cand):
                target_panel = cand
                initial['panel'] = target_panel.id
                panel_label = target_panel.permanent_id or target_panel.serial_number
                initial['title'] = f"Maintenance Request for {panel_label}"
                derived = target_panel.get_derived_condition()
                if derived['is_inspected']:
                    initial['description'] = f"Current condition: {derived['label']}.\n{derived['detail']}"
                    if 'Damage' in derived['label'] or 'Review' in derived['label']:
                        initial['priority'] = 'High'
                    elif 'Cleaning' in derived['label']:
                        initial['priority'] = 'Medium'
                    else:
                        initial['priority'] = 'Low'
                else:
                    initial['description'] = "Routine physical inspection or maintenance request."
            else:
                messages.warning(request, "Selected panel is not accessible.")
        except (Panel.DoesNotExist, ValueError):
            messages.warning(request, "Specified panel does not exist.")

    # Check for active existing issue on this panel
    existing_open_issue = None
    if target_panel:
        existing_open_issue = target_panel.issues.filter(
            status__in=['Open', 'Assigned', 'In Progress']
        ).first()

    if request.method == 'POST':
        form = MaintenanceIssueForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            issue = form.save(commit=False)
            # Verify panel ownership
            if not can_view_panel(request.user, issue.panel):
                return HttpResponseForbidden("Access Denied: You cannot create a maintenance issue for a panel you do not own.")

            # Duplicate prevention check
            duplicate_check = issue.panel.issues.filter(status__in=['Open', 'Assigned', 'In Progress']).first()
            if duplicate_check and not form.cleaned_data.get('confirm_duplicate'):
                messages.warning(
                    request,
                    f"Notice: Panel {issue.panel.permanent_id or issue.panel.serial_number} already has an active work order (#{duplicate_check.id}: '{duplicate_check.title}' - {duplicate_check.status}). If you wish to submit an additional separate request, check 'Confirm submission of additional work order'."
                )
                return render(request, 'core/issue_form.html', {
                    'form': form,
                    'linked_inspection': linked_inspection,
                    'target_panel': issue.panel,
                    'existing_open_issue': duplicate_check,
                })

            with transaction.atomic():
                issue.user = request.user
                if linked_inspection:
                    issue.inspection = linked_inspection
                if issue.panel and issue.panel.installation:
                    issue.installation = issue.panel.installation
                # Unassigned by default: only administrators can assign technicians
                issue.assigned_technician = None
                issue.status = 'Open'
                issue.save()

                # Record immutable creation log
                record_maintenance_log(
                    issue=issue,
                    user=request.user,
                    action_type='status_change',
                    prev_status='',
                    new_status='Open',
                    notes=f"Work order #{issue.id} created by {request.user.username}."
                )

            # Notify Administrators of new maintenance request
            notify_admins(
                event_type='new_maintenance_issue',
                title=f"New Work Order #{issue.id}: {issue.title}",
                message=f"Customer {request.user.username} logged a {issue.priority} priority request for panel {issue.panel.permanent_id or issue.panel.serial_number}.",
                target_url=reverse('issue_detail', kwargs={'pk': issue.pk}),
                exclude_user=request.user
            )

            messages.success(request, f"Maintenance work order #{issue.id} ('{issue.title}') created successfully!")
            return redirect('issue_detail', pk=issue.pk)
    else:
        form = MaintenanceIssueForm(user=request.user, initial=initial)

    return render(request, 'core/issue_form.html', {
        'form': form,
        'linked_inspection': linked_inspection,
        'target_panel': target_panel,
        'existing_open_issue': existing_open_issue,
    })


@login_required
def issue_detail_view(request, pk):
    """
    Detailed Work Order View and Lifecycle Actions:
    - Customer: View status, assigned technician, notes, resolution details, and action history.
    - Technician: Start work (Assigned -> In Progress), log field actions (cleaning, repairs, notes), and submit resolution (In Progress -> Resolved) with mandatory notes.
    - Admin: Assign/reassign certified technician, update priority, confirm closure (Resolved -> Closed).
    Strictly verifies object-level permissions and enforces valid state machine transitions.
    """
    issue = get_object_or_404(
        MaintenanceIssue.objects.select_related(
            'panel', 'panel__installation', 'installation', 'assigned_technician', 'user'
        ),
        pk=pk
    )

    if not can_view_issue(request.user, issue):
        return HttpResponseForbidden("Access Denied: You do not have permission to view this maintenance issue.")

    user_is_admin = is_admin(request.user)
    user_is_assigned_tech = is_technician(request.user) and issue.assigned_technician_id == request.user.id

    if request.method == 'POST':
        action = request.POST.get('action')

        # 1. Admin Assign / Reassign Technician
        if action == 'assign_technician':
            if not user_is_admin:
                return HttpResponseForbidden("Access Denied: Only administrators can assign technicians.")
            assign_form = AdminTechnicianAssignForm(request.POST)
            if assign_form.is_valid():
                with transaction.atomic():
                    tech = assign_form.cleaned_data['technician']
                    pri = assign_form.cleaned_data.get('priority')
                    notes = assign_form.cleaned_data.get('notes', '').strip()
                    prev_tech = issue.assigned_technician
                    prev_status = issue.status

                    issue.assigned_technician = tech
                    if pri:
                        issue.priority = pri
                    if issue.status == 'Open':
                        issue.status = 'Assigned'
                    issue.save()

                    if prev_tech and prev_tech != tech:
                        log_msg = f"Reassigned from {prev_tech.username} to {tech.username} by administrator {request.user.username}."
                    else:
                        log_msg = f"Assigned to certified technician {tech.username} by administrator {request.user.username}."
                    if notes:
                        log_msg += f" Note: {notes}"

                    record_maintenance_log(
                        issue=issue,
                        user=request.user,
                        action_type='assignment',
                        prev_status=prev_status,
                        new_status=issue.status,
                        technician=tech,
                        notes=log_msg
                    )

                    # Notify assigned technician
                    if tech and tech != request.user:
                        ev = 'work_reassigned' if prev_tech and prev_tech != tech else 'work_assigned'
                        notify_user(
                            recipient=tech,
                            event_type=ev,
                            title=f"Work Order #{issue.id} Assigned ({issue.priority} Priority)",
                            message=f"You have been assigned to work order #{issue.id} ('{issue.title}') for panel {issue.panel.permanent_id or issue.panel.serial_number}.",
                            target_url=reverse('issue_detail', kwargs={'pk': issue.pk})
                        )

                    # Notify customer
                    if issue.user and issue.user != request.user:
                        notify_user(
                            recipient=issue.user,
                            event_type='maintenance_assigned',
                            title=f"Technician Assigned to Work Order #{issue.id}",
                            message=f"Certified technician {tech.username} has been assigned to your request '{issue.title}'.",
                            target_url=reverse('issue_detail', kwargs={'pk': issue.pk})
                        )

                messages.success(request, f"Technician {tech.username} assigned to work order #{issue.id}.")
                return redirect('issue_detail', pk=issue.pk)
            else:
                for field, errs in assign_form.errors.items():
                    for e in errs:
                        messages.error(request, f"Assignment Error: {e}")

        # 2. Technician Starts Work (Assigned -> In Progress)
        elif action == 'start_work':
            if not (user_is_assigned_tech or user_is_admin):
                return HttpResponseForbidden("Access Denied: Only the assigned technician can start work on this ticket.")
            if issue.status != 'Assigned':
                messages.error(request, f"Cannot start work: ticket is in '{issue.status}' status (expected 'Assigned').")
                return redirect('issue_detail', pk=issue.pk)
            with transaction.atomic():
                prev_status = issue.status
                issue.status = 'In Progress'
                issue.save(update_fields=['status', 'updated_at'])
                record_maintenance_log(
                    issue=issue,
                    user=request.user,
                    action_type='status_change',
                    prev_status=prev_status,
                    new_status='In Progress',
                    notes=f"Work accepted and marked In Progress by {request.user.username}."
                )
            messages.success(request, "Work order marked In Progress. You may now record field actions and submit resolution.")
            return redirect('issue_detail', pk=issue.pk)

        # Backward-compatible status update action
        elif action == 'update_status':
            if is_customer(request.user):
                return HttpResponseForbidden("Access Denied: Customers cannot modify work order status.")
            if not (user_is_assigned_tech or user_is_admin):
                return HttpResponseForbidden("Access Denied: Only assigned technicians or administrators can update status.")
            new_status = request.POST.get('status')
            if new_status == 'In Progress':
                with transaction.atomic():
                    prev_status = issue.status
                    issue.status = 'In Progress'
                    issue.save(update_fields=['status', 'updated_at'])
                    record_maintenance_log(
                        issue=issue,
                        user=request.user,
                        action_type='status_change',
                        prev_status=prev_status,
                        new_status='In Progress',
                        notes=f"Work status updated to In Progress by {request.user.username}."
                    )
                messages.success(request, "Work order marked In Progress.")
                return redirect('issue_detail', pk=issue.pk)
            elif new_status == 'Resolved':
                notes = request.POST.get('resolution_notes', '').strip() or request.POST.get('notes', '').strip() or 'Resolved during maintenance inspection.'
                with transaction.atomic():
                    prev_status = issue.status
                    issue.status = 'Resolved'
                    issue.resolution_notes = notes
                    issue.resolved_at = timezone.now()
                    issue.save(update_fields=['status', 'resolution_notes', 'resolved_at', 'updated_at'])
                    record_maintenance_log(
                        issue=issue,
                        user=request.user,
                        action_type='resolution',
                        prev_status=prev_status,
                        new_status='Resolved',
                        notes=notes
                    )
                messages.success(request, f"Work order #{issue.id} marked Resolved.")
                return redirect('issue_detail', pk=issue.pk)
            else:
                messages.error(request, f"Invalid status transition to '{new_status}'.")
                return redirect('issue_detail', pk=issue.pk)

        # 3. Technician Resolves Work (In Progress -> Resolved)
        elif action == 'resolve_work':
            if not (user_is_assigned_tech or user_is_admin):
                return HttpResponseForbidden("Access Denied: Only the assigned technician can resolve this ticket.")
            if issue.status != 'In Progress':
                messages.error(request, f"Cannot resolve: ticket is in '{issue.status}' status (must be 'In Progress').")
                return redirect('issue_detail', pk=issue.pk)

            res_form = TechnicianResolutionForm(request.POST)
            if res_form.is_valid():
                with transaction.atomic():
                    resolution_notes = res_form.cleaned_data['resolution_notes']
                    prev_status = issue.status
                    issue.status = 'Resolved'
                    issue.resolution_notes = resolution_notes
                    issue.resolved_at = timezone.now()
                    issue.save(update_fields=['status', 'resolution_notes', 'resolved_at', 'updated_at'])

                    record_maintenance_log(
                        issue=issue,
                        user=request.user,
                        action_type='resolution',
                        prev_status=prev_status,
                        new_status='Resolved',
                        notes=resolution_notes
                    )

                    # Notify Administrators of technician completion
                    notify_admins(
                        event_type='technician_completion',
                        title=f"Work Order #{issue.id} Resolved",
                        message=f"Technician {request.user.username} resolved work order #{issue.id} ('{issue.title}').",
                        target_url=reverse('issue_detail', kwargs={'pk': issue.pk}),
                        exclude_user=request.user
                    )

                    # Notify Customer of Resolution
                    if issue.user and issue.user != request.user:
                        notify_user(
                            recipient=issue.user,
                            event_type='maintenance_completed',
                            title=f"Work Order #{issue.id} Resolved",
                            message=f"Service on panel {issue.panel.permanent_id or issue.panel.serial_number} was completed by technician {request.user.username}.",
                            target_url=reverse('issue_detail', kwargs={'pk': issue.pk})
                        )

                messages.success(request, f"Work order #{issue.id} marked Resolved! Customer can now see completed maintenance details.")
                return redirect('issue_detail', pk=issue.pk)
            else:
                for field, errs in res_form.errors.items():
                    for e in errs:
                        messages.error(request, e)

        # 4. Admin Closes Work Order (Resolved -> Closed)
        elif action == 'close_work':
            if not user_is_admin:
                return HttpResponseForbidden("Access Denied: Only administrators can close work orders.")
            if issue.status != 'Resolved':
                messages.error(request, f"Cannot close ticket: status is '{issue.status}' (must be 'Resolved').")
                return redirect('issue_detail', pk=issue.pk)
            with transaction.atomic():
                prev_status = issue.status
                close_notes = request.POST.get('closure_notes', '').strip() or "Work order approved and closed by administrator."
                issue.status = 'Closed'
                issue.closed_at = timezone.now()
                issue.save(update_fields=['status', 'closed_at', 'updated_at'])
                record_maintenance_log(
                    issue=issue,
                    user=request.user,
                    action_type='closure',
                    prev_status=prev_status,
                    new_status='Closed',
                    notes=close_notes
                )

                # Notify Customer of Final Ticket Closure
                if issue.user and issue.user != request.user:
                    notify_user(
                        recipient=issue.user,
                        event_type='maintenance_closed',
                        title=f"Work Order #{issue.id} Approved & Closed",
                        message=f"Work order #{issue.id} ('{issue.title}') has been finalized and closed by the administrator.",
                        target_url=reverse('issue_detail', kwargs={'pk': issue.pk})
                    )

            messages.success(request, f"Work order #{issue.id} successfully closed.")
            return redirect('issue_detail', pk=issue.pk)

        # 5. Technician / Admin Adds Field Action Log
        elif action == 'add_log':
            if not can_update_issue(request.user, issue):
                return HttpResponseForbidden("Access Denied: Only assigned technicians or administrators can record maintenance action logs.")
            log_form = MaintenanceActionForm(request.POST)
            if log_form.is_valid():
                with transaction.atomic():
                    log = log_form.save(commit=False)
                    log.panel = issue.panel
                    log.issue = issue
                    log.user = request.user
                    log.save()

                    if log.action_type == 'cleaning':
                        issue.panel.last_cleaned_date = log.performed_at
                        issue.panel.save(update_fields=['last_cleaned_date'])

                messages.success(request, f"Maintenance action '{log.get_action_type_display()}' recorded!")
                return redirect('issue_detail', pk=issue.pk)
            else:
                messages.error(request, "Failed to record maintenance action. Please check the form.")

        # 6. Admin Update Priority
        elif action == 'update_priority':
            if not user_is_admin:
                return HttpResponseForbidden("Access Denied: Only administrators can change priority.")
            new_pri = request.POST.get('priority')
            if new_pri in ['Low', 'Medium', 'High']:
                old_pri = issue.priority
                issue.priority = new_pri
                issue.save(update_fields=['priority', 'updated_at'])
                record_maintenance_log(
                    issue=issue,
                    user=request.user,
                    action_type='note',
                    notes=f"Priority updated from {old_pri} to {new_pri} by administrator {request.user.username}."
                )
                messages.success(request, f"Priority updated to {new_pri}.")
                return redirect('issue_detail', pk=issue.pk)

        # 7. Backward compatibility for legacy test actions
        elif action == 'update_status':
            new_status = request.POST.get('status')
            if not can_update_issue(request.user, issue):
                return HttpResponseForbidden("Access Denied: You cannot update status on this issue.")
            if is_technician(request.user):
                if issue.assigned_technician != request.user:
                    return HttpResponseForbidden("Access Denied: You are not assigned to this work order.")
                if new_status == 'In Progress' and issue.status == 'Assigned':
                    issue.status = 'In Progress'
                    issue.save(update_fields=['status', 'updated_at'])
                    record_maintenance_log(issue, request.user, 'status_change', prev_status='Assigned', new_status='In Progress', notes="Status updated to In Progress.")
                    messages.success(request, "Status updated to In Progress.")
                    return redirect('issue_detail', pk=issue.pk)
                elif new_status == 'Resolved' and issue.status == 'In Progress':
                    notes = request.POST.get('resolution_notes', '').strip() or "Work completed by technician."
                    issue.status = 'Resolved'
                    issue.resolution_notes = notes
                    issue.resolved_at = timezone.now()
                    issue.save()
                    record_maintenance_log(issue, request.user, 'resolution', prev_status='In Progress', new_status='Resolved', notes=notes)
                    messages.success(request, "Status updated to Resolved.")
                    return redirect('issue_detail', pk=issue.pk)
                else:
                    return HttpResponseForbidden(f"Invalid status transition from {issue.status} to {new_status} for technician.")
            elif user_is_admin:
                old_status = issue.status
                issue.status = new_status
                if new_status in ['Resolved', 'Closed']:
                    issue.resolved_at = timezone.now()
                issue.save()
                record_maintenance_log(issue, request.user, 'status_change', prev_status=old_status, new_status=new_status, notes=f"Admin updated status to {new_status}.")
                messages.success(request, f"Status updated to {new_status}.")
                return redirect('issue_detail', pk=issue.pk)
            else:
                return HttpResponseForbidden("Access Denied.")

        # 8. Admin Set / Update Service Fee
        elif action == 'set_service_fee':
            if not user_is_admin:
                return HttpResponseForbidden("Access Denied: Only administrators can set maintenance charges.")
            fee_str = request.POST.get('service_fee', '0.00').strip()
            try:
                fee = Decimal(fee_str)
                if fee < Decimal('0.00'):
                    raise ValueError("Service charge cannot be negative.")
            except (ValueError, ArithmeticError):
                messages.error(request, "Invalid service charge amount. Please enter a valid number (e.g. 499.00).")
                return redirect('issue_detail', pk=issue.pk)

            with transaction.atomic():
                old_fee = issue.service_fee
                issue.service_fee = fee
                if issue.payment_status in ['unbilled', 'failed'] and fee > Decimal('0.00'):
                    issue.payment_status = 'pending'
                elif fee == Decimal('0.00') and issue.payment_status != 'paid':
                    issue.payment_status = 'unbilled'
                issue.save(update_fields=['service_fee', 'payment_status', 'updated_at'])

                record_maintenance_log(
                    issue=issue,
                    user=request.user,
                    action_type='note',
                    notes=f"Service charge updated from ₹{old_fee:.2f} to ₹{fee:.2f} by administrator {request.user.username}."
                )
            messages.success(request, f"Service charge of ₹{fee:.2f} set for work order #{issue.id}.")
            return redirect('issue_detail', pk=issue.pk)

    action_logs = issue.action_logs.select_related('user', 'technician').order_by('-created_at', '-performed_at')
    log_form = MaintenanceActionForm()
    assign_form = AdminTechnicianAssignForm(initial={'technician': issue.assigned_technician, 'priority': issue.priority}) if user_is_admin else None
    res_form = TechnicianResolutionForm(initial={'resolution_notes': issue.resolution_notes}) if (user_is_assigned_tech or user_is_admin) else None

    # Payment workflow context
    successful_payment = issue.latest_successful_payment
    is_cust = is_customer(request.user)
    can_pay = (is_cust or user_is_admin) and issue.service_fee > Decimal('0.00') and issue.payment_status != 'paid'

    context = {
        'issue': issue,
        'action_logs': action_logs,
        'log_form': log_form,
        'assign_form': assign_form,
        'res_form': res_form,
        'can_update': can_update_issue(request.user, issue),
        'user_is_admin': user_is_admin,
        'user_is_assigned_tech': user_is_assigned_tech,
        'user_role': get_user_role(request.user),
        'successful_payment': successful_payment,
        'razorpay_configured': is_razorpay_configured(),
        'is_customer': is_cust,
        'can_pay': can_pay,
    }
    return render(request, 'core/issue_detail.html', context)


# ============================================================================
# Authentication Views
# ============================================================================

def login_view(request):
    """User login view."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            next_url = request.GET.get('next', 'dashboard')
            return redirect(next_url)
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()

    return render(request, 'core/login.html', {'form': form})


def logout_view(request):
    """User logout view."""
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect('login')


# ============================================================================
# Phase 8: Inspection History & Protected Media Views
# ============================================================================

@login_required
def secure_maintenance_image_view(request, pk):
    """
    Enforces object-level authorization for maintenance supporting photographs.
    Returns HTTP 403 Forbidden if user is unauthorized.
    """
    issue = get_object_or_404(MaintenanceIssue.objects.select_related('panel', 'installation'), pk=pk)

    if not can_view_issue(request.user, issue):
        return HttpResponseForbidden("Access Denied: You do not have permission to view or download this maintenance photo.")

    if not issue.supporting_photo or not os.path.exists(issue.supporting_photo.path):
        raise Http404("Maintenance photo not found on server.")

    content_type = mimetypes.guess_type(issue.supporting_photo.name)[0] or 'image/jpeg'
    return FileResponse(open(issue.supporting_photo.path, 'rb'), content_type=content_type)


@login_required
def inspection_list_view(request):
    """
    Inspection History Queue with rich multi-parameter filtering and pagination.
    - Installation filter (scoped to accessible installations)
    - Panel filter (scoped to accessible panels)
    - Date range filter (date_from, date_to)
    - Predicted visual condition filter
    - Technician review status filter
    - Preserves history for active and retired panels.
    - Scoped strictly by role permissions.
    """
    inspections_qs = get_accessible_inspections(request.user).select_related(
        'panel', 'panel__installation', 'user', 'reviewed_by'
    ).order_by('-inspected_at')

    inst_filter = request.GET.get('installation', 'all')
    panel_filter = request.GET.get('panel', 'all')
    condition_filter = request.GET.get('condition', 'all')
    review_status_filter = request.GET.get('review_status', 'all')
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()

    if inst_filter != 'all':
        try:
            inspections_qs = inspections_qs.filter(panel__installation_id=int(inst_filter))
        except (ValueError, TypeError):
            pass

    if panel_filter != 'all':
        try:
            inspections_qs = inspections_qs.filter(panel_id=int(panel_filter))
        except (ValueError, TypeError):
            pass

    if condition_filter != 'all':
        inspections_qs = inspections_qs.filter(predicted_class=condition_filter)

    if review_status_filter != 'all':
        inspections_qs = inspections_qs.filter(review_status=review_status_filter)

    if date_from:
        try:
            d_from = datetime.datetime.strptime(date_from, "%Y-%m-%d").date()
            inspections_qs = inspections_qs.filter(inspected_at__date__gte=d_from)
        except ValueError:
            pass

    if date_to:
        try:
            d_to = datetime.datetime.strptime(date_to, "%Y-%m-%d").date()
            inspections_qs = inspections_qs.filter(inspected_at__date__lte=d_to)
        except ValueError:
            pass

    total_count = inspections_qs.count()

    paginator = Paginator(inspections_qs, 15)
    page_number = request.GET.get('page', 1)
    try:
        page_obj = paginator.get_page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.get_page(1)

    accessible_installations = get_accessible_installations(request.user).order_by('name')
    accessible_panels = get_accessible_panels(request.user).select_related('installation').order_by('permanent_id', 'serial_number')

    conditions_list = [
        'Normal', 'Dusty', 'Bird-Dropping', 'Surface-Damage', 'Cracked',
        'Electrical-Damage', 'Snow-Covered', 'Unable to assess / Retake photo'
    ]

    context = {
        'page_obj': page_obj,
        'total_count': total_count,
        'installations': accessible_installations,
        'panels': accessible_panels,
        'conditions_list': conditions_list,
        'inst_filter': inst_filter,
        'panel_filter': panel_filter,
        'condition_filter': condition_filter,
        'review_status_filter': review_status_filter,
        'date_from': date_from,
        'date_to': date_to,
        'user_role': get_user_role(request.user),
        'is_admin': is_admin(request.user),
        'is_technician': is_technician(request.user),
        'is_customer': is_customer(request.user),
    }
    return render(request, 'core/inspection_list.html', context)


# ============================================================================
# Phase 8: Reports Hub & Secure Export Views
# ============================================================================

@login_required
def reports_index_view(request):
    """
    Central Reports Management Hub.
    Offers access to:
    1. Individual Panel Inspection Report
    2. Installation Condition Summary
    3. Maintenance History Report
    Enforces RBAC scoping across all report selection menus.
    """
    installations = get_accessible_installations(request.user).order_by('name')
    panels = get_accessible_panels(request.user).select_related('installation').order_by('permanent_id', 'serial_number')

    context = {
        'installations': installations,
        'panels': panels,
        'user_role': get_user_role(request.user),
        'is_admin': is_admin(request.user),
        'is_technician': is_technician(request.user),
        'is_customer': is_customer(request.user),
        'current_date_str': datetime.date.today().strftime("%B %d, %Y"),
    }
    return render(request, 'core/reports/reports_index.html', context)


@login_required
def report_panel_view(request, pk):
    """
    Individual Panel Inspection & Maintenance Report.
    Includes:
    - Generation date and physical panel identification
    - Current derived condition
    - Historical inspections list (AI prediction and technician verification separated)
    - Maintenance history and resolution notes
    - Explicit disclaimer on optical RGB limitations
    - Supports printable HTML layout and PDF download (?format=pdf).
    """
    panel = get_object_or_404(
        Panel.objects.select_related('installation', 'installation__owner', 'installation__assigned_technician'),
        pk=pk
    )

    if not can_view_panel(request.user, panel):
        return HttpResponseForbidden("Access Denied: You do not have permission to view reports for this panel.")

    derived_condition = panel.get_derived_condition()
    inspections = panel.inspections.select_related('user', 'reviewed_by').order_by('-inspected_at')
    issues = panel.issues.select_related('user', 'assigned_technician').prefetch_related('action_logs').order_by('-created_at')

    if request.GET.get('format') == 'pdf':
        return generate_panel_report_pdf(panel, derived_condition, inspections, issues)

    context = {
        'panel': panel,
        'derived_condition': derived_condition,
        'inspections': inspections,
        'issues': issues,
        'generated_date': timezone.now(),
        'user_role': get_user_role(request.user),
    }
    return render(request, 'core/reports/report_panel.html', context)


@login_required
def report_installation_view(request, pk):
    """
    Installation Condition Summary Report.
    Includes:
    - Generation date and installation details
    - Fleet summary metrics: active panels count, retired panels count, real condition breakdown
    - Panel inventory status table (coordinates, condition, verification, open tickets)
    - Active maintenance tickets summary
    - Explicit disclaimer on optical RGB limitations
    - Supports printable HTML layout and PDF download (?format=pdf).
    """
    installation = get_object_or_404(
        Installation.objects.select_related('owner', 'assigned_technician'),
        pk=pk
    )

    if not can_view_installation(request.user, installation):
        return HttpResponseForbidden("Access Denied: You do not have permission to view reports for this installation.")

    all_panels = list(installation.panels.prefetch_related('inspections', 'issues').order_by('grid_row', 'grid_col', 'permanent_id'))
    active_panels = [p for p in all_panels if p.status == 'active']
    retired_panels = [p for p in all_panels if p.status == 'retired']

    breakdown = {
        'total_active': len(active_panels),
        'total_retired': len(retired_panels),
        'normal': 0,
        'cleaning': 0,
        'damage': 0,
        'review': 0,
        'not_inspected': 0,
    }

    panel_summaries = []
    for p in all_panels:
        cond = p.get_derived_condition()
        if p.status == 'active':
            st = cond['status']
            if st == 'normal':
                breakdown['normal'] += 1
            elif st in ('dust', 'bird'):
                breakdown['cleaning'] += 1
            elif st == 'damage':
                breakdown['damage'] += 1
            elif st == 'review':
                breakdown['review'] += 1
            else:
                breakdown['not_inspected'] += 1

        open_issue = p.issues.filter(status__in=['Open', 'Assigned', 'In Progress']).first()
        panel_summaries.append({
            'panel': p,
            'condition': cond,
            'open_issue': open_issue,
            'is_retired': (p.status == 'retired'),
        })

    active_issues = installation.maintenance_issues.filter(
        status__in=['Open', 'Assigned', 'In Progress']
    ).select_related('panel', 'assigned_technician').order_by('-created_at')

    if request.GET.get('format') == 'pdf':
        return generate_installation_report_pdf(installation, breakdown, panel_summaries, active_issues)

    context = {
        'installation': installation,
        'breakdown': breakdown,
        'panel_summaries': panel_summaries,
        'active_issues': active_issues,
        'generated_date': timezone.now(),
        'user_role': get_user_role(request.user),
    }
    return render(request, 'core/reports/report_installation.html', context)


@login_required
def report_maintenance_view(request):
    """
    Maintenance History and Work Order Audit Report.
    Includes:
    - Generation date and report scope
    - Summary of tickets by status (Total, Open, Assigned, In Progress, Resolved, Closed)
    - Full work order table with technician assignments and resolution notes
    - Filterable by installation and date range
    - Scoped strictly by role permissions
    - Supports printable HTML layout and PDF download (?format=pdf).
    """
    issues_qs = get_accessible_maintenance_issues(request.user).select_related(
        'panel', 'panel__installation', 'installation', 'assigned_technician', 'user'
    ).order_by('-created_at')

    inst_id = request.GET.get('installation', 'all')
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()

    selected_installation = None
    if inst_id != 'all':
        try:
            cand = Installation.objects.get(pk=int(inst_id))
            if can_view_installation(request.user, cand):
                selected_installation = cand
                issues_qs = issues_qs.filter(installation=cand)
            else:
                return HttpResponseForbidden("Access Denied: You do not have permission to view maintenance records for this installation.")
        except (Installation.DoesNotExist, ValueError):
            pass

    if date_from:
        try:
            d_from = datetime.datetime.strptime(date_from, "%Y-%m-%d").date()
            issues_qs = issues_qs.filter(created_at__date__gte=d_from)
        except ValueError:
            pass

    if date_to:
        try:
            d_to = datetime.datetime.strptime(date_to, "%Y-%m-%d").date()
            issues_qs = issues_qs.filter(created_at__date__lte=d_to)
        except ValueError:
            pass

    stats = {
        'total': issues_qs.count(),
        'open': issues_qs.filter(status='Open').count(),
        'assigned': issues_qs.filter(status='Assigned').count(),
        'in_progress': issues_qs.filter(status='In Progress').count(),
        'resolved': issues_qs.filter(status='Resolved').count(),
        'closed': issues_qs.filter(status='Closed').count(),
    }

    issues_list = list(issues_qs)

    if request.GET.get('format') == 'pdf':
        return generate_maintenance_report_pdf(issues_list, stats, selected_installation)

    context = {
        'issues': issues_list,
        'stats': stats,
        'selected_installation': selected_installation,
        'installations': get_accessible_installations(request.user).order_by('name'),
        'inst_filter': inst_id,
        'date_from': date_from,
        'date_to': date_to,
        'generated_date': timezone.now(),
        'user_role': get_user_role(request.user),
    }
    return render(request, 'core/reports/report_maintenance.html', context)


# ============================================================================
# Razorpay Test Mode Payment Views
# ============================================================================

@login_required
def payment_checkout_view(request, issue_id):
    """
    Renders Razorpay Test Mode payment modal for a maintenance work order.
    - Accessible only by the Customer owning the installation or an Administrator.
    - Converts INR to paise and creates real Razorpay Sandbox order.
    - Gracefully notifies if Razorpay credentials are not yet configured in .env.
    """
    issue = get_object_or_404(
        MaintenanceIssue.objects.select_related('panel', 'installation', 'panel__installation', 'user'),
        pk=issue_id
    )

    if not can_view_issue(request.user, issue):
        return HttpResponseForbidden("Access Denied: You do not have permission to pay for this work order.")

    # Only installation owners (customer) or administrators can pay
    user_is_owner = (
        (issue.installation and issue.installation.owner_id == request.user.id) or
        (issue.panel and issue.panel.installation and issue.panel.installation.owner_id == request.user.id) or
        (issue.user_id == request.user.id)
    )
    if not (user_is_owner or is_admin(request.user)):
        return HttpResponseForbidden("Access Denied: Only the customer who owns this installation can make payments.")

    if issue.payment_status == 'paid':
        messages.info(request, f"Work order #{issue.id} has already been paid and settled in full.")
        return redirect('issue_detail', pk=issue.pk)

    if not issue.service_fee or issue.service_fee <= Decimal('0.00'):
        messages.warning(request, f"Work order #{issue.id} has no billable service charge.")
        return redirect('issue_detail', pk=issue.pk)

    if not is_razorpay_configured():
        context = {
            'issue': issue,
            'razorpay_configured': False,
            'amount_inr': issue.service_fee,
        }
        return render(request, 'core/payment_checkout.html', context)

    # Create real Razorpay sandbox order
    order_data, tx, err = create_order_for_issue(issue, request.user)
    if err:
        messages.error(request, f"Payment Gateway Error: {err}")
        return redirect('issue_detail', pk=issue.pk)

    context = {
        'issue': issue,
        'order': order_data,
        'key_id': get_razorpay_public_key(),
        'amount_inr': issue.service_fee,
        'amount_paise': order_data['amount'],
        'customer_name': request.user.get_full_name() or request.user.username,
        'customer_email': request.user.email or f"{request.user.username}@solarguard.local",
        'razorpay_configured': True,
    }
    return render(request, 'core/payment_checkout.html', context)


@login_required
def payment_verify_view(request, issue_id):
    """
    POST callback from Razorpay checkout modal.
    Cryptographically verifies HMAC-SHA256 signature server-side.
    Guarantees idempotency and prevents duplicate payments.
    """
    if request.method != 'POST':
        return HttpResponseForbidden("Method not allowed. Payment verification requires POST.")

    issue = get_object_or_404(MaintenanceIssue, pk=issue_id)
    if not can_view_issue(request.user, issue):
        return HttpResponseForbidden("Access Denied: You do not have permission to verify this payment.")

    razorpay_order_id = request.POST.get('razorpay_order_id', '').strip()
    razorpay_payment_id = request.POST.get('razorpay_payment_id', '').strip()
    razorpay_signature = request.POST.get('razorpay_signature', '').strip()

    # Client-side dismissal / user cancelled
    if request.POST.get('cancelled') == '1':
        record_payment_cancellation(issue, razorpay_order_id, description="Payment modal closed by user")
        messages.info(request, "Payment checkout was cancelled. You may retry when ready.")
        return redirect('issue_detail', pk=issue.pk)

    if not (razorpay_order_id and razorpay_payment_id and razorpay_signature):
        record_payment_cancellation(issue, razorpay_order_id, description="Missing required payment tokens in callback")
        messages.error(request, "Payment verification aborted: Missing gateway signature parameters.")
        return redirect('issue_detail', pk=issue.pk)

    tx, is_valid, err = verify_razorpay_payment_signature(
        issue=issue,
        razorpay_order_id=razorpay_order_id,
        razorpay_payment_id=razorpay_payment_id,
        razorpay_signature=razorpay_signature
    )

    if is_valid:
        messages.success(
            request,
            f"Payment of ₹{tx.amount:.2f} successfully verified in Razorpay Test Mode! "
            f"Receipt #{tx.receipt_number} has been generated."
        )
    elif tx and tx.status == 'pending':
        messages.warning(
            request,
            f"Payment is authorized by gateway but not yet captured. Transaction remains in pending status."
        )
    else:
        messages.error(request, f"Payment verification failed: {err}")

    return redirect('issue_detail', pk=issue.pk)


@login_required
def payment_receipt_download_view(request, payment_id):
    """
    Generates and returns downloadable PDF receipt for a verified PaymentTransaction.
    Protected by object-level permission check: only authorized parties can download.
    """
    tx = get_object_or_404(
        PaymentTransaction.objects.select_related('issue', 'issue__panel', 'issue__installation', 'user'),
        pk=payment_id
    )

    if not can_view_issue(request.user, tx.issue):
        return HttpResponseForbidden("Access Denied: You do not have permission to view or download this payment receipt.")

    if tx.status != 'success':
        return HttpResponseForbidden("Receipt unavailable: Payment has not been successfully verified.")

    pdf_bytes = generate_payment_receipt_pdf(tx)
    filename = f"SolarGuard_Receipt_{tx.receipt_number or tx.id}.pdf"
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ============================================================================
# Role-Based Notification Center Views
# ============================================================================

@login_required
def notification_list_view(request):
    """
    Role-based in-app notification center.
    Displays recipient-isolated notifications with read/unread filtering.
    """
    status_filter = request.GET.get('status', 'all')
    notifs_qs = Notification.objects.filter(recipient=request.user)

    if status_filter == 'unread':
        notifs_qs = notifs_qs.filter(is_read=False)
    elif status_filter == 'read':
        notifs_qs = notifs_qs.filter(is_read=True)

    unread_count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    all_count = Notification.objects.filter(recipient=request.user).count()

    paginator = Paginator(notifs_qs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'core/notification_list.html', {
        'notifications': page_obj,
        'page_obj': page_obj,
        'status_filter': status_filter,
        'unread_count': unread_count,
        'all_count': all_count,
    })


@login_required
def notification_open_view(request, pk):
    """
    Opens the related record linked to a notification and marks it as read.
    Enforces strict recipient isolation: users can only open their own notifications.
    """
    notif = get_object_or_404(Notification, pk=pk, recipient=request.user)
    if not notif.is_read:
        notif.is_read = True
        notif.save(update_fields=['is_read'])

    if notif.target_url:
        return redirect(notif.target_url)
    return redirect('dashboard')


@login_required
def notification_mark_all_read_view(request):
    """
    Marks all notifications for the authenticated user as read.
    Safe against both POST and GET, redirecting back to referer or notification list.
    """
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    messages.success(request, "All notifications marked as read.")
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect('notification_list')


@login_required
def notification_mark_read_view(request, pk):
    """
    Toggles a single notification as read without navigating away.
    """
    notif = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notif.is_read = True
    notif.save(update_fields=['is_read'])
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect('notification_list')


