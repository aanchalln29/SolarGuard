"""
SolarGuard — Solar Panel Layout Engine & Revision Management Service

Handles:
1. Draft layout creation, versioning, and editing (isolated from active layout).
2. Rectangular and irregular array generation (e.g., 4-3-4 module configurations).
3. Stable immutable panel permanent IDs (SG-01-P006) independent of mutable (row, col) positions.
4. Safe panel removal without deletion of historical inspection records.
5. Atomic verification and live layout application within database transactions.
"""

import re
from typing import Dict, Any, List, Tuple, Optional
from django.db import transaction, models
from django.utils import timezone
from django.core.exceptions import ValidationError

from .models import Installation, Panel, LayoutRevision


def generate_next_panel_id(installation: Installation) -> str:
    """
    Generates a collision-safe, installation-scoped immutable panel identifier:
    Format: SG-{installation_id:02d}-P{seq:03d}
    Example: SG-01-P001, SG-01-P002
    Inspects all existing panels (both active and retired) to prevent ID reuse.
    """
    prefix = f"SG-{installation.id:02d}-P"
    existing_panels = Panel.objects.filter(installation=installation)
    
    max_seq = 0
    pattern = re.compile(rf"^SG-{installation.id:02d}-P(\d+)$")
    for p in existing_panels:
        if p.permanent_id:
            m = pattern.match(p.permanent_id)
            if m:
                try:
                    num = int(m.group(1))
                    if num > max_seq:
                        max_seq = num
                except ValueError:
                    pass

    next_seq = max_seq + 1
    return f"{prefix}{next_seq:03d}"


def get_or_create_draft_revision(installation: Installation, user) -> Tuple[LayoutRevision, bool]:
    """
    Retrieves an existing in-progress draft or changes_requested revision for an installation,
    or creates a new draft revision derived from the current active layout.
    Crucial Rule: Editing a verified layout creates a draft without altering the active layout.
    """
    # Check for existing draft or changes_requested revision
    draft = installation.layout_revisions.filter(
        status__in=['draft', 'changes_requested']
    ).order_by('-version_number').first()

    if draft:
        return draft, False

    # Determine next version number
    max_ver = installation.layout_revisions.aggregate(m=models.Max('version_number'))['m'] or 0
    new_version = max_ver + 1

    # Copy arrangement from active layout (verified or imported) if available
    active = installation.active_layout
    if active and active.layout_data and 'active_cells' in active.layout_data:
        grid_rows = active.grid_rows
        grid_cols = active.grid_cols
        # Deep copy active cells
        copied_cells = [dict(c) for c in active.layout_data.get('active_cells', [])]
        layout_data = {
            'rows': grid_rows,
            'cols': grid_cols,
            'active_cells': copied_cells
        }
    else:
        # Initial empty 3x4 grid default
        grid_rows = 3
        grid_cols = 4
        layout_data = {
            'rows': grid_rows,
            'cols': grid_cols,
            'active_cells': []
        }

    draft = LayoutRevision.objects.create(
        installation=installation,
        version_number=new_version,
        status='draft',
        grid_rows=grid_rows,
        grid_cols=grid_cols,
        layout_data=layout_data,
        submitted_by=user,
        review_notes=""
    )
    return draft, True


def validate_layout_data(
    installation: Installation,
    grid_rows: int,
    grid_cols: int,
    active_cells: List[Dict[str, Any]]
) -> Tuple[bool, Optional[str]]:
    """
    Strict server-side validation for solar panel layout arrangements:
    1. Grid dimensions within sensible bounds (1 to 30 rows/cols).
    2. Coordinates within grid bounds.
    3. Positive 1-indexed integers for row and column.
    4. No duplicate occupied positions (two panels in the same grid cell).
    5. No duplicate panel identities within the arrangement.
    6. All referenced existing panels belong strictly to this installation.
    """
    if not isinstance(grid_rows, int) or not isinstance(grid_cols, int):
        return False, "Grid rows and columns must be integers."

    if grid_rows < 1 or grid_rows > 30:
        return False, f"Grid rows must be between 1 and 30 (received {grid_rows})."

    if grid_cols < 1 or grid_cols > 30:
        return False, f"Grid columns must be between 1 and 30 (received {grid_cols})."

    occupied_positions = set()
    used_panel_ids = set()

    # Pre-fetch existing panel IDs for this installation
    inst_panels = {p.permanent_id: p for p in installation.panels.all() if p.permanent_id}

    for idx, cell in enumerate(active_cells):
        row = cell.get('row')
        col = cell.get('col')
        panel_id = cell.get('panel_id')

        if not isinstance(row, int) or not isinstance(col, int):
            return False, f"Cell #{idx+1} has invalid row or column coordinates."

        if row < 1 or row > grid_rows:
            return False, f"Cell position Row {row} is outside the grid bounds (1 to {grid_rows})."

        if col < 1 or col > grid_cols:
            return False, f"Cell position Col {col} is outside the grid bounds (1 to {grid_cols})."

        pos_key = (row, col)
        if pos_key in occupied_positions:
            return False, f"Duplicate position: Grid slot (Row {row}, Col {col}) is occupied more than once."
        occupied_positions.add(pos_key)

        if not panel_id:
            return False, f"Cell at (Row {row}, Col {col}) is missing a permanent panel identifier."

        if panel_id in used_panel_ids:
            return False, f"Duplicate panel ID: '{panel_id}' appears multiple times in the layout."
        used_panel_ids.add(panel_id)

        # If referencing an existing panel from another installation, reject!
        if not panel_id.startswith("NEW_") and panel_id not in inst_panels:
            # Check if this ID exists anywhere else in DB
            foreign_panel = Panel.objects.filter(permanent_id=panel_id).exclude(installation=installation).first()
            if foreign_panel:
                return False, f"Unauthorized module reference: Panel '{panel_id}' belongs to another installation."

    return True, None


def generate_rectangular_grid(
    draft_revision: LayoutRevision,
    rows: int,
    cols: int,
    user
) -> LayoutRevision:
    """
    Generates a full rectangular arrangement for a draft layout.
    Reuses existing panels of the installation first, then creates stable draft IDs for new modules.
    Empty slots are not created as physical records.
    """
    installation = draft_revision.installation
    existing_panels = list(installation.panels.filter(status='active').order_by('id'))

    active_cells = []
    panel_idx = 0
    total_slots = rows * cols

    # Keep track of next sequence for new modules
    current_highest = 0
    prefix = f"SG-{installation.id:02d}-P"
    pattern = re.compile(rf"^SG-{installation.id:02d}-P(\d+)$")
    for p in installation.panels.all():
        if p.permanent_id:
            m = pattern.match(p.permanent_id)
            if m:
                try:
                    num = int(m.group(1))
                    if num > current_highest:
                        current_highest = num
                except ValueError:
                    pass

    for r in range(1, rows + 1):
        for c in range(1, cols + 1):
            if panel_idx < len(existing_panels):
                p = existing_panels[panel_idx]
                perm_id = p.permanent_id or f"{prefix}{p.id:03d}"
                serial = p.serial_number or perm_id
                panel_idx += 1
            else:
                current_highest += 1
                perm_id = f"{prefix}{current_highest:03d}"
                serial = perm_id

            active_cells.append({
                'row': r,
                'col': c,
                'panel_id': perm_id,
                'serial_number': serial,
                'status': 'active'
            })

    draft_revision.grid_rows = rows
    draft_revision.grid_cols = cols
    draft_revision.layout_data = {
        'rows': rows,
        'cols': cols,
        'active_cells': active_cells
    }
    draft_revision.status = 'draft'
    draft_revision.submitted_by = user
    draft_revision.save(update_fields=['grid_rows', 'grid_cols', 'layout_data', 'status', 'submitted_by', 'updated_at'])
    return draft_revision


def save_draft_layout(
    draft_revision: LayoutRevision,
    grid_rows: int,
    grid_cols: int,
    active_cells: List[Dict[str, Any]],
    user
) -> Tuple[bool, Optional[str]]:
    """
    Saves work-in-progress layout changes to a draft revision.
    Validates arrangement without altering live physical panel records.
    """
    installation = draft_revision.installation
    is_valid, err = validate_layout_data(installation, grid_rows, grid_cols, active_cells)
    if not is_valid:
        return False, err

    draft_revision.grid_rows = grid_rows
    draft_revision.grid_cols = grid_cols
    draft_revision.layout_data = {
        'rows': grid_rows,
        'cols': grid_cols,
        'active_cells': active_cells
    }
    draft_revision.status = 'draft'
    draft_revision.submitted_by = user
    draft_revision.save(update_fields=['grid_rows', 'grid_cols', 'layout_data', 'status', 'submitted_by', 'updated_at'])
    return True, None


def submit_draft_for_verification(draft_revision: LayoutRevision, user) -> Tuple[bool, Optional[str]]:
    """
    Validates and submits a draft layout revision for technician/admin verification.
    Transitions status to 'pending_verification'.
    """
    layout_data = draft_revision.layout_data or {}
    active_cells = layout_data.get('active_cells', [])
    rows = draft_revision.grid_rows
    cols = draft_revision.grid_cols

    if not active_cells:
        return False, "Cannot submit an empty layout. Please place at least one solar panel module in the grid."

    is_valid, err = validate_layout_data(draft_revision.installation, rows, cols, active_cells)
    if not is_valid:
        return False, err

    draft_revision.status = 'pending_verification'
    draft_revision.submitted_by = user
    draft_revision.submitted_at = timezone.now()
    draft_revision.save(update_fields=['status', 'submitted_by', 'submitted_at', 'updated_at'])
    return True, None


def cancel_draft_revision(draft_revision: LayoutRevision, user) -> bool:
    """
    Cancels draft editing and discards unsubmitted draft changes.
    Preserves active verified layout and live panel coordinates.
    """
    if draft_revision.status in ['draft', 'changes_requested']:
        draft_revision.delete()
        return True
    return False


def apply_approved_layout(
    revision: LayoutRevision,
    reviewer_user,
    review_notes: str = ""
) -> Tuple[bool, Optional[str]]:
    """
    ATOMIC VERIFICATION & LIVE LAYOUT APPLICATION:
    1. Validates layout arrangement.
    2. Supersedes previous verified layouts for this installation.
    3. Atomically updates physical panel coordinates (grid_row, grid_col).
    4. Creates newly approved physical panels in DB.
    5. Retires explicitly removed panels (status='retired', grid_row=None, grid_col=None).
    6. Preserves all historical inspections, uploads, and maintenance logs.
    7. Marks revision as 'verified'.
    """
    installation = revision.installation
    layout_data = revision.layout_data or {}
    active_cells = layout_data.get('active_cells', [])
    rows = revision.grid_rows
    cols = revision.grid_cols

    # Legacy fallback: if active_cells is empty, populate from installation's existing active panels
    if not active_cells:
        inst_panels = installation.panels.filter(status='active')
        if inst_panels.exists():
            active_cells = []
            for p in inst_panels:
                r = p.grid_row or 1
                c = p.grid_col or 1
                active_cells.append({
                    'row': r,
                    'col': c,
                    'panel_id': p.permanent_id or p.serial_number,
                    'serial_number': p.serial_number,
                    'status': 'active'
                })
                if r > rows:
                    rows = r
                if c > cols:
                    cols = c
            revision.grid_rows = rows
            revision.grid_cols = cols
            revision.layout_data = {'rows': rows, 'cols': cols, 'active_cells': active_cells}

    is_valid, err = validate_layout_data(installation, rows, cols, active_cells)
    if not is_valid:
        return False, f"Cannot verify invalid layout: {err}"

    if not active_cells:
        return False, "Cannot verify an empty layout without physical panels."

    with transaction.atomic():
        # 1. Supersede any existing active verified layouts
        installation.layout_revisions.filter(status='verified').update(status='superseded')

        # 2. Map existing active panels in DB
        db_panels = {p.permanent_id: p for p in installation.panels.all() if p.permanent_id}
        placed_panel_ids = set()

        # 3. Apply coordinates to active cells & create new panels
        for cell in active_cells:
            pid = cell['panel_id']
            row = cell['row']
            col = cell['col']
            placed_panel_ids.add(pid)

            if pid in db_panels:
                panel = db_panels[pid]
                panel.grid_row = row
                panel.grid_col = col
                panel.status = 'active'
                panel.save(update_fields=['grid_row', 'grid_col', 'status'])
            else:
                # Brand new panel approved in layout
                target_serial = cell.get('serial_number') or pid
                if Panel.objects.filter(serial_number=target_serial).exists():
                    target_serial = f"{target_serial}-{installation.id}"
                    if Panel.objects.filter(serial_number=target_serial).exists():
                        target_serial = f"{target_serial}-{timezone.now().strftime('%f')}"

                Panel.objects.create(
                    installation=installation,
                    permanent_id=pid,
                    serial_number=target_serial,
                    site_location=installation.site_address or installation.name,
                    grid_row=row,
                    grid_col=col,
                    status='active',
                    user=installation.owner
                )

        # 4. Safely retire panels that were removed from the arrangement
        # Never delete records or inspections!
        for pid, panel in db_panels.items():
            if pid not in placed_panel_ids and panel.status == 'active':
                panel.status = 'retired'
                panel.grid_row = None
                panel.grid_col = None
                panel.save(update_fields=['status', 'grid_row', 'grid_col'])

        # 5. Mark revision as Verified
        revision.status = 'verified'
        revision.reviewed_by = reviewer_user
        revision.reviewed_at = timezone.now()
        revision.review_notes = review_notes or "Layout verified and applied to live installation array."
        revision.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'review_notes', 'updated_at'])

    return True, None
