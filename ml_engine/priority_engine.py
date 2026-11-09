"""
SolarGuard — Transparent Rules-Based Maintenance Prioritization Engine

Deterministic expert triage system using strictly real inputs:
1. Real MobileNetV2 CNN visual finding (Surface-Damage, Bird-Dropping, Dusty, Normal, Unable to assess)
2. Stored user cleaning date (if recorded)
3. Verified historical inspection records in database (if any)

Outputs clear, actionable categories:
- 'Manual Inspection Recommended'
- 'Cleaning Recommended'
- 'Routine'
- 'Unable to Assess'

Does NOT fabricate sensor readings, energy loss percentages, or safety guarantees.
"""

def calculate_maintenance_priority(panel, visual_finding="Normal"):
    """
    Computes a transparent maintenance recommendation from real known inputs.
    """
    vf = (visual_finding or "").lower()
    breakdown = []
    
    # Check actual recorded cleaning history
    days_cleaning = panel.days_since_last_cleaning if hasattr(panel, 'days_since_last_cleaning') else None
    fault_count = panel.fault_count_last_6_months if hasattr(panel, 'fault_count_last_6_months') else 0

    # Rule 1: Surface Fracture / Physical Damage
    if 'damage' in vf or 'crack' in vf:
        level = "Manual Inspection Recommended"
        summary_advice = (
            "Visible surface anomaly or fracture detected on panel face. "
            "Recommend physical close-up verification by a qualified technician to assess module glass/cell integrity."
        )
        breakdown.append(f"Visual anomaly: Surface-Damage detected ('{visual_finding}').")
        if fault_count > 0:
            breakdown.append(f"{fault_count} prior anomalous inspections recorded for this panel in the past 6 months.")

    # Rule 2: Opaque Organic Soiling (Bird Droppings)
    elif 'bird' in vf:
        level = "Cleaning Recommended"
        summary_advice = (
            "Localized opaque soiling detected. Recommend surface cleaning using demineralized water "
            "and soft sponge to eliminate reverse-bias hot-spot risk."
        )
        breakdown.append("Visual anomaly: Bird-Dropping (localized opaque obstruction).")
        if days_cleaning is not None:
            breakdown.append(f"Last recorded wash: {days_cleaning} days ago.")
        else:
            breakdown.append("Cleaning history: Not recorded for this panel.")

    # Rule 3: Uniform Particulate Soiling (Dust)
    elif 'dust' in vf:
        level = "Cleaning Recommended"
        summary_advice = (
            "Particulate dust accumulation detected. Schedule routine washing during early morning "
            "or evening hours to restore light transmission."
        )
        breakdown.append("Visual anomaly: Dusty (surface particulate soiling).")
        if days_cleaning is not None:
            if days_cleaning >= 60:
                breakdown.append(f"Extended interval since last wash: {days_cleaning} days.")
            else:
                breakdown.append(f"Last recorded wash was {days_cleaning} days ago.")
        else:
            breakdown.append("Cleaning history: Not recorded for this panel.")

    # Rule 4: Inconclusive / Image Quality Triage
    elif 'unable' in vf or 'retake' in vf:
        level = "Unable to Assess"
        summary_advice = (
            "Image clarity, lighting, or focus was insufficient for reliable screening. "
            "Please capture a clear, well-lit photograph facing the panel."
        )
        breakdown.append("Quality triage: photograph is unreadable, blurred, or outside standard illumination.")

    # Rule 5: AI Model Unavailable / Inference Failed
    elif 'unavailable' in vf or 'offline' in vf or 'failed' in vf or 'error' in vf or 'missing' in vf:
        level = "Unable to Assess"
        summary_advice = (
            "AI visual screening was offline or unavailable during screening. "
            "Visual condition cannot be confirmed automatically. "
            "Manual on-site inspection or photo re-inspection is recommended to verify panel status."
        )
        breakdown.append("Visual screening: AI Model Unavailable (inference did not complete).")
        # Independent maintenance rule check: cleaning interval
        if days_cleaning is not None:
            if days_cleaning >= 90:
                level = "Cleaning Recommended"
                breakdown.append(f"Independent Rule: {days_cleaning} days since last recorded wash (preventive wash interval exceeded, independent of visual screening).")
            else:
                breakdown.append(f"Independent Rule: Last recorded wash was {days_cleaning} days ago.")
        else:
            breakdown.append("Independent Rule: Panel cleaning history not recorded.")

    # Rule 6: Verified or Detected Normal Surface
    elif 'normal' in vf or 'clean' in vf or vf == '':
        if days_cleaning is not None and days_cleaning >= 90:
            level = "Cleaning Recommended"
            summary_advice = (
                "Surface appears visually clear, but recorded interval since last washing exceeds 90 days. "
                "Routine wash recommended as preventive maintenance."
            )
            breakdown.append("Visual condition: Normal (no supported visible anomalies).")
            breakdown.append(f"Preventive wash due: {days_cleaning} days since last recorded wash.")
        else:
            level = "Routine"
            summary_advice = (
                "No supported visible surface anomalies detected. Continue standard monitoring. "
                "Note: RGB photography screens visible surface defects only; it does not verify internal electrical performance."
            )
            breakdown.append("Visual condition: Normal.")
            if days_cleaning is not None:
                breakdown.append(f"Cleaned {days_cleaning} days ago.")
            else:
                breakdown.append("Standard periodic maintenance applies.")

    # Rule 7: Fallback for any other unrecognized or inconclusive finding
    else:
        level = "Unable to Assess"
        summary_advice = (
            f"Visual finding '{visual_finding}' is inconclusive or unrecognized. "
            "Manual visual inspection recommended to confirm panel condition."
        )
        breakdown.append(f"Inconclusive visual finding: '{visual_finding}'.")

    explanation_text = " | ".join(breakdown)

    return {
        'priority_level': level,
        'summary_advice': summary_advice,
        'breakdown': breakdown,
        'explanation_text': explanation_text,
        'priority_score': 0, # Legacy field kept safe for backwards compatibility
        'engine': 'Transparent Rules-Based Operational Triage'
    }
