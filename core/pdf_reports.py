"""
SolarGuard PDF Report Generator.
Generates clean, professional PDF reports for:
1. Individual Panel Inspection & Maintenance Record
2. Installation Condition Summary Report
3. Maintenance History & Work Order Audit Report

All reports contain only real database records and explicit disclaimers on optical RGB limitations.
No synthetic telemetry, fabricated power curves, or imaginary health percentages.
"""

import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
)
from django.http import HttpResponse


def get_sg_styles():
    """Builds branded paragraph styles."""
    styles = getSampleStyleSheet()
    
    brand_emerald = colors.HexColor("#176B52")
    brand_ink = colors.HexColor("#192B27")
    brand_muted = colors.HexColor("#6C757D")
    
    styles.add(ParagraphStyle(
        name='SGTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=brand_emerald,
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name='SGSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=brand_muted,
        spaceAfter=12,
    ))
    styles.add(ParagraphStyle(
        name='SGSectionHeader',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=brand_ink,
        spaceBefore=10,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name='SGBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=brand_ink,
    ))
    styles.add(ParagraphStyle(
        name='SGBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=13,
        textColor=brand_ink,
    ))
    styles.add(ParagraphStyle(
        name='SGMuted',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=brand_muted,
    ))
    styles.add(ParagraphStyle(
        name='SGDisclaimer',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#555555"),
    ))
    styles.add(ParagraphStyle(
        name='TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=11,
        textColor=colors.white,
    ))
    styles.add(ParagraphStyle(
        name='TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=brand_ink,
    ))
    return styles


def generate_panel_report_pdf(panel, derived_condition, inspections, issues):
    """
    Builds a PDF report for an individual solar panel.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    styles = get_sg_styles()
    story = []

    # Header
    panel_label = panel.permanent_id or panel.serial_number
    story.append(Paragraph("SolarGuard &bull; Panel Inspection & Maintenance Record", styles['SGTitle']))
    story.append(Paragraph(
        f"Installation: {panel.installation.name if panel.installation else 'Unlinked'} | Panel: {panel_label}",
        styles['SGSubtitle']
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#176B52"), spaceAfter=10))

    # Panel Details Table
    inst_name = panel.installation.name if panel.installation else "N/A"
    inst_address = panel.installation.site_address if panel.installation else "N/A"
    coords = f"Row {panel.grid_row or '?'}, Col {panel.grid_col or '?'}"
    status_str = "Active Module" if panel.status == 'active' else "Retired Module (Preserved History)"
    last_cleaned = panel.last_cleaned_date.strftime("%Y-%m-%d") if panel.last_cleaned_date else "No record"
    install_date = panel.install_date.strftime("%Y-%m-%d") if panel.install_date else "Not specified"

    meta_data = [
        [
            Paragraph("<b>Permanent ID:</b>", styles['SGBold']), Paragraph(panel.permanent_id or "Pending", styles['SGBody']),
            Paragraph("<b>Serial Number:</b>", styles['SGBold']), Paragraph(panel.serial_number or "N/A", styles['SGBody']),
        ],
        [
            Paragraph("<b>Installation:</b>", styles['SGBold']), Paragraph(inst_name, styles['SGBody']),
            Paragraph("<b>Site Address:</b>", styles['SGBold']), Paragraph(inst_address, styles['SGBody']),
        ],
        [
            Paragraph("<b>Grid Position:</b>", styles['SGBold']), Paragraph(coords, styles['SGBody']),
            Paragraph("<b>Status:</b>", styles['SGBold']), Paragraph(status_str, styles['SGBody']),
        ],
        [
            Paragraph("<b>Commission Date:</b>", styles['SGBold']), Paragraph(install_date, styles['SGBody']),
            Paragraph("<b>Last Cleaned:</b>", styles['SGBold']), Paragraph(last_cleaned, styles['SGBody']),
        ],
    ]
    meta_table = Table(meta_data, colWidths=[100, 170, 90, 180])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8F9FA")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#DEE2E6")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 12))

    # Current Condition Banner
    story.append(Paragraph("Current Surface Visual Condition", styles['SGSectionHeader']))
    cond_label = derived_condition.get('label', 'Not Inspected')
    cond_detail = derived_condition.get('detail', 'No inspection photographs on file.')
    
    cond_color = colors.HexColor("#176B52") if derived_condition['status'] == 'normal' else (
        colors.HexColor("#D6A545") if derived_condition['status'] in ('dust', 'bird') else (
            colors.HexColor("#DC3545") if derived_condition['status'] == 'damage' else colors.HexColor("#6C757D")
        )
    )

    cond_data = [
        [
            Paragraph(f"<b>Status:</b> {cond_label}", styles['SGBold']),
            Paragraph(cond_detail, styles['SGBody'])
        ]
    ]
    cond_table = Table(cond_data, colWidths=[180, 360])
    cond_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F4F7F5")),
        ('BOX', (0, 0), (-1, -1), 1.5, cond_color),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(cond_table)
    story.append(Spacer(1, 12))

    # Inspection History
    story.append(Paragraph("Inspection History", styles['SGSectionHeader']))
    if inspections.exists():
        insp_rows = [[
            Paragraph("Date", styles['TableHeader']),
            Paragraph("AI Finding", styles['TableHeader']),
            Paragraph("Confidence", styles['TableHeader']),
            Paragraph("Review State", styles['TableHeader']),
            Paragraph("Technician Verification", styles['TableHeader']),
        ]]
        for insp in inspections[:10]:
            conf_str = f"{insp.confidence_score:.1f}%" if insp.confidence_score else "N/A"
            review_state = insp.get_review_status_display()
            tech_finding = insp.verified_finding or "Pending field review" if insp.review_status == 'ai_predicted' else (insp.verified_finding or "Verified")
            insp_rows.append([
                Paragraph(insp.inspected_at.strftime("%Y-%m-%d"), styles['TableCell']),
                Paragraph(insp.predicted_class, styles['TableCell']),
                Paragraph(conf_str, styles['TableCell']),
                Paragraph(review_state, styles['TableCell']),
                Paragraph(tech_finding, styles['TableCell']),
            ])
        insp_table = Table(insp_rows, colWidths=[70, 110, 65, 125, 170])
        insp_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#176B52")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#DEE2E6")),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8F9FA")]),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(insp_table)
    else:
        story.append(Paragraph("No optical inspections recorded for this panel yet.", styles['SGMuted']))
    story.append(Spacer(1, 12))

    # Maintenance History
    story.append(Paragraph("Maintenance & Work Order History", styles['SGSectionHeader']))
    if issues.exists():
        m_rows = [[
            Paragraph("Ticket #", styles['TableHeader']),
            Paragraph("Date", styles['TableHeader']),
            Paragraph("Title", styles['TableHeader']),
            Paragraph("Status", styles['TableHeader']),
            Paragraph("Technician", styles['TableHeader']),
            Paragraph("Resolution Notes", styles['TableHeader']),
        ]]
        for issue in issues[:8]:
            tech_str = issue.assigned_technician.username if issue.assigned_technician else "Unassigned"
            res_notes = (issue.resolution_notes[:60] + "...") if issue.resolution_notes and len(issue.resolution_notes) > 60 else (issue.resolution_notes or "—")
            m_rows.append([
                Paragraph(f"#{issue.id}", styles['TableCell']),
                Paragraph(issue.created_at.strftime("%Y-%m-%d"), styles['TableCell']),
                Paragraph(issue.title[:30], styles['TableCell']),
                Paragraph(issue.status, styles['TableCell']),
                Paragraph(tech_str, styles['TableCell']),
                Paragraph(res_notes, styles['TableCell']),
            ])
        m_table = Table(m_rows, colWidths=[45, 65, 115, 65, 85, 165])
        m_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#192B27")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#DEE2E6")),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8F9FA")]),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(m_table)
    else:
        story.append(Paragraph("No maintenance work orders logged for this panel.", styles['SGMuted']))
    story.append(Spacer(1, 16))

    # Explicit Optical Limitations Disclaimer
    story.append(KeepTogether([
        HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CCCCCC"), spaceAfter=6),
        Paragraph(
            "<b>Technical Notice & Optical Classification Limitations:</b> This report reflects visual surface findings "
            "derived from 2D RGB photography analyzed by the SolarGuard MobileNetV2 classifier. Optical photography cannot "
            "verify internal electrical output, bypass diode integrity, junction box connectivity, micro-cracks invisible to "
            "the visual spectrum, or inverter power conversion. Model confidence scores reflect classifier certainty and do "
            "not equal physical degradation or electrical efficiency percentages. Physical verification by a certified technician "
            "is required to confirm electrical health.",
            styles['SGDisclaimer']
        )
    ]))

    doc.build(story)
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    filename = f"SolarGuard_Panel_Report_{panel_label}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def generate_installation_report_pdf(installation, breakdown, panel_summaries, active_issues):
    """
    Builds a PDF report summarizing an entire solar installation.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    styles = get_sg_styles()
    story = []

    # Header
    story.append(Paragraph("SolarGuard &bull; Installation Condition Summary Report", styles['SGTitle']))
    story.append(Paragraph(
        f"Site: {installation.name} | Address: {installation.site_address}",
        styles['SGSubtitle']
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#176B52"), spaceAfter=10))

    # Installation Overview Table
    owner_str = installation.owner.username if installation.owner else "N/A"
    tech_str = installation.assigned_technician.username if installation.assigned_technician else "Unassigned"
    install_date = installation.install_date.strftime("%Y-%m-%d") if installation.install_date else "Not specified"
    inst_type = installation.get_installation_type_display() if hasattr(installation, 'get_installation_type_display') else installation.installation_type

    meta_data = [
        [
            Paragraph("<b>Installation Name:</b>", styles['SGBold']), Paragraph(installation.name, styles['SGBody']),
            Paragraph("<b>Owner Account:</b>", styles['SGBold']), Paragraph(owner_str, styles['SGBody']),
        ],
        [
            Paragraph("<b>Site Address:</b>", styles['SGBold']), Paragraph(installation.site_address or "N/A", styles['SGBody']),
            Paragraph("<b>Assigned Technician:</b>", styles['SGBold']), Paragraph(tech_str, styles['SGBody']),
        ],
        [
            Paragraph("<b>Installation Type:</b>", styles['SGBold']), Paragraph(inst_type or "Rooftop", styles['SGBody']),
            Paragraph("<b>Commission Date:</b>", styles['SGBold']), Paragraph(install_date, styles['SGBody']),
        ],
    ]
    meta_table = Table(meta_data, colWidths=[110, 160, 110, 160])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8F9FA")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#DEE2E6")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 10))

    # Fleet Health Metric Summary
    story.append(Paragraph("Fleet Condition Breakdown (Active Modules)", styles['SGSectionHeader']))
    summary_data = [
        [
            Paragraph("Active Panels", styles['TableHeader']),
            Paragraph("Appears Normal", styles['TableHeader']),
            Paragraph("Needs Cleaning", styles['TableHeader']),
            Paragraph("Surface Damage", styles['TableHeader']),
            Paragraph("Uninspected", styles['TableHeader']),
            Paragraph("Retired (Excluded)", styles['TableHeader']),
        ],
        [
            Paragraph(str(breakdown['total_active']), styles['SGBold']),
            Paragraph(str(breakdown['normal']), styles['TableCell']),
            Paragraph(str(breakdown['cleaning']), styles['TableCell']),
            Paragraph(str(breakdown['damage']), styles['TableCell']),
            Paragraph(str(breakdown['not_inspected']), styles['TableCell']),
            Paragraph(str(breakdown['total_retired']), styles['TableCell']),
        ]
    ]
    summary_table = Table(summary_data, colWidths=[90, 90, 90, 90, 90, 90])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#176B52")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#DEE2E6")),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#F4F7F5")),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 10))

    # Panel Inventory Condition Table
    story.append(Paragraph("Module Condition Inventory", styles['SGSectionHeader']))
    p_rows = [[
        Paragraph("Panel ID", styles['TableHeader']),
        Paragraph("Grid Pos", styles['TableHeader']),
        Paragraph("Status", styles['TableHeader']),
        Paragraph("Latest Finding", styles['TableHeader']),
        Paragraph("Inspection Date", styles['TableHeader']),
        Paragraph("Active Work Order", styles['TableHeader']),
    ]]
    for item in panel_summaries[:15]:
        p = item['panel']
        cond = item['condition']
        p_id = p.permanent_id or p.serial_number
        coords = f"R{p.grid_row or '?'}:C{p.grid_col or '?'}"
        mod_status = "Retired" if item['is_retired'] else "Active"
        insp_date = cond['inspection'].inspected_at.strftime("%Y-%m-%d") if cond.get('inspection') else "Never"
        work_order = f"#{item['open_issue'].id} ({item['open_issue'].status})" if item['open_issue'] else "None"

        p_rows.append([
            Paragraph(p_id, styles['TableCell']),
            Paragraph(coords, styles['TableCell']),
            Paragraph(mod_status, styles['TableCell']),
            Paragraph(cond['label'], styles['TableCell']),
            Paragraph(insp_date, styles['TableCell']),
            Paragraph(work_order, styles['TableCell']),
        ])
    p_table = Table(p_rows, colWidths=[90, 60, 60, 130, 90, 110])
    p_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#192B27")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#DEE2E6")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8F9FA")]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(p_table)
    story.append(Spacer(1, 14))

    # Disclaimer
    story.append(KeepTogether([
        HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CCCCCC"), spaceAfter=6),
        Paragraph(
            "<b>Technical Notice & Optical Classification Limitations:</b> Optical inspection reflects observable surface "
            "features only. Uninspected panels are explicitly designated 'Not Inspected' and are never assumed healthy. "
            "SolarGuard does not synthesize power curves, kwH production, or efficiency percentages from photographs. "
            "Comprehensive system verification requires physical testing by certified personnel.",
            styles['SGDisclaimer']
        )
    ]))

    doc.build(story)
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    safe_name = installation.name.replace(" ", "_")
    response['Content-Disposition'] = f'attachment; filename="SolarGuard_Installation_Report_{safe_name}.pdf"'
    return response


def generate_maintenance_report_pdf(issues_list, stats, selected_installation):
    """
    Builds a PDF report for maintenance issues and work order history.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    styles = get_sg_styles()
    story = []

    # Header
    scope_str = f"Installation: {selected_installation.name}" if selected_installation else "All Accessible Solar Sites"
    story.append(Paragraph("SolarGuard &bull; Maintenance History & Work Order Audit Report", styles['SGTitle']))
    story.append(Paragraph(scope_str, styles['SGSubtitle']))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#176B52"), spaceAfter=10))

    # Summary Stats Table
    stats_data = [
        [
            Paragraph("Total Work Orders", styles['TableHeader']),
            Paragraph("Open", styles['TableHeader']),
            Paragraph("Assigned", styles['TableHeader']),
            Paragraph("In Progress", styles['TableHeader']),
            Paragraph("Resolved", styles['TableHeader']),
            Paragraph("Closed", styles['TableHeader']),
        ],
        [
            Paragraph(str(stats['total']), styles['SGBold']),
            Paragraph(str(stats['open']), styles['TableCell']),
            Paragraph(str(stats['assigned']), styles['TableCell']),
            Paragraph(str(stats['in_progress']), styles['TableCell']),
            Paragraph(str(stats['resolved']), styles['TableCell']),
            Paragraph(str(stats['closed']), styles['TableCell']),
        ]
    ]
    stats_table = Table(stats_data, colWidths=[90, 90, 90, 90, 90, 90])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#176B52")),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#DEE2E6")),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor("#F4F7F5")),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(stats_table)
    story.append(Spacer(1, 12))

    # Work Order Table
    story.append(Paragraph("Maintenance Work Order Log", styles['SGSectionHeader']))
    if issues_list:
        rows = [[
            Paragraph("Ticket #", styles['TableHeader']),
            Paragraph("Date", styles['TableHeader']),
            Paragraph("Panel / Installation", styles['TableHeader']),
            Paragraph("Title", styles['TableHeader']),
            Paragraph("Status", styles['TableHeader']),
            Paragraph("Technician", styles['TableHeader']),
            Paragraph("Resolution Notes", styles['TableHeader']),
        ]]
        for issue in issues_list[:15]:
            p_label = issue.panel.permanent_id or issue.panel.serial_number if issue.panel else "Site"
            tech_str = issue.assigned_technician.username if issue.assigned_technician else "Unassigned"
            res_str = (issue.resolution_notes[:50] + "...") if issue.resolution_notes and len(issue.resolution_notes) > 50 else (issue.resolution_notes or "—")
            rows.append([
                Paragraph(f"#{issue.id}", styles['TableCell']),
                Paragraph(issue.created_at.strftime("%Y-%m-%d"), styles['TableCell']),
                Paragraph(p_label, styles['TableCell']),
                Paragraph(issue.title[:25], styles['TableCell']),
                Paragraph(issue.status, styles['TableCell']),
                Paragraph(tech_str, styles['TableCell']),
                Paragraph(res_str, styles['TableCell']),
            ])
        w_table = Table(rows, colWidths=[45, 60, 90, 110, 60, 75, 100])
        w_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#192B27")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#DEE2E6")),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8F9FA")]),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(w_table)
    else:
        story.append(Paragraph("No maintenance records found for the selected scope.", styles['SGMuted']))
    story.append(Spacer(1, 14))

    # Disclaimer
    story.append(KeepTogether([
        HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CCCCCC"), spaceAfter=6),
        Paragraph(
            "<b>Audit Compliance Note:</b> All maintenance records are immutable database entries reflecting actual technician "
            "actions and administrator assignments. Work orders marked 'Resolved' reflect recorded field services and do not "
            "automatically alter historical AI optical inspection findings.",
            styles['SGDisclaimer']
        )
    ]))

    doc.build(story)
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="SolarGuard_Maintenance_History_Report.pdf"'
    return response
