"""
SolarGuard — PDF Receipt Generator for Verified Test Mode Payments.

Produces clean, branded, audit-compliant PDF receipts for successfully verified
Razorpay Sandbox / Test Mode transactions using ReportLab.
Clearly marks all documents with: TEST PAYMENT — NO REAL MONEY COLLECTED.
"""

import io
import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
)
from django.utils import timezone

from .models import PaymentTransaction


def get_receipt_styles():
    """Builds branded paragraph styles for PDF receipts."""
    styles = getSampleStyleSheet()

    brand_emerald = colors.HexColor("#176B52")
    brand_ink = colors.HexColor("#192B27")
    brand_muted = colors.HexColor("#6C757D")
    test_warning = colors.HexColor("#B45309")
    test_bg = colors.HexColor("#FEF3C7")

    styles.add(ParagraphStyle(
        name='ReceiptTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=brand_emerald,
        spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        name='ReceiptSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=brand_muted,
        spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name='TestNotice',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=test_warning,
        alignment=1,  # Center
    ))
    styles.add(ParagraphStyle(
        name='SectionHeader',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=brand_ink,
        spaceBefore=8,
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name='ReceiptBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=brand_ink,
    ))
    styles.add(ParagraphStyle(
        name='ReceiptBodyBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=13,
        textColor=brand_ink,
    ))
    styles.add(ParagraphStyle(
        name='ReceiptMuted',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=brand_muted,
    ))
    styles.add(ParagraphStyle(
        name='ReceiptTableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.white,
    ))
    styles.add(ParagraphStyle(
        name='ReceiptTableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=brand_ink,
    ))
    styles.add(ParagraphStyle(
        name='ReceiptTableCellRight',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=brand_ink,
        alignment=2,  # Right
    ))
    styles.add(ParagraphStyle(
        name='ReceiptTotalCell',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=brand_emerald,
        alignment=2,  # Right
    ))
    styles.add(ParagraphStyle(
        name='ReceiptDisclaimer',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=7.5,
        leading=10.5,
        textColor=colors.HexColor("#555555"),
        alignment=1,  # Center
    ))
    return styles


def generate_payment_receipt_pdf(tx: PaymentTransaction) -> bytes:
    """
    Generates a professional PDF receipt for a verified PaymentTransaction.
    Returns the binary content of the PDF.
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

    styles = get_receipt_styles()
    story = []

    brand_emerald = colors.HexColor("#176B52")
    brand_subtle = colors.HexColor("#EBF5F1")
    amber_subtle = colors.HexColor("#FEF3C7")
    amber_border = colors.HexColor("#F59E0B")
    grey_border = colors.HexColor("#DEE2E6")

    issue = tx.issue
    panel = issue.panel
    installation = issue.installation or (panel.installation if panel else None)
    customer = tx.user or (issue.user if issue else None)

    # 1. Header Banner: SolarGuard Branding & Document Identification
    header_data = [
        [
            Paragraph("SolarGuard AI Monitoring", styles['ReceiptTitle']),
            Paragraph(f"<b>RECEIPT NUMBER:</b><br/>{tx.receipt_number or 'SG-RCP-PENDING'}", styles['ReceiptBodyBold']),
        ],
        [
            Paragraph("Clean Energy Asset Operations & Maintenance Management", styles['ReceiptSubtitle']),
            Paragraph(f"<b>Date:</b> {tx.verified_at.strftime('%B %d, %Y at %H:%M') if tx.verified_at else tx.created_at.strftime('%B %d, %Y')}", styles['ReceiptMuted']),
        ]
    ]
    header_table = Table(header_data, colWidths=[360, 180])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 8))

    # 2. Mandatory Demonstration Test Warning Banner
    test_warning_text = (
        "★ TEST PAYMENT — NO REAL MONEY COLLECTED ★<br/>"
        "<font size=8.5 color='#92400E'>This transaction was executed in Razorpay Sandbox (Test Mode) "
        "for academic demonstration purposes. No real bank accounts or credit cards were debited.</font>"
    )
    warning_table = Table(
        [[Paragraph(test_warning_text, styles['TestNotice'])]],
        colWidths=[540]
    )
    warning_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), amber_subtle),
        ('BOX', (0, 0), (-1, -1), 1.5, amber_border),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    story.append(warning_table)
    story.append(Spacer(1, 14))

    # 3. Transaction Summary & Parties Table
    parties_data = [
        [
            Paragraph("<b>CUSTOMER / BILLED TO:</b>", styles['ReceiptMuted']),
            Paragraph("<b>SERVICE DETAILS:</b>", styles['ReceiptMuted']),
        ],
        [
            Paragraph(
                f"<b>{customer.get_full_name() or customer.username}</b><br/>"
                f"Username: {customer.username}<br/>"
                f"Email: {customer.email or 'N/A'}<br/>"
                f"Site Address: {installation.site_address if installation else 'Standalone Module'}",
                styles['ReceiptBody']
            ),
            Paragraph(
                f"<b>Solar Installation:</b> {installation.name if installation else 'N/A'}<br/>"
                f"<b>Target Panel:</b> {panel.permanent_id or panel.serial_number}<br/>"
                f"<b>Work Order:</b> #{issue.id} — {issue.title}<br/>"
                f"<b>Assigned Tech:</b> {issue.assigned_technician.username if issue.assigned_technician else 'Pending'}",
                styles['ReceiptBody']
            ),
        ]
    ]
    parties_table = Table(parties_data, colWidths=[270, 270])
    parties_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F8F9FA")),
        ('BOX', (0, 0), (-1, -1), 1, grey_border),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(parties_table)
    story.append(Spacer(1, 14))

    # 4. Itemized Financial Breakdown Table
    items_data = [
        [
            Paragraph("Description of Services Rendered", styles['ReceiptTableHeader']),
            Paragraph("Type / Priority", styles['ReceiptTableHeader']),
            Paragraph("Status", styles['ReceiptTableHeader']),
            Paragraph("Amount (INR)", styles['ReceiptTableHeader']),
        ],
        [
            Paragraph(
                f"<b>Maintenance Service Fee — Work Order #{issue.id}</b><br/>"
                f"<font size=7.5 color='#6C757D'>Panel {panel.serial_number} at {installation.name if installation else 'Site'}. "
                f"Action item: {issue.description[:80] if issue.description else 'Field service & diagnosis'}</font>",
                styles['ReceiptTableCell']
            ),
            Paragraph(f"{issue.priority} Priority", styles['ReceiptTableCell']),
            Paragraph("Paid (Test Mode)", styles['ReceiptTableCell']),
            Paragraph(f"₹{tx.amount:.2f}", styles['ReceiptTableCellRight']),
        ],
        [
            Paragraph("SolarGuard Cloud Diagnostic & Report Generation", styles['ReceiptTableCell']),
            Paragraph("Automated", styles['ReceiptTableCell']),
            Paragraph("Included", styles['ReceiptTableCell']),
            Paragraph("₹0.00", styles['ReceiptTableCellRight']),
        ],
        [
            Paragraph("Test Sandbox Processing Fee (Razorpay Sandbox)", styles['ReceiptTableCell']),
            Paragraph("Gateway Test", styles['ReceiptTableCell']),
            Paragraph("Waived (₹0.00)", styles['ReceiptTableCell']),
            Paragraph("₹0.00", styles['ReceiptTableCellRight']),
        ],
        [
            Paragraph("<b>TOTAL AMOUNT PAID (INR):</b>", styles['ReceiptTotalCell']),
            "", "",
            Paragraph(f"<b>₹{tx.amount:.2f}</b>", styles['ReceiptTotalCell']),
        ]
    ]

    items_table = Table(items_data, colWidths=[270, 95, 85, 90])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), brand_emerald),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -2), 0.5, grey_border),
        ('SPAN', (0, 4), (2, 4)),
        ('BACKGROUND', (0, 4), (-1, 4), brand_subtle),
        ('LINEABOVE', (0, 4), (-1, 4), 1.5, brand_emerald),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 14))

    # 5. Gateway Verification & Cryptographic Provenance
    story.append(Paragraph("Payment Gateway Provenance & Verification Details", styles['SectionHeader']))
    audit_data = [
        [
            Paragraph("<b>Gateway Environment:</b>", styles['ReceiptMuted']),
            Paragraph("Razorpay Test Mode / Sandbox (api.razorpay.com)", styles['ReceiptTableCell']),
        ],
        [
            Paragraph("<b>Razorpay Order ID:</b>", styles['ReceiptMuted']),
            Paragraph(f"<font name='Courier'>{tx.razorpay_order_id}</font>", styles['ReceiptTableCell']),
        ],
        [
            Paragraph("<b>Razorpay Payment ID:</b>", styles['ReceiptMuted']),
            Paragraph(f"<font name='Courier'>{tx.razorpay_payment_id or 'N/A'}</font>", styles['ReceiptTableCell']),
        ],
        [
            Paragraph("<b>Signature Verification:</b>", styles['ReceiptMuted']),
            Paragraph("<b>PASSED</b> (Server-side HMAC-SHA256 signature verified against secret key)", styles['ReceiptTableCell']),
        ],
        [
            Paragraph("<b>Currency / Sub-units:</b>", styles['ReceiptMuted']),
            Paragraph(f"{tx.currency} &bull; {tx.amount_paise} paise", styles['ReceiptTableCell']),
        ],
        [
            Paragraph("<b>Verification Timestamp:</b>", styles['ReceiptMuted']),
            Paragraph(str(tx.verified_at or timezone.now()), styles['ReceiptTableCell']),
        ],
    ]
    audit_table = Table(audit_data, colWidths=[160, 380])
    audit_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, colors.HexColor("#EEEEEE")),
    ]))
    story.append(audit_table)
    story.append(Spacer(1, 16))

    # 6. Legal / Academic Demonstration Disclaimer
    story.append(HRFlowable(width="100%", thickness=0.5, color=brand_emerald, spaceAfter=8))
    story.append(Paragraph(
        "<b>ACADEMIC DEMONSTRATION NOTICE:</b> This official test receipt was automatically generated by "
        "SolarGuard AI Monitoring System for academic and educational evaluation. Razorpay Test Mode credentials "
        "were utilized to simulate real-world e-commerce settlement. No real bank accounts, UPI IDs, or credit cards "
        "incurred actual financial charges. This document is verifiable via the local SolarGuard SQLite audit ledger.",
        styles['ReceiptDisclaimer']
    ))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "SolarGuard — Intelligent AI Photovoltaic Monitoring & Maintenance Platform &bull; All Rights Reserved",
        styles['ReceiptDisclaimer']
    ))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
